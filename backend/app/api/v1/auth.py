import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt as jose_jwt
from slowapi import Limiter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.core.redis import add_token_to_blacklist, is_token_blacklisted, redis_client
from app.core.security import (
    JWTError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User
from app.schemas.auth import LogoutRequest, RefreshRequest, TokenResponse

_bearer_scheme = HTTPBearer()

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Google OAuth 2.0 constants
# ---------------------------------------------------------------------------
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
# Google ID tokens may use either issuer value
_GOOGLE_VALID_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}

# Cache Google's public keys (JWKS) for ID token verification
_jwks_cache: dict | None = None
_jwks_cache_time: float = 0
_JWKS_CACHE_TTL = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
def _get_client_ip(request: Request) -> str:
    if settings.trusted_proxy:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_get_client_ip, storage_uri=settings.redis_url)


# ---------------------------------------------------------------------------
# Google JWKS + ID token verification
# ---------------------------------------------------------------------------
async def _get_google_jwks() -> dict:
    """Fetch and cache Google's JSON Web Key Set."""
    global _jwks_cache, _jwks_cache_time
    now = time.time()
    if _jwks_cache and now - _jwks_cache_time < _JWKS_CACHE_TTL:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(GOOGLE_JWKS_URL, timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cache_time = now
        return _jwks_cache


async def _verify_google_id_token(id_token_str: str, access_token: str | None = None) -> dict:
    """Verify a Google-issued ID token's signature, audience, issuer, and expiry."""
    global _jwks_cache_time

    jwks = await _get_google_jwks()
    header = jose_jwt.get_unverified_header(id_token_str)
    kid = header.get("kid")

    # Find the signing key that matches the token's key ID
    key = next((k for k in jwks.get("keys", []) if k["kid"] == kid), None)

    if key is None:
        # Key might have rotated — refresh cache once and retry
        _jwks_cache_time = 0
        jwks = await _get_google_jwks()
        key = next((k for k in jwks.get("keys", []) if k["kid"] == kid), None)
        if key is None:
            raise ValueError("No matching Google signing key found")

    # Decode with signature + audience + expiry checks, but verify issuer
    # manually because Google may use either of two issuer values.
    claims = jose_jwt.decode(
        id_token_str,
        key,
        algorithms=["RS256"],
        audience=settings.google_client_id,
        access_token=access_token,
        options={"verify_iss": False},
    )
    if claims.get("iss") not in _GOOGLE_VALID_ISSUERS:
        raise ValueError(f"Invalid issuer: {claims.get('iss')}")
    return claims


def _check_google_configured() -> None:
    """Raise 503 if Google OAuth is not configured."""
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )


# ---------------------------------------------------------------------------
# Google OAuth endpoints
# ---------------------------------------------------------------------------
@router.get("/google/login")
@limiter.limit("20/minute")
async def google_login(request: Request) -> RedirectResponse:
    """Redirect the user to Google's OAuth 2.0 consent screen."""
    _check_google_configured()

    state = secrets.token_urlsafe(32)
    await redis_client.setex(f"oauth_state:{state}", 600, "1")

    callback_url = str(request.url_for("google_callback"))

    params = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
    )
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{params}", status_code=302)


@router.get("/google/callback")
@limiter.limit("20/minute")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Handle the OAuth 2.0 callback from Google."""
    frontend = settings.frontend_url

    # --- Error from Google (user denied, etc.) ---
    if error:
        logger.warning("Google OAuth error", error=error)
        return RedirectResponse(url=f"{frontend}/login#error=access_denied")

    if not code or not state:
        return RedirectResponse(url=f"{frontend}/login#error=missing_params")

    # --- Verify CSRF state (atomic delete to prevent replay) ---
    state_key = f"oauth_state:{state}"
    deleted = await redis_client.delete(state_key)
    if not deleted:
        logger.warning("Invalid or expired OAuth state")
        return RedirectResponse(url=f"{frontend}/login#error=invalid_state")

    # --- Exchange authorisation code for tokens ---
    callback_url = str(request.url_for("google_callback"))
    try:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": callback_url,
                },
                timeout=10,
            )
    except httpx.HTTPError:
        logger.exception("Failed to exchange Google auth code")
        return RedirectResponse(url=f"{frontend}/login#error=token_exchange_failed")

    if token_resp.status_code != 200:
        logger.error("Google token exchange failed", status=token_resp.status_code)
        return RedirectResponse(url=f"{frontend}/login#error=token_exchange_failed")

    token_data = token_resp.json()
    id_token_str = token_data.get("id_token")
    if not id_token_str:
        return RedirectResponse(url=f"{frontend}/login#error=no_id_token")
    access_token_str = token_data.get("access_token")

    # --- Verify the ID token (signature, audience, issuer, expiry) ---
    try:
        claims = await _verify_google_id_token(id_token_str, access_token=access_token_str)
    except Exception:
        logger.exception("Google ID token verification failed")
        return RedirectResponse(url=f"{frontend}/login#error=invalid_id_token")

    email: str | None = claims.get("email")
    email_verified: bool = claims.get("email_verified", False)
    google_id: str | None = claims.get("sub")

    if not email or not email_verified:
        return RedirectResponse(url=f"{frontend}/login#error=email_not_verified")

    # --- Enforce domain allowlist (if configured) ---
    if settings.google_allowed_domains:
        allowed = [d.strip().lower() for d in settings.google_allowed_domains.split(",") if d.strip()]
        domain = email.split("@")[1].lower()
        if allowed and domain not in allowed:
            logger.warning("Domain not allowed", email=email, domain=domain)
            return RedirectResponse(url=f"{frontend}/login#error=domain_not_allowed")

    # --- Find or create user ---
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            username=email,
            email=email,
            google_id=google_id,
            password_hash=None,
            role="admin",
        )
        session.add(user)
        try:
            await session.commit()
        except IntegrityError:
            # Concurrent first-login race — the other request won; re-fetch
            await session.rollback()
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user is None:
                return RedirectResponse(url=f"{frontend}/login#error=token_exchange_failed")
        else:
            await session.refresh(user)
            logger.info("User created via Google SSO", user_id=user.id, email=email)
    elif user.google_id and user.google_id != google_id:
        # Google ID mismatch — the email is linked to a different Google account
        logger.warning("Google ID mismatch", email=email, expected=user.google_id)
        return RedirectResponse(url=f"{frontend}/login#error=account_mismatch")
    elif not user.google_id:
        # Link existing user account to their Google identity
        user.google_id = google_id
        await session.commit()
        logger.info("Linked Google ID to existing user", user_id=user.id, email=email)

    # --- Issue application JWT tokens ---
    access_token = create_access_token(user.id, user.role, email=email)
    refresh_token = create_refresh_token(user.id, user.role)

    logger.info("User logged in via Google SSO", user_id=user.id, email=email)

    fragment = urlencode({"access_token": access_token, "refresh_token": refresh_token})
    return RedirectResponse(url=f"{frontend}/login#{fragment}", status_code=302)


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------
@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    body: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Exchange a valid refresh token for a new access + refresh token pair."""
    try:
        payload = decode_token(body.refresh_token)
    except JWTError as jwt_error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from jwt_error

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    old_jti = payload.get("jti")
    if old_jti and await is_token_blacklisted(old_jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    user_id = payload.get("sub")
    user = None
    if user_id:
        result = await session.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Rotate: blacklist the old refresh token
    if old_jti:
        old_exp = payload.get("exp", 0)
        ttl = max(int(old_exp - time.time()), 1)
        await add_token_to_blacklist(old_jti, ttl)

    return TokenResponse(
        access_token=create_access_token(user.id, user.role, email=user.email),
        refresh_token=create_refresh_token(user.id, user.role),
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest | None = None,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    _user: User = Depends(get_current_user),
) -> None:
    """Blacklist the access token (and optionally the refresh token) in Redis."""
    try:
        access_payload = decode_token(credentials.credentials)
        jti = access_payload.get("jti")
        exp = access_payload.get("exp", 0)
        if jti:
            ttl = max(int(exp - time.time()), 1)
            await add_token_to_blacklist(jti, ttl)
    except JWTError:
        pass

    if body and body.refresh_token:
        try:
            refresh_payload = decode_token(body.refresh_token)
            if refresh_payload.get("type") == "refresh":
                r_jti = refresh_payload.get("jti")
                r_exp = refresh_payload.get("exp", 0)
                if r_jti:
                    ttl = max(int(r_exp - time.time()), 1)
                    await add_token_to_blacklist(r_jti, ttl)
        except JWTError:
            pass

    logger.info("User logged out", user_id=_user.id, email=_user.email)

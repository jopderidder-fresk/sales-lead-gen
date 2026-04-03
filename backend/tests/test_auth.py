"""Tests for JWT authentication endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.main import app
from app.models.enums import UserRole
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_user(
    user_id: int = 1,
    username: str = "testuser",
    email: str = "test@example.com",
    role: UserRole = UserRole.USER,
    password: str = "securepassword",
):
    """Return a mock User object."""
    user = MagicMock()
    user.id = user_id
    user.username = username
    user.email = email
    user.role = role
    user.password_hash = hash_password(password)
    user.created_at = "2025-01-01T00:00:00"
    return user


def _admin_user():
    return _fake_user(user_id=2, username="admin", email="admin@test.com", role=UserRole.ADMIN)


def _auth_header(user_id: int = 1, role: str = "user") -> dict[str, str]:
    token = create_access_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------


class TestLogin:
    def test_login_success(self, client: TestClient) -> None:
        user = _fake_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user

        with (
            patch("app.api.v1.auth.get_session") as mock_get_session,
            patch("app.core.deps.is_token_blacklisted", return_value=False),
        ):
            mock_session = AsyncMock()
            mock_session.execute.return_value = mock_result
            mock_get_session.return_value = mock_session

            # Override the dependency
            from app.core.database import get_session

            app.dependency_overrides[get_session] = lambda: mock_session

            response = client.post(
                "/api/v1/auth/login",
                json={"username": "testuser", "password": "securepassword"},
            )

            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self, client: TestClient) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        from app.core.database import get_session

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        app.dependency_overrides[get_session] = lambda: mock_session

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent", "password": "wrongpassword"},
        )

        app.dependency_overrides.clear()
        assert response.status_code == 401

    def test_login_missing_fields(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    def test_refresh_success(self, client: TestClient) -> None:
        user = _fake_user()
        refresh_token = create_refresh_token(user.id, user.role)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user

        from app.core.database import get_session

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        app.dependency_overrides[get_session] = lambda: mock_session

        with (
            patch("app.api.v1.auth.is_token_blacklisted", return_value=False),
            patch("app.api.v1.auth.add_token_to_blacklist") as mock_blacklist,
        ):
            response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
            )
            # Old refresh token should be blacklisted (rotation)
            mock_blacklist.assert_called_once()

        app.dependency_overrides.clear()
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_with_access_token_fails(self, client: TestClient) -> None:
        """Using an access token as a refresh token should fail."""
        access_token = create_access_token(1, "user")

        from app.core.database import get_session

        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = lambda: mock_session

        with patch("app.api.v1.auth.is_token_blacklisted", return_value=False):
            response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": access_token},
            )

        app.dependency_overrides.clear()
        assert response.status_code == 401

    def test_refresh_with_revoked_token_fails(self, client: TestClient) -> None:
        """A blacklisted refresh token should be rejected."""
        refresh_token = create_refresh_token(1, "user")

        from app.core.database import get_session

        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = lambda: mock_session

        with patch("app.api.v1.auth.is_token_blacklisted", return_value=True):
            response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
            )

        app.dependency_overrides.clear()
        assert response.status_code == 401

    def test_refresh_with_invalid_token(self, client: TestClient) -> None:
        from app.core.database import get_session

        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = lambda: mock_session

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )

        app.dependency_overrides.clear()
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------


class TestRegister:
    def test_register_as_admin(self, client: TestClient) -> None:
        admin = _admin_user()

        # First call: get_current_user looks up admin; second call: check existing user
        mock_result_admin = MagicMock()
        mock_result_admin.scalar_one_or_none.return_value = admin

        mock_result_no_existing = MagicMock()
        mock_result_no_existing.scalar_one_or_none.return_value = None

        from app.core.database import get_session

        mock_session = AsyncMock()
        mock_session.execute.side_effect = [mock_result_admin, mock_result_no_existing]
        # add() is synchronous on real SQLAlchemy sessions
        mock_session.add = MagicMock()

        def _simulate_refresh(u):
            u.id = 3
            u.created_at = datetime.now(timezone.utc)

        mock_session.refresh = AsyncMock(side_effect=_simulate_refresh)

        app.dependency_overrides[get_session] = lambda: mock_session

        with patch("app.core.deps.is_token_blacklisted", return_value=False):
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "username": "newuser",
                    "email": "new@test.com",
                    "password": "securepass123",
                    "role": "user",
                },
                headers=_auth_header(admin.id, admin.role),
            )

        app.dependency_overrides.clear()
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "new@test.com"

    def test_register_as_non_admin_forbidden(self, client: TestClient) -> None:
        user = _fake_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user

        from app.core.database import get_session

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        app.dependency_overrides[get_session] = lambda: mock_session

        with patch("app.core.deps.is_token_blacklisted", return_value=False):
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "username": "newuser",
                    "email": "new@test.com",
                    "password": "securepass123",
                    "role": "user",
                },
                headers=_auth_header(user.id, user.role),
            )

        app.dependency_overrides.clear()
        assert response.status_code == 403

    def test_register_duplicate_user(self, client: TestClient) -> None:
        admin = _admin_user()
        existing_user = _fake_user()

        mock_result_admin = MagicMock()
        mock_result_admin.scalar_one_or_none.return_value = admin

        mock_result_existing = MagicMock()
        mock_result_existing.scalar_one_or_none.return_value = existing_user

        from app.core.database import get_session

        mock_session = AsyncMock()
        mock_session.execute.side_effect = [mock_result_admin, mock_result_existing]
        app.dependency_overrides[get_session] = lambda: mock_session

        with patch("app.core.deps.is_token_blacklisted", return_value=False):
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "username": "testuser",
                    "email": "test@example.com",
                    "password": "securepass123",
                    "role": "user",
                },
                headers=_auth_header(admin.id, admin.role),
            )

        app.dependency_overrides.clear()
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout
# ---------------------------------------------------------------------------


class TestLogout:
    def test_logout_blacklists_access_token(self, client: TestClient) -> None:
        user = _fake_user()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user

        from app.core.database import get_session

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        app.dependency_overrides[get_session] = lambda: mock_session

        with (
            patch("app.core.deps.is_token_blacklisted", return_value=False),
            patch("app.api.v1.auth.add_token_to_blacklist") as mock_blacklist,
        ):
            response = client.post(
                "/api/v1/auth/logout",
                headers=_auth_header(user.id, user.role),
            )
            # Access token JTI should be blacklisted
            mock_blacklist.assert_called_once()

        app.dependency_overrides.clear()
        assert response.status_code == 204

    def test_logout_blacklists_both_tokens(self, client: TestClient) -> None:
        """When refresh_token is provided in body, both tokens are blacklisted."""
        user = _fake_user()
        refresh_token = create_refresh_token(user.id, user.role)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user

        from app.core.database import get_session

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        app.dependency_overrides[get_session] = lambda: mock_session

        with (
            patch("app.core.deps.is_token_blacklisted", return_value=False),
            patch("app.api.v1.auth.add_token_to_blacklist") as mock_blacklist,
        ):
            response = client.post(
                "/api/v1/auth/logout",
                json={"refresh_token": refresh_token},
                headers=_auth_header(user.id, user.role),
            )
            # Both access + refresh token JTIs should be blacklisted
            assert mock_blacklist.call_count == 2

        app.dependency_overrides.clear()
        assert response.status_code == 204

    def test_logout_without_token(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/logout")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Token validation / dependencies
# ---------------------------------------------------------------------------


class TestTokenValidation:
    def test_access_protected_route_without_token(self, client: TestClient) -> None:
        """Endpoints protected by get_current_user should return 401 or 403 without a token."""
        response = client.post("/api/v1/auth/logout")
        assert response.status_code in (401, 403)

    def test_access_with_invalid_token(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer invalidtoken"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Security module unit tests
# ---------------------------------------------------------------------------


class TestSecurityUtils:
    def test_password_hashing(self) -> None:
        from app.core.security import hash_password, verify_password

        hashed = hash_password("mypassword")
        assert hashed != "mypassword"
        assert verify_password("mypassword", hashed)
        assert not verify_password("wrongpassword", hashed)

    def test_access_token_roundtrip(self) -> None:
        from app.core.security import create_access_token, decode_token

        token = create_access_token(42, "admin")
        payload = decode_token(token)
        assert payload["sub"] == "42"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"
        assert "jti" in payload
        assert "exp" in payload

    def test_refresh_token_roundtrip(self) -> None:
        from app.core.security import create_refresh_token, decode_token

        token = create_refresh_token(42, "user")
        payload = decode_token(token)
        assert payload["sub"] == "42"
        assert payload["role"] == "user"
        assert payload["type"] == "refresh"

    def test_decode_invalid_token(self) -> None:
        from app.core.security import JWTError, decode_token

        with pytest.raises(JWTError):
            decode_token("not.a.valid.token")

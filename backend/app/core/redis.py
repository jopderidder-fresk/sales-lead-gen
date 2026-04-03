from redis.asyncio import Redis

from app.core.config import settings

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


async def add_token_to_blacklist(jti: str, ttl_seconds: int) -> None:
    """Add a token's JTI to the blacklist with a TTL matching its remaining life."""
    await redis_client.setex(f"token_blacklist:{jti}", ttl_seconds, "1")


async def is_token_blacklisted(jti: str) -> bool:
    """Check whether a token's JTI has been blacklisted."""
    return await redis_client.exists(f"token_blacklist:{jti}") > 0

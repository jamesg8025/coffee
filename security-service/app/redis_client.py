"""
Async Redis client — single shared instance for the security-service.

Created at application startup and injected as a FastAPI dependency.
Also imported directly by the rate limiter.
"""

from redis.asyncio import Redis

from app.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    """Return the module-level Redis client (set at startup)."""
    if _redis is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() first.")
    return _redis


async def init_redis() -> Redis:
    """Create and store the Redis connection. Called in app lifespan."""
    global _redis
    settings = get_settings()
    _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    await _redis.ping()
    return _redis


async def close_redis() -> None:
    """Close the Redis connection. Called in app lifespan teardown."""
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None

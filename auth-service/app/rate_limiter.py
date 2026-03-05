"""
Redis sliding window rate limiter — auth-service copy.

Identical logic to security-service/app/rate_limiter.py.
Both services connect to the same Redis instance so security-service
can monitor the counters and blocks set here.

See security-service/app/rate_limiter.py for full algorithm comments.
"""

import time

from redis.asyncio import Redis

_FAILURES_KEY = "ratelimit:failures:{ip}"
_BLOCKED_KEY = "ratelimit:blocked:{ip}"
_BLOCK_COUNT_KEY = "ratelimit:block_count:{ip}"


async def is_blocked(redis: Redis, ip: str) -> int:
    """Return remaining block TTL in seconds, or 0 if not blocked."""
    ttl = await redis.ttl(_BLOCKED_KEY.format(ip=ip))
    return max(ttl, 0)


async def record_failure(
    redis: Redis,
    ip: str,
    window_seconds: int,
    max_failures: int,
    block_seconds: int,
) -> int:
    """Record one login failure. Returns block TTL if triggered, else 0."""
    key = _FAILURES_KEY.format(ip=ip)
    now = time.time()
    window_start = now - window_seconds

    async with redis.pipeline(transaction=True) as pipe:
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()

    count = results[2]
    if count >= max_failures:
        count_key = _BLOCK_COUNT_KEY.format(ip=ip)
        block_num = await redis.incr(count_key)
        await redis.expire(count_key, 86400)
        effective_seconds = min(block_seconds * (2 ** (block_num - 1)), 86400)
        await redis.setex(
            _BLOCKED_KEY.format(ip=ip), effective_seconds, str(effective_seconds)
        )
        return effective_seconds

    return 0

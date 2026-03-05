"""
Redis sliding window rate limiter for brute-force login protection.

Algorithm:
  - Per-IP, maintain a sorted set of FAILURE timestamps in Redis.
  - Score = member = Unix timestamp (float as string).
  - On each failure: trim old entries outside the window, add current, count.
  - If count ≥ threshold → set a block key with TTL.
  - Progressive backoff: each successive block doubles the TTL (capped at 24 h).

Redis keys:
  ratelimit:failures:{ip}    — sorted set of failure timestamps
  ratelimit:blocked:{ip}     — string key with TTL; value = block duration (seconds)
  ratelimit:block_count:{ip} — integer; how many times this IP has been blocked

Interview talking point:
  "I used a sorted set rather than a simple counter so I could implement a true
  sliding window — old failures naturally age out. A plain counter would reset
  abruptly at the window boundary, allowing an attacker to burst at the boundary."
"""

import time

from redis.asyncio import Redis

_FAILURES_KEY = "ratelimit:failures:{ip}"
_BLOCKED_KEY = "ratelimit:blocked:{ip}"
_BLOCK_COUNT_KEY = "ratelimit:block_count:{ip}"


async def is_blocked(redis: Redis, ip: str) -> int:
    """
    Return the remaining block TTL in seconds, or 0 if not blocked.
    Used by middleware to short-circuit requests before any work is done.
    """
    ttl = await redis.ttl(_BLOCKED_KEY.format(ip=ip))
    return max(ttl, 0)


async def record_failure(
    redis: Redis,
    ip: str,
    window_seconds: int,
    max_failures: int,
    block_seconds: int,
) -> int:
    """
    Record one login failure for the given IP.
    Returns the block TTL (seconds) if this failure triggered a block, else 0.

    Uses a Redis pipeline (atomic) to avoid race conditions.
    """
    key = _FAILURES_KEY.format(ip=ip)
    now = time.time()
    window_start = now - window_seconds

    async with redis.pipeline(transaction=True) as pipe:
        pipe.zremrangebyscore(key, 0, window_start)   # drop stale entries
        pipe.zadd(key, {str(now): now})               # record this failure
        pipe.zcard(key)                               # count in window
        pipe.expire(key, window_seconds)              # auto-clean the key
        results = await pipe.execute()

    count = results[2]
    if count >= max_failures:
        count_key = _BLOCK_COUNT_KEY.format(ip=ip)
        block_num = await redis.incr(count_key)
        await redis.expire(count_key, 86400)  # reset block-count after 1 day

        # Progressive backoff: 1×, 2×, 4×, 8× … capped at 24 h
        effective_seconds = min(block_seconds * (2 ** (block_num - 1)), 86400)
        await redis.setex(
            _BLOCKED_KEY.format(ip=ip), effective_seconds, str(effective_seconds)
        )
        return effective_seconds

    return 0


async def clear_block(redis: Redis, ip: str) -> bool:
    """
    Manually unblock an IP (admin action).
    Deletes the block key and resets the failure history.
    Returns True if the IP was actually blocked.
    """
    deleted = await redis.delete(_BLOCKED_KEY.format(ip=ip))
    await redis.delete(_FAILURES_KEY.format(ip=ip))
    await redis.delete(_BLOCK_COUNT_KEY.format(ip=ip))
    return deleted > 0


async def list_blocked(redis: Redis) -> list[dict]:
    """
    Scan Redis for all currently blocked IPs and their remaining TTLs.
    Used by the admin endpoint to surface active blocks.
    """
    blocked = []
    async for key in redis.scan_iter("ratelimit:blocked:*"):
        ttl = await redis.ttl(key)
        if ttl > 0:
            ip = key.replace("ratelimit:blocked:", "")
            blocked.append({"ip": ip, "ttl_seconds": ttl})
    return blocked

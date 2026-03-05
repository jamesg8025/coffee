"""
Login rate limiting middleware for auth-service.

Intercepts POST /auth/login requests:
  1. Pre-request:  check if the client IP is blocked → return 429 immediately.
  2. Post-response: if the login returned 401, record the failure in Redis.
                    If failures hit the threshold, set a block key with TTL.

The Retry-After header tells well-behaved clients how long to wait.
The security-service can read the same Redis keys to surface blocked IPs
to admins via its /blocked-ips endpoint.

Interview talking point:
  "I put rate limiting in middleware rather than the route handler because
  middleware runs before any business logic, so a blocked IP never touches
  the database or bcrypt at all. That keeps the hot path fast and reduces
  load amplification from attackers."
"""

import logging

from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.rate_limiter import is_blocked, record_failure

logger = logging.getLogger(__name__)

_LOGIN_PATH = "/auth/login"


class LoginRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that enforces a sliding window rate limit on logins.

    Accepts a `get_redis` callable rather than a direct Redis instance so that
    the middleware can be registered at app-creation time (before lifespan runs
    and the Redis connection is opened).  The callable is invoked at each
    dispatch, guaranteeing we always use the live connection.
    """

    def __init__(self, app, get_redis, settings):
        super().__init__(app)
        self._get_redis = get_redis
        self._settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only apply to login endpoint
        if not (request.method == "POST" and request.url.path == _LOGIN_PATH):
            return await call_next(request)

        redis = self._get_redis()
        if redis is None:
            # Redis not yet initialised (e.g., early health-check during startup)
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        s = self._settings

        # --- Pre-request: reject blocked IPs before any work ---
        ttl = await is_blocked(redis, ip)
        if ttl:
            logger.info("Blocked IP %s attempted login (TTL=%ss)", ip, ttl)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Too many failed login attempts. Try again in {ttl} seconds."
                },
                headers={"Retry-After": str(ttl)},
            )

        response = await call_next(request)

        # --- Post-response: record failures ---
        if response.status_code == 401:
            block_ttl = await record_failure(
                redis,
                ip,
                window_seconds=s.rate_limit_window_seconds,
                max_failures=s.rate_limit_max_failures,
                block_seconds=s.rate_limit_block_seconds,
            )
            if block_ttl:
                logger.warning(
                    "IP %s blocked for %ss after %s failed logins",
                    ip,
                    block_ttl,
                    s.rate_limit_max_failures,
                )

        return response

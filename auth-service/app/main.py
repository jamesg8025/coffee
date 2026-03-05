from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.config import get_settings
from app.middleware import LoginRateLimitMiddleware
from app.routers import auth, mfa, users
from app.secrets import load_secrets

settings = get_settings()

_redis: Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis
    load_secrets()
    _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    await _redis.ping()
    yield
    if _redis:
        await _redis.aclose()


app = FastAPI(
    title="Coffee Connoisseur — Auth Service",
    version="2.0.0",
    description=(
        "Authentication and authorization: registration, login, "
        "JWT issuance, refresh token rotation, TOTP MFA, RBAC."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware — runs before every request.
# Blocks IPs that have exceeded the login failure threshold.
# The _redis client is initialised in lifespan above.
# We pass a lambda so the middleware always gets the live client object.
app.add_middleware(
    LoginRateLimitMiddleware,
    get_redis=lambda: _redis,
    settings=settings,
)


@app.get("/health", tags=["ops"])
async def health():
    return {"status": "healthy", "service": "auth-service"}


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(mfa.router, prefix="/auth/mfa", tags=["mfa"])
app.include_router(users.router, prefix="/users", tags=["users"])

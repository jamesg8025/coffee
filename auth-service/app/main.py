from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.secrets import load_secrets

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load secrets once at startup (cached via lru_cache)
    load_secrets()
    yield


app = FastAPI(
    title="Coffee Connoisseur — Auth Service",
    version="1.0.0",
    description="Authentication and authorization: registration, login, JWT issuance, refresh token rotation, TOTP MFA.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["ops"])
async def health():
    return {"status": "healthy", "service": "auth-service"}


# Auth routes will be mounted here in Phase 2:
# from app.routers import auth, users
# app.include_router(auth.router, prefix="/auth", tags=["auth"])
# app.include_router(users.router, prefix="/users", tags=["users"])

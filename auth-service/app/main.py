from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, mfa, users
from app.secrets import load_secrets

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_secrets()
    yield


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


@app.get("/health", tags=["ops"])
async def health():
    return {"status": "healthy", "service": "auth-service"}


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(mfa.router, prefix="/auth/mfa", tags=["mfa"])
app.include_router(users.router, prefix="/users", tags=["users"])

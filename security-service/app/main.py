from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Coffee Connoisseur — Security Service",
    version="1.0.0",
    description="Rate limiting, automated vulnerability scanning, anomaly detection, and secrets monitoring.",
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
    return {"status": "healthy", "service": "security-service"}


# Routers mounted in Phase 4:
# from app.routers import rate_limit, scans
# app.include_router(rate_limit.router, prefix="/rate-limit", tags=["rate-limit"])
# app.include_router(scans.router, prefix="/security", tags=["security"])

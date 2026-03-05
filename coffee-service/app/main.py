from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import coffees, collections, tasting_notes, recommendations

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Coffee Connoisseur — Coffee Service",
    version="1.0.0",
    description="Coffee catalog, personal collections, tasting notes, and AI-powered recommendations.",
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
    return {"status": "healthy", "service": "coffee-service"}


app.include_router(coffees.router, prefix="/coffees", tags=["coffees"])
app.include_router(collections.router, prefix="/collections", tags=["collections"])
app.include_router(tasting_notes.router, prefix="/tasting-notes", tags=["tasting-notes"])
app.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])

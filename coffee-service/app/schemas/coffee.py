"""
Pydantic schemas for the coffee-service.

One file keeps cross-schema references (e.g. CollectionResponse including
CoffeeResponse) simple — no circular import problems.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.coffee import CollectionStatus, RoastLevel


# ---------------------------------------------------------------------------
# Coffee catalog
# ---------------------------------------------------------------------------

class CoffeeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    origin_country: str | None = None
    roast_level: RoastLevel | None = None
    flavor_profile: dict | None = None
    description: str | None = None


class CoffeeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    origin_country: str | None = None
    roast_level: RoastLevel | None = None
    flavor_profile: dict | None = None
    description: str | None = None
    is_active: bool | None = None


class CoffeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    roaster_id: uuid.UUID | None
    origin_country: str | None
    roast_level: str | None
    flavor_profile: dict | None
    description: str | None
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Personal collections
# ---------------------------------------------------------------------------

class CollectionCreate(BaseModel):
    coffee_id: uuid.UUID
    quantity: float | None = None
    purchase_date: date | None = None
    status: CollectionStatus = CollectionStatus.ACTIVE


class CollectionUpdate(BaseModel):
    quantity: float | None = None
    purchase_date: date | None = None
    status: CollectionStatus | None = None


class CollectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    coffee_id: uuid.UUID
    quantity: float | None
    purchase_date: date | None
    status: str
    created_at: datetime
    coffee: CoffeeResponse | None = None


# ---------------------------------------------------------------------------
# Tasting notes
# ---------------------------------------------------------------------------

class BrewParams(BaseModel):
    """Structured brew parameters — every field is optional."""
    method: str | None = None          # pour_over, espresso, french_press, aeropress …
    grind_size: str | None = None      # fine, medium-fine, medium, coarse
    water_temp_celsius: float | None = None
    brew_time_seconds: int | None = None
    dose_grams: float | None = None
    yield_grams: float | None = None


class FlavorRatings(BaseModel):
    """Numeric ratings 1–10 for each flavor dimension."""
    acidity: int | None = Field(None, ge=1, le=10)
    sweetness: int | None = Field(None, ge=1, le=10)
    body: int | None = Field(None, ge=1, le=10)
    bitterness: int | None = Field(None, ge=1, le=10)
    overall: int | None = Field(None, ge=1, le=10)


class TastingNoteCreate(BaseModel):
    coffee_id: uuid.UUID
    brew_params: BrewParams | None = None
    ratings: FlavorRatings | None = None
    notes: str | None = None
    is_public: bool = False


class TastingNoteUpdate(BaseModel):
    brew_params: BrewParams | None = None
    ratings: FlavorRatings | None = None
    notes: str | None = None
    is_public: bool | None = None


class TastingNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    coffee_id: uuid.UUID
    brew_params: dict | None
    ratings: dict | None
    notes: str | None
    is_public: bool
    created_at: datetime
    coffee: CoffeeResponse | None = None


# ---------------------------------------------------------------------------
# AI recommendations
# ---------------------------------------------------------------------------

class RecommendationRequest(BaseModel):
    """
    Optional explicit preferences.  All fields are lists of strings — NOT
    free-form text — to prevent prompt injection.  User input never goes
    directly into the system prompt; it goes into structured JSON in the
    user message.
    """
    preferred_roast_levels: list[str] | None = None
    preferred_origins: list[str] | None = None
    flavor_preferences: list[str] | None = None


class RecommendedCoffee(BaseModel):
    coffee_id: uuid.UUID
    name: str
    reason: str


class RecommendationResponse(BaseModel):
    recommendations: list[RecommendedCoffee]
    based_on_notes_count: int

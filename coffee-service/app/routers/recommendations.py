"""
AI-powered coffee recommendations using OpenAI.

Security note: user-supplied preference strings are injected into structured
JSON inside the *user* message — never interpolated into the system prompt.
This prevents prompt injection: even if a user writes "ignore previous
instructions", it arrives as a JSON value, not as executable instructions.

Interview talking point: "Structured-data injection keeps user content out of
the system prompt entirely.  The LLM sees it as data, not commands."
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from openai import AsyncOpenAI, OpenAIError
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.config import get_settings
from app.database import get_db
from app.dependencies import CurrentUser, get_current_user
from app.schemas.coffee import RecommendationRequest, RecommendationResponse, RecommendedCoffee

router = APIRouter()

_SYSTEM_PROMPT = """\
You are a coffee sommelier assistant.  You will be given:
1. A JSON object describing the user's tasting history (recent notes).
2. A JSON array of available coffees in the catalog.
3. Optional explicit preferences from the user.

Your task: recommend up to 3 coffees from the catalog that best match the
user's tastes and preferences.  Reply ONLY with valid JSON — no prose, no
markdown — in this exact shape:

{
  "recommendations": [
    {"coffee_id": "<uuid>", "name": "<name>", "reason": "<one sentence>"},
    ...
  ]
}

Rules:
- Only recommend coffees that appear in the provided catalog array.
- Base your reasoning on flavour profile, roast level, and origin patterns
  visible in the tasting history.
- If the tasting history is empty, use the explicit preferences only.
- If there is nothing to go on, return your top 3 picks from the catalog with
  a generic reason.
"""


@router.post("", response_model=RecommendationResponse)
async def get_recommendations(
    request: RecommendationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI recommendations are not configured on this server.",
        )

    # Pull the user's last 20 tasting notes for context
    notes = await crud.tasting_notes.get_user_tasting_notes(db, current_user.id, limit=20)
    # Pull up to 50 active coffees for the model to choose from
    coffees = await crud.coffees.list_coffees(db, limit=50)

    notes_payload = [
        {
            "coffee_name": n.coffee.name if n.coffee else str(n.coffee_id),
            "brew_params": n.brew_params,
            "ratings": n.ratings,
            "notes": n.notes,
        }
        for n in notes
    ]

    catalog_payload = [
        {
            "coffee_id": str(c.id),
            "name": c.name,
            "origin_country": c.origin_country,
            "roast_level": c.roast_level,
            "flavor_profile": c.flavor_profile,
            "description": c.description,
        }
        for c in coffees
    ]

    # User-supplied preferences go into the *user* message as structured JSON,
    # never into the system prompt.
    user_message = json.dumps(
        {
            "tasting_history": notes_payload,
            "catalog": catalog_payload,
            "preferences": {
                "preferred_roast_levels": request.preferred_roast_levels,
                "preferred_origins": request.preferred_origins,
                "flavor_preferences": request.flavor_preferences,
            },
        },
        default=str,
    )

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=512,
            temperature=0.4,
        )
    except OpenAIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service error: {exc}",
        )

    try:
        raw = json.loads(response.choices[0].message.content)
        recs = [RecommendedCoffee(**item) for item in raw.get("recommendations", [])]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned an unexpected response format.",
        )

    return RecommendationResponse(
        recommendations=recs,
        based_on_notes_count=len(notes),
    )

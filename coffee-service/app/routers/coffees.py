"""
Coffee catalog endpoints.

Access rules:
  GET /coffees         — public (no token required)
  GET /coffees/{id}    — public
  POST /coffees        — ROASTER or ADMIN
  PATCH /coffees/{id}  — ROASTER who owns it, or ADMIN
  DELETE /coffees/{id} — ROASTER who owns it, or ADMIN
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.database import get_db
from app.dependencies import CurrentUser, get_current_user, require_role
from app.models.coffee import RoastLevel
from app.schemas.coffee import CoffeeCreate, CoffeeResponse, CoffeeUpdate

router = APIRouter()


@router.get("", response_model=list[CoffeeResponse])
async def list_coffees(
    search: str | None = Query(None, description="Case-insensitive name search"),
    roast_level: RoastLevel | None = Query(None),
    origin: str | None = Query(None, description="Filter by origin country"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await crud.coffees.list_coffees(
        db,
        search=search,
        roast_level=roast_level,
        origin=origin,
        skip=skip,
        limit=limit,
    )


@router.get("/{coffee_id}", response_model=CoffeeResponse)
async def get_coffee(
    coffee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    coffee = await crud.coffees.get_coffee(db, coffee_id)
    if not coffee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coffee not found")
    return coffee


@router.post("", response_model=CoffeeResponse, status_code=status.HTTP_201_CREATED)
async def create_coffee(
    data: CoffeeCreate,
    current_user: CurrentUser = Depends(require_role("ROASTER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    return await crud.coffees.create_coffee(db, data, roaster_id=current_user.id)


@router.patch("/{coffee_id}", response_model=CoffeeResponse)
async def update_coffee(
    coffee_id: uuid.UUID,
    data: CoffeeUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    coffee = await crud.coffees.get_coffee(db, coffee_id)
    if not coffee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coffee not found")

    is_owner = coffee.roaster_id == current_user.id
    is_admin = current_user.role == "ADMIN"
    if not (is_owner or is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    return await crud.coffees.update_coffee(db, coffee, data)


@router.delete("/{coffee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coffee(
    coffee_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    coffee = await crud.coffees.get_coffee(db, coffee_id)
    if not coffee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coffee not found")

    is_owner = coffee.roaster_id == current_user.id
    is_admin = current_user.role == "ADMIN"
    if not (is_owner or is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    await crud.coffees.delete_coffee(db, coffee)

"""
Personal coffee collections.  All endpoints require authentication.
A user can only read/modify their own collection entries.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.database import get_db
from app.dependencies import CurrentUser, get_current_user
from app.models.coffee import CollectionStatus
from app.schemas.coffee import CollectionCreate, CollectionResponse, CollectionUpdate

router = APIRouter()


@router.get("", response_model=list[CollectionResponse])
async def list_collections(
    status: CollectionStatus | None = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await crud.collections.get_user_collections(db, current_user.id, status=status)


@router.post("", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    data: CollectionCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    coffee = await crud.coffees.get_coffee(db, data.coffee_id)
    if not coffee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coffee not found")
    return await crud.collections.create_collection(db, data, current_user.id)


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    col = await crud.collections.get_collection(db, collection_id, current_user.id)
    if not col:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return col


@router.patch("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: uuid.UUID,
    data: CollectionUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    col = await crud.collections.get_collection(db, collection_id, current_user.id)
    if not col:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return await crud.collections.update_collection(db, col, data)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    col = await crud.collections.get_collection(db, collection_id, current_user.id)
    if not col:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    await crud.collections.delete_collection(db, col)

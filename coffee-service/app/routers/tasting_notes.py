"""
Tasting notes endpoints.

Access rules:
  GET  /tasting-notes                     — auth required (own notes)
  POST /tasting-notes                     — auth required
  GET  /tasting-notes/{id}               — owner OR note is public
  PATCH/DELETE /tasting-notes/{id}       — owner only
  GET  /tasting-notes/coffee/{coffee_id} — public (no token required)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.database import get_db
from app.dependencies import CurrentUser, get_current_user
from app.schemas.coffee import TastingNoteCreate, TastingNoteResponse, TastingNoteUpdate

router = APIRouter()


@router.get("", response_model=list[TastingNoteResponse])
async def list_my_tasting_notes(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await crud.tasting_notes.get_user_tasting_notes(db, current_user.id)


@router.post("", response_model=TastingNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_tasting_note(
    data: TastingNoteCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    coffee = await crud.coffees.get_coffee(db, data.coffee_id)
    if not coffee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coffee not found")
    return await crud.tasting_notes.create_tasting_note(db, data, current_user.id)


# NOTE: this route must be defined BEFORE /{note_id} so FastAPI doesn't
# try to parse "coffee" as a UUID.
@router.get("/coffee/{coffee_id}", response_model=list[TastingNoteResponse])
async def get_public_notes_for_coffee(
    coffee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await crud.tasting_notes.get_public_notes_for_coffee(db, coffee_id)


@router.get("/{note_id}", response_model=TastingNoteResponse)
async def get_tasting_note(
    note_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    note = await crud.tasting_notes.get_tasting_note(db, note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tasting note not found")
    return note


@router.patch("/{note_id}", response_model=TastingNoteResponse)
async def update_tasting_note(
    note_id: uuid.UUID,
    data: TastingNoteUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    note = await crud.tasting_notes.get_tasting_note(db, note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tasting note not found")
    if note.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return await crud.tasting_notes.update_tasting_note(db, note, data)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tasting_note(
    note_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    note = await crud.tasting_notes.get_tasting_note(db, note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tasting note not found")
    if note.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    await crud.tasting_notes.delete_tasting_note(db, note)

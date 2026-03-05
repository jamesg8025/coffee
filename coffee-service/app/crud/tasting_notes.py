import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coffee import TastingNote
from app.schemas.coffee import TastingNoteCreate, TastingNoteUpdate


async def get_user_tasting_notes(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 50,
) -> list[TastingNote]:
    result = await db.execute(
        select(TastingNote)
        .options(selectinload(TastingNote.coffee))
        .where(TastingNote.user_id == user_id)
        .order_by(TastingNote.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def get_public_notes_for_coffee(
    db: AsyncSession, coffee_id: uuid.UUID
) -> list[TastingNote]:
    result = await db.execute(
        select(TastingNote)
        .options(selectinload(TastingNote.coffee))
        .where(TastingNote.coffee_id == coffee_id, TastingNote.is_public == True)  # noqa: E712
        .order_by(TastingNote.created_at.desc())
    )
    return list(result.scalars())


async def get_tasting_note(
    db: AsyncSession, note_id: uuid.UUID, user_id: uuid.UUID
) -> TastingNote | None:
    """Returns the note if it's owned by user_id or is public."""
    result = await db.execute(
        select(TastingNote)
        .options(selectinload(TastingNote.coffee))
        .where(TastingNote.id == note_id)
    )
    note = result.scalar_one_or_none()
    if note is None:
        return None
    if note.user_id != user_id and not note.is_public:
        return None
    return note


async def create_tasting_note(
    db: AsyncSession, data: TastingNoteCreate, user_id: uuid.UUID
) -> TastingNote:
    brew = data.brew_params.model_dump() if data.brew_params else None
    ratings = data.ratings.model_dump() if data.ratings else None
    note = TastingNote(
        coffee_id=data.coffee_id,
        user_id=user_id,
        brew_params=brew,
        ratings=ratings,
        notes=data.notes,
        is_public=data.is_public,
    )
    db.add(note)
    await db.flush()
    await db.refresh(note, ["coffee"])
    return note


async def update_tasting_note(
    db: AsyncSession, note: TastingNote, data: TastingNoteUpdate
) -> TastingNote:
    updates = data.model_dump(exclude_unset=True)
    if "brew_params" in updates and updates["brew_params"] is not None:
        updates["brew_params"] = data.brew_params.model_dump()
    if "ratings" in updates and updates["ratings"] is not None:
        updates["ratings"] = data.ratings.model_dump()
    for field, value in updates.items():
        setattr(note, field, value)
    await db.flush()
    return note


async def delete_tasting_note(db: AsyncSession, note: TastingNote) -> None:
    await db.delete(note)
    await db.flush()

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coffee import Collection, CollectionStatus
from app.schemas.coffee import CollectionCreate, CollectionUpdate


async def get_user_collections(
    db: AsyncSession,
    user_id: uuid.UUID,
    status: CollectionStatus | None = None,
) -> list[Collection]:
    q = (
        select(Collection)
        .options(selectinload(Collection.coffee))
        .where(Collection.user_id == user_id)
    )
    if status:
        q = q.where(Collection.status == status)
    q = q.order_by(Collection.created_at.desc())
    result = await db.execute(q)
    return list(result.scalars())


async def get_collection(
    db: AsyncSession, collection_id: uuid.UUID, user_id: uuid.UUID
) -> Collection | None:
    """Returns the collection only if it belongs to user_id."""
    result = await db.execute(
        select(Collection)
        .options(selectinload(Collection.coffee))
        .where(Collection.id == collection_id, Collection.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_collection(
    db: AsyncSession, data: CollectionCreate, user_id: uuid.UUID
) -> Collection:
    col = Collection(**data.model_dump(), user_id=user_id)
    db.add(col)
    await db.flush()
    await db.refresh(col, ["coffee"])
    return col


async def update_collection(
    db: AsyncSession, collection: Collection, data: CollectionUpdate
) -> Collection:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(collection, field, value)
    await db.flush()
    return collection


async def delete_collection(db: AsyncSession, collection: Collection) -> None:
    await db.delete(collection)
    await db.flush()

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coffee import Coffee, RoastLevel
from app.schemas.coffee import CoffeeCreate, CoffeeUpdate


async def list_coffees(
    db: AsyncSession,
    search: str | None = None,
    roast_level: RoastLevel | None = None,
    origin: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> list[Coffee]:
    q = select(Coffee).where(Coffee.is_active == True)  # noqa: E712
    if search:
        q = q.where(Coffee.name.ilike(f"%{search}%"))
    if roast_level:
        q = q.where(Coffee.roast_level == roast_level)
    if origin:
        q = q.where(Coffee.origin_country.ilike(f"%{origin}%"))
    q = q.order_by(Coffee.name).offset(skip).limit(limit)
    result = await db.execute(q)
    return list(result.scalars())


async def get_coffee(db: AsyncSession, coffee_id: uuid.UUID) -> Coffee | None:
    result = await db.execute(select(Coffee).where(Coffee.id == coffee_id))
    return result.scalar_one_or_none()


async def create_coffee(
    db: AsyncSession, data: CoffeeCreate, roaster_id: uuid.UUID
) -> Coffee:
    coffee = Coffee(**data.model_dump(), roaster_id=roaster_id)
    db.add(coffee)
    await db.flush()
    return coffee


async def update_coffee(
    db: AsyncSession, coffee: Coffee, data: CoffeeUpdate
) -> Coffee:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(coffee, field, value)
    await db.flush()
    return coffee


async def delete_coffee(db: AsyncSession, coffee: Coffee) -> None:
    await db.delete(coffee)
    await db.flush()

"""
Seed the coffee catalog with realistic sample data.

Usage (inside the coffee-service container):
    python seeds/seed.py

The script is idempotent — it skips coffees whose name already exists.
"""

import asyncio
import os
import sys

# Allow running from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.coffee import Coffee, RoastLevel

COFFEES = [
    {
        "name": "Ethiopia Yirgacheffe Natural",
        "origin_country": "Ethiopia",
        "roast_level": RoastLevel.LIGHT,
        "flavor_profile": {"notes": ["blueberry", "jasmine", "lemon"], "body": "light", "acidity": "bright"},
        "description": "A naturally processed Ethiopian with explosive fruit sweetness and floral aromatics.",
    },
    {
        "name": "Colombia Huila Washed",
        "origin_country": "Colombia",
        "roast_level": RoastLevel.MEDIUM,
        "flavor_profile": {"notes": ["caramel", "red apple", "hazelnut"], "body": "medium", "acidity": "balanced"},
        "description": "Classic Colombian cup — sweet caramel backbone with crisp fruit acidity.",
    },
    {
        "name": "Guatemala Antigua Dark",
        "origin_country": "Guatemala",
        "roast_level": RoastLevel.DARK,
        "flavor_profile": {"notes": ["dark chocolate", "smoky", "brown sugar"], "body": "full", "acidity": "low"},
        "description": "Rich, bold Guatemalan single origin roasted dark for espresso or French press.",
    },
    {
        "name": "Kenya AA Washed",
        "origin_country": "Kenya",
        "roast_level": RoastLevel.LIGHT,
        "flavor_profile": {"notes": ["blackcurrant", "grapefruit", "black tea"], "body": "medium", "acidity": "winey"},
        "description": "Classic Kenyan with that trademark winey acidity and intense berry character.",
    },
    {
        "name": "Brazil Cerrado Natural",
        "origin_country": "Brazil",
        "roast_level": RoastLevel.MEDIUM,
        "flavor_profile": {"notes": ["milk chocolate", "walnut", "dried cherry"], "body": "heavy", "acidity": "low"},
        "description": "Smooth, nutty Brazilian with low acidity — great as a base for espresso blends.",
    },
    {
        "name": "Costa Rica Tarrazu Honey",
        "origin_country": "Costa Rica",
        "roast_level": RoastLevel.MEDIUM,
        "flavor_profile": {"notes": ["peach", "honey", "almond"], "body": "medium", "acidity": "mild"},
        "description": "Honey-processed Costa Rican with stone-fruit sweetness and a silky finish.",
    },
    {
        "name": "Sumatra Mandheling",
        "origin_country": "Indonesia",
        "roast_level": RoastLevel.MEDIUM_DARK,
        "flavor_profile": {"notes": ["cedar", "dark cocoa", "earthy"], "body": "full", "acidity": "low"},
        "description": "Wet-hulled Indonesian — earthy, syrupy body with a distinctive herbal complexity.",
    },
    {
        "name": "Panama Gesha Natural",
        "origin_country": "Panama",
        "roast_level": RoastLevel.LIGHT,
        "flavor_profile": {"notes": ["bergamot", "peach tea", "rose"], "body": "delicate", "acidity": "bright"},
        "description": "The legendary Gesha variety — intensely floral and tea-like; a true collector's cup.",
    },
]


async def seed():
    async with AsyncSessionLocal() as db:
        seeded = 0
        skipped = 0
        for data in COFFEES:
            result = await db.execute(select(Coffee).where(Coffee.name == data["name"]))
            if result.scalar_one_or_none():
                skipped += 1
                continue
            coffee = Coffee(**data)
            db.add(coffee)
            seeded += 1
        await db.commit()
        print(f"Seed complete — {seeded} added, {skipped} already existed.")


if __name__ == "__main__":
    asyncio.run(seed())

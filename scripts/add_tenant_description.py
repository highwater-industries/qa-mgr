"""Add description column to tenants table."""
import asyncio
from sqlalchemy import text
from database.config import engine


async def add_description_column():
    """Add description column if it doesn't exist."""
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS description VARCHAR(1000);"
        ))
        print("✓ Added description column to tenants table")


if __name__ == "__main__":
    asyncio.run(add_description_column())

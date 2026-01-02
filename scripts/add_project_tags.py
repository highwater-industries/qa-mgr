"""Add tags column to projects table."""
import asyncio
from sqlalchemy import text
from database.config import engine


async def add_tags_column():
    """Add tags array column to projects table."""
    async with engine.begin() as conn:
        # Add tags column
        await conn.execute(
            text("""
                ALTER TABLE projects 
                ADD COLUMN IF NOT EXISTS tags TEXT[] 
                NOT NULL DEFAULT '{}';
            """)
        )
        print("✓ Added tags column to projects table")


if __name__ == "__main__":
    asyncio.run(add_tags_column())

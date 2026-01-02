"""Create initial superuser for testing."""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from database.config import AsyncSessionLocal
from database.models.user import User
from api.auth.password import get_password_hash

async def create_superuser():
    """Create a superuser for testing."""
    async with AsyncSessionLocal() as db:
        # Check if superuser already exists
        from sqlalchemy import select
        result = await db.execute(
            select(User).where(User.username == "admin")
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print("❌ Superuser 'admin' already exists")
            return
        
        # Create superuser
        user = User(
            email="admin@qa-mgr.local",
            username="admin",
            full_name="System Administrator",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
            is_superuser=True,
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        print("✅ Superuser created successfully!")
        print(f"   Username: admin")
        print(f"   Password: admin123")
        print(f"   Email: admin@qa-mgr.local")

if __name__ == "__main__":
    asyncio.run(create_superuser())

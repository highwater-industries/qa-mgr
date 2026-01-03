"""User repository for database operations."""
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.user import User
from api.repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    """Repository for user operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db, User)
    
    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.db.execute(
            select(User)
            .where(User.email == email)
            .where(User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()
    
    async def get_by_username(self, username: str) -> User | None:
        """Get user by username."""
        result = await self.db.execute(
            select(User)
            .where(User.username == username)
            .where(User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()
    
    async def list_users(
        self, skip: int = 0, limit: int = 100, active_only: bool = True
    ) -> list[User]:
        """List users with pagination."""
        query = select(User).where(User.deleted_at.is_(None))
        
        if active_only:
            query = query.where(User.is_active == True)
        
        query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())




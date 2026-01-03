"""Base repository with common CRUD operations."""
from typing import Generic, TypeVar, Type
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlmodel import SQLModel

ModelType = TypeVar("ModelType", bound=SQLModel)

class BaseRepository(Generic[ModelType]):
    """Base repository with common database operations."""
    
    def __init__(self, db: AsyncSession, model: Type[ModelType]):
        self.db = db
        self.model = model
    
    async def get_by_id(self, id: UUID) -> ModelType | None:
        """Get single record by ID."""
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """Get all records with pagination."""
        result = await self.db.execute(
            select(self.model)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def create(self, obj: ModelType) -> ModelType:
        """Create new record."""
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj
    
    async def update(self, obj: ModelType) -> ModelType:
        """Update existing record."""
        await self.db.commit()
        await self.db.refresh(obj)
        return obj
    
    async def delete(self, id: UUID) -> bool:
        """Soft delete record."""
        from datetime import datetime, timezone
        obj = await self.get_by_id(id)
        if obj and hasattr(obj, 'deleted_at'):
            obj.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await self.db.commit()
            return True
        return False
    
    async def count(self) -> int:
        """Count total records."""
        result = await self.db.execute(
            select(func.count(self.model.id))
        )
        return result.scalar_one()




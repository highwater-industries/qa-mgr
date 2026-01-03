"""User service for business logic."""
from uuid import UUID
from fastapi import HTTPException, status
import bcrypt

from database.models.user import User
from api.repositories.user import UserRepository
from api.schemas.user import UserCreateRequest, UserUpdateRequest


class UserService:
    """Business logic for user operations."""
    
    def __init__(self, repo: UserRepository):
        self.repo = repo
    
    async def create_user(
        self, user_data: UserCreateRequest, created_by_admin: bool = False
    ) -> User:
        """
        Create new user.
        
        - Admins can create users with superuser flag
        - Regular users cannot create superuser accounts
        """
        # Check email uniqueness
        existing_email = await self.repo.get_by_email(user_data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        
        # Check username uniqueness
        existing_username = await self.repo.get_by_username(user_data.username)
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )
        
        # Hash password
        hashed_password = bcrypt.hashpw(
            user_data.password.encode('utf-8'), 
            bcrypt.gensalt()
        ).decode('utf-8')
        
        # Create user
        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            is_superuser=user_data.is_superuser if created_by_admin else False,
            is_active=True,
        )
        
        return await self.repo.create(user)
    
    async def get_user(self, user_id: UUID) -> User:
        """Get user by ID."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user
    
    async def list_users(
        self, 
        skip: int = 0, 
        limit: int = 100,
        active_only: bool = True
    ) -> list[User]:
        """List all users."""
        return await self.repo.list_users(skip, limit, active_only)
    
    async def update_user(
        self, user_id: UUID, user_data: UserUpdateRequest
    ) -> User:
        """Update user profile."""
        user = await self.get_user(user_id)
        
        # Check email uniqueness if changing
        if user_data.email and user_data.email != user.email:
            existing = await self.repo.get_by_email(user_data.email)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use",
                )
            user.email = user_data.email
        
        if user_data.full_name is not None:
            user.full_name = user_data.full_name
        
        return await self.repo.update(user)
    
    async def deactivate_user(
        self, user_id: UUID, reason: str | None = None
    ) -> User:
        """Deactivate user account."""
        user = await self.get_user(user_id)
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already deactivated",
            )
        
        user.is_active = False
        # Store reason if needed (would require additional field)
        return await self.repo.update(user)
    
    async def reactivate_user(self, user_id: UUID) -> User:
        """Reactivate user account."""
        user = await self.get_user(user_id)
        
        if user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already active",
            )
        
        user.is_active = True
        return await self.repo.update(user)




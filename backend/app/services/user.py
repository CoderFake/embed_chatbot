from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis
from datetime import datetime
import pytz

from app.models.user import User
from app.cache.service import CacheService
from app.cache.keys import CacheKeys
from app.config.settings import settings
from app.utils.logging import get_logger
from app.utils.datetime_utils import now
from app.utils.hasher import Hasher

logger = get_logger(__name__)


class UserService:
    """
    User service with cache integration.
    """
    
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.cache = CacheService(redis)
        self.hasher = Hasher()
    
    async def get_by_id(self, user_id: str) -> Optional[User]:
        """
        Get user by ID with cache-aside pattern.
        
        Args:
            user_id: User UUID
            
        Returns:
            User instance or None
        """
        cache_key = CacheKeys.user(user_id)
        cached_data = await self.cache.get(cache_key)
        
        if cached_data:
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if user:
                if cached_data.get("last_login"):
                    user.last_login = datetime.fromisoformat(cached_data["last_login"])

            return user
        
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user_dict = {
                "id": str(user.id),
                "email": user.email,
                "password_hash": user.password_hash,
                "full_name": user.full_name,
                "role": user.role.value,
                "is_active": user.is_active,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "created_at": user.created_at.isoformat(),
                "updated_at": user.updated_at.isoformat(),
            }
            await self.cache.set(cache_key, user_dict, ttl=settings.CACHE_USER_TTL)
        
        return user
    
    async def get_by_email(self, email: str, include_deleted: bool = False) -> Optional[User]:
        """
        Get user by email.
        
        Args:
            email: User email
            include_deleted: Include deleted users in search
            
        Returns:
            User instance or None
        """
        query = select(User).where(User.email == email)
        if not include_deleted:
            query = query.where(User.is_deleted == False)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def create(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str
    ) -> User:
        """
        Create new user with hashed password.
        
        Args:
            email: User email
            password: Plain text password
            full_name: User full name
            role: User role
            
        Returns:
            Created user instance
        """
        password_hash = self.hasher.hash_password(password)
        
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
            is_active=True,
            last_login=None
        )
        
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        
        logger.info(f"Created user: {user.email} with role: {user.role}")
        return user
    
    async def update(
        self,
        user: User,
        full_name: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> User:
        """
        Update existing user and invalidate cache.
        
        Args:
            user: User instance to update
            full_name: Optional new full name
            role: Optional new role
            is_active: Optional new active status
            
        Returns:
            Updated user instance
        """
        if full_name is not None:
            user.full_name = full_name
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        
        await self.db.flush()
        await self.db.refresh(user)
        
        cache_key = CacheKeys.user(str(user.id))
        await self.cache.delete(cache_key)
        
        logger.info(f"Updated user: {user.email}")
        return user
    
    async def delete(self, user: User) -> None:
        """
        Soft delete user (set is_deleted=True) and invalidate cache.
        
        Args:
            user: User instance to soft delete
        """
        
        user_id = str(user.id)
        user.is_deleted = True
        user.deleted_at = now()
        user.is_active = False 
        
        await self.db.flush()
        
        cache_key = CacheKeys.user(user_id)
        await self.cache.delete(cache_key)
        
        logger.info(f"Soft deleted user: {user.email}")
    
    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None
    ) -> List[User]:
        """
        Get all users with optional filtering (excludes deleted users).
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            is_active: Optional filter by active status
            
        Returns:
            List of users
        """
        query = select(User).where(User.is_deleted == False)
        
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        
        query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def activate(self, user: User) -> User:
        """
        Activate user account.
        
        Args:
            user: User instance
            
        Returns:
            Updated user instance
        """
        user.is_active = True
        await self.db.flush()
        await self.db.refresh(user)
        
        cache_key = CacheKeys.user(str(user.id))
        await self.cache.delete(cache_key)
        
        logger.info(f"Activated user: {user.email}")
        return user
    
    async def deactivate(self, user: User) -> User:
        """
        Deactivate user account.
        
        Args:
            user: User instance
            
        Returns:
            Updated user instance
        """
        user.is_active = False
        await self.db.flush()
        await self.db.refresh(user)
        
        cache_key = CacheKeys.user(str(user.id))
        await self.cache.delete(cache_key)
        
        logger.info(f"Deactivated user: {user.email}")
        return user


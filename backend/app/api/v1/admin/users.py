from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db, get_redis
from app.core.dependencies import Admin, Root, get_current_user
from app.common.types import CurrentUser
from app.common.enums import UserRole
from app.services.user import UserService
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("", response_model=UserResponse, dependencies=[Depends(Admin)])
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Create a new user.
    
    **Required role:** root, admin
    """
    user_service = UserService(db, redis)
    
    existing_user = await user_service.get_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    user = await user_service.create(
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name,
        role=user_data.role.value
    )
    
    await db.commit()
    
    logger.info(f"User created: {user.email} by {current_user.email}")
    
    return user


@router.get("", response_model=List[UserResponse], dependencies=[Depends(Admin)])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    List all users with optional filtering.
    
    **Required role:** root, admin
    """
    user_service = UserService(db, redis)
    
    users = await user_service.get_all(
        skip=skip,
        limit=limit,
        is_active=is_active
    )
    
    return users


@router.get("/{user_id}", response_model=UserResponse, dependencies=[Depends(Admin)])
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Get user details by ID.
    
    **Required role:** root, admin
    """
    user_service = UserService(db, redis)
    
    user = await user_service.get_by_id(str(user_id))
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Update user details.
    
    **Required role:** Any authenticated user (for self-edit), admin/root (for others)
    
    **Permission rules:**
    - Any user: Can update their own full_name
    - Root: Can update any user
    - Admin: Can only update their own profile
    """
    user_service = UserService(db, redis)
    
    user = await user_service.get_by_id(str(user_id))
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    is_self = str(user.id) == current_user.user_id
    is_root = current_user.role == UserRole.ROOT.value
    is_admin = current_user.role == UserRole.ADMIN.value
    
    if not is_root and not is_admin and not is_self:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile"
        )
    
    if is_admin and not is_self:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin can only update their own profile"
        )
    
    
    if str(user.id) == current_user.user_id:
        if user_data.role and user_data.role.value != current_user.role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change your own role"
            )
        if user_data.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own account"
            )
    
    updated_user = await user_service.update(
        user=user,
        full_name=user_data.full_name,
        role=user_data.role.value if user_data.role else None,
        is_active=user_data.is_active
    )
    
    await db.commit()
    
    logger.info(f"User updated: {user.email} by {current_user.email}")
    
    return updated_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(Root)])
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Root)
):
    """
    Delete user permanently.
    
    **Required role:** root only
    
    **Permission rules:**
    - Root: Can delete Admin and Member (cannot delete Root)
    - Admin: Cannot delete anyone (no access to this endpoint)
    """
    user_service = UserService(db, redis)
    
    user = await user_service.get_by_id(str(user_id))
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if str(user.id) == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    if user.role == UserRole.ROOT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete Root users"
        )
    
    await user_service.delete(user)
    await db.commit()
    
    logger.info(f"User deleted: {user.email} by {current_user.email}")


@router.post("/{user_id}/activate", response_model=UserResponse, dependencies=[Depends(Admin)])
async def activate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Activate user account.
    
    **Required role:** root, admin
    """
    user_service = UserService(db, redis)
    
    user = await user_service.get_by_id(str(user_id))
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    activated_user = await user_service.activate(user)
    await db.commit()
    
    logger.info(f"User activated: {user.email} by {current_user.email}")
    
    return activated_user


@router.post("/{user_id}/deactivate", response_model=UserResponse, dependencies=[Depends(Admin)])
async def deactivate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Deactivate user account.
    
    **Required role:** root, admin
    
    **Permission rules:**
    - Root: Can deactivate any user (Admin, Member)
    - Admin: Can only deactivate Member (cannot deactivate Admin or Root)
    """
    user_service = UserService(db, redis)
    
    user = await user_service.get_by_id(str(user_id))
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if str(user.id) == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    if current_user.role == UserRole.ADMIN.value:
        if str(user.id) != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin can only manage their own profile"
            )
    
    deactivated_user = await user_service.deactivate(user)
    await db.commit()
    
    logger.info(f"User deactivated: {user.email} by {current_user.email}")
    
    return deactivated_user


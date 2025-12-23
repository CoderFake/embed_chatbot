from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis

from app.core.database import get_db, get_redis
from app.core.security import decode_token, verify_token_type
from app.common.types import CurrentUser
from app.common.enums import UserRole
from app.utils.logging import get_logger
from app.cache.keys import CacheKeys

logger = get_logger(__name__)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
) -> CurrentUser:
    """
    Get current authenticated user from JWT token.
    Validates token, checks blacklist, and verifies user is active.
    
    Args:
        credentials: HTTP Bearer credentials
        db: Database session
        redis: Redis client
        
    Returns:
        CurrentUser instance
        
    Raises:
        HTTPException: If authentication fails or user is deactivated
    """
    token = credentials.credentials
    
    payload = decode_token(token)
    
    verify_token_type(payload, "access")
    
    jti = payload.get("jti")
    if jti:
        is_blacklisted = await redis.exists(CacheKeys.blacklist(jti))
        if is_blacklisted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    user_id = payload.get("sub")
    email = payload.get("email")
    role = payload.get("role")
    full_name = payload.get("full_name")
    
    if not user_id or not email or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    from app.models.user import User
    
    result = await db.execute(
        select(User.is_active).where(User.id == UUID(user_id))
    )
    is_active = result.scalar_one_or_none()
    
    if is_active is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated",
        )
    
    return CurrentUser(
        user_id=user_id,
        email=email,
        role=role,
        full_name=full_name
    )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
) -> Optional[CurrentUser]:
    """
    Get current user if authenticated, None otherwise.
    Useful for endpoints that work for both authenticated and anonymous users.
    
    Args:
        credentials: Optional HTTP Bearer credentials
        db: Database session
        redis: Redis client
        
    Returns:
        CurrentUser instance or None
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db, redis)
    except HTTPException:
        return None


def _require_role(*allowed_roles: str):
    """
    Internal function to create role checker dependency.
    
    Args:
        *allowed_roles: Variable number of allowed role names
        
    Returns:
        Dependency function that checks user role
    """
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if not current_user.has_role(*allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {', '.join(allowed_roles)}"
            )
        logger.info(f"User {current_user.email} authorized with role {current_user.role}")
        return current_user
    
    return role_checker


Root = _require_role(UserRole.ROOT.value)
Admin = _require_role(UserRole.ROOT.value, UserRole.ADMIN.value)
Member = _require_role(UserRole.ROOT.value, UserRole.ADMIN.value, UserRole.MEMBER.value)


async def get_widget_session(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    redis: Redis = Depends(get_redis)
) -> dict:
    """
    Get and validate widget session from token.
    
    Args:
        credentials: HTTP Bearer credentials
        redis: Redis client
        
    Returns:
        Dictionary with session data (bot_id, visitor_id, session_id, origin)
        
    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    
    payload = decode_token(token)
    
    verify_token_type(payload, "widget")
    
    jti = payload.get("jti")
    if jti:
        is_blacklisted = await redis.exists(CacheKeys.blacklist(jti))
        if is_blacklisted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been closed",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    visitor_id = payload.get("sub")
    bot_id = payload.get("bot_id")
    session_id = payload.get("session_id")
    origin = payload.get("origin")
    
    if not all([visitor_id, bot_id, session_id, origin]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid widget token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "visitor_id": visitor_id,
        "bot_id": bot_id,
        "session_id": session_id,
        "origin": origin,
        "jti": jti
    }


async def verify_admin_token(token: str, db: AsyncSession) -> None:
    """
    Verify admin token for SSE endpoints (since EventSource can't send headers).
    
    Args:
        token: Access token from query string
        db: Database session
        
    Raises:
        HTTPException: If token invalid or user not admin/root
    """
    try:
        payload = decode_token(token)
        verify_token_type(payload, "access")
        
        user_id = payload.get("sub")
        
        from app.models.user import User
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user or user.role not in [UserRole.ADMIN.value, UserRole.ROOT.value]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SSE authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis
from jose import jwt, JWTError
from fastapi import HTTPException, status, Request
import uuid

from app.models.user import User, Blacklist, TokenType
from app.cache.invalidation import CacheInvalidation
from app.services.user import UserService
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_jti_from_token,
    decode_token,
    verify_token_type
)
from app.utils.hasher import Hasher
from app.cache.service import CacheService
from app.cache.keys import CacheKeys
from app.config.settings import settings
from app.utils.logging import get_logger
from app.utils.email_queue import queue_email
from app.utils.request_utils import get_request_origin
from app.utils.datetime_utils import now
from app.common.constants import (
    EmailSubject,
    ResponseMessage,
    RedisKeyPrefix,
    FrontendRoute,
    DefaultValue
)

logger = get_logger(__name__)


class AuthService:
    """
    Authentication service for login, logout, and token management.
    """
    
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.cache = CacheService(redis)
        self.user_service = UserService(db, redis)
        self.hasher = Hasher()
    
    async def login(
        self,
        email: str,
        password: str
    ) -> Tuple[str, str, User, bool]:
        """
        Authenticate user and generate tokens.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            Tuple of (access_token, refresh_token, user, force_password_change)
            
        Raises:
            HTTPException: If authentication fails
        """
        user = await self.user_service.get_by_email(email)
        
        if not user:
            logger.warning(f"Login failed: user not found - {email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        if not user.is_active:
            logger.warning(f"Login failed: user inactive - {email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        if not self.hasher.verify_password(password, user.password_hash):
            logger.warning(f"Login failed: invalid password - {email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        force_password_change = user.last_login is None
        
        user.last_login = now()
        await self.db.flush()
        await self.db.commit()
        
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "full_name": user.full_name
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token({"sub": str(user.id)})
        
        logger.info(f"User logged in successfully: {email} (force_password_change={force_password_change})")
        
        return access_token, refresh_token, user, force_password_change
    
    async def logout(
        self,
        access_token: str,
        refresh_token: Optional[str] = None
    ) -> None:
        """
        Logout user by blacklisting tokens.
        
        Args:
            access_token: Access token to blacklist
            refresh_token: Optional refresh token to blacklist
        """
        access_jti = get_jti_from_token(access_token)
        if access_jti:
            cache_key = CacheKeys.blacklist(access_jti)
            ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            await self.cache.set(cache_key, {"revoked": True}, ttl=ttl, as_json=True)
            
            blacklist_entry = Blacklist(
                token=access_jti,
                token_type=TokenType.ACCESS,
                reason="logout",
                blacklisted_at=now(),
                expires_at=now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            )
            self.db.add(blacklist_entry)
        
        if refresh_token:
            refresh_jti = get_jti_from_token(refresh_token)
            if refresh_jti:
                cache_key = CacheKeys.blacklist(refresh_jti)
                ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
                await self.cache.set(cache_key, {"revoked": True}, ttl=ttl, as_json=True)
                
            blacklist_entry = Blacklist(
                token=refresh_jti,
                token_type=TokenType.REFRESH,
                reason="logout",
                blacklisted_at=now(),
                expires_at=now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
            )
            self.db.add(blacklist_entry)
        
        await self.db.commit()
        logger.info("User logged out successfully")
    
    async def refresh_access_token(
        self,
        refresh_token: str
    ) -> tuple[str, str]:
        """
        Generate new access token and refresh token (rotating refresh token).

        Implements rotating refresh token pattern:
        1. Validate old refresh token
        2. Generate new access token AND new refresh token
        3. Blacklist old refresh token
        4. Return both new tokens

        Args:
            refresh_token: Valid refresh token

        Returns:
            Tuple of (new_access_token, new_refresh_token)

        Raises:
            HTTPException: If refresh token is invalid or blacklisted
        """
        payload = decode_token(refresh_token)
        verify_token_type(payload, "refresh")

        jti = payload.get("jti")
        if jti:
            is_blacklisted = await self.redis.exists(CacheKeys.blacklist(jti))
            if is_blacklisted:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token has been revoked"
                )

        user_id = payload.get("sub")
        user = await self.user_service.get_by_id(user_id)

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "full_name": user.full_name
        }

        new_access_token = create_access_token(token_data)
        new_refresh_token = create_refresh_token(token_data)

        if jti:
            blacklist_entry = Blacklist(
                token=jti,
                token_type=TokenType.REFRESH,
                reason="token_rotation",
                blacklisted_at=now(),
                expires_at=now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
            )
            self.db.add(blacklist_entry)
            await self.db.commit()

            ttl = int(payload.get("exp") - datetime.now(timezone.utc).timestamp())
            if ttl > 0:
                await self.redis.setex(
                    CacheKeys.blacklist(jti),
                    ttl,
                    "1"
                )

        logger.info(f"Access token and refresh token rotated for user: {user.email}")

        return new_access_token, new_refresh_token
    
    async def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str,
        request: Optional[Request] = None
    ) -> None:
        """
        Change user password and blacklist all existing tokens.
        
        Args:
            user_id: User UUID
            old_password: Current password
            new_password: New password
            request: Optional Request object for IP tracking
            
        Raises:
            HTTPException: If old password is incorrect
        """
        user = await self.user_service.get_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if not self.hasher.verify_password(old_password, user.password_hash):
            logger.warning(f"Password change failed: invalid old password - {user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password"
            )
        
        user.password_hash = self.hasher.hash_password(new_password)
        await self.db.flush()
        
        result = await self.db.execute(
            select(Blacklist).where(Blacklist.user_id == user_id)
        )
        existing_blacklist = result.scalars().all()
        jti_set = {bl.token for bl in existing_blacklist}
        
        user_tokens_key = f"{RedisKeyPrefix.USER_TOKENS}:{user_id}"
        cached_tokens = await self.cache.get(user_tokens_key)
        
        if cached_tokens:
            for token_jti in cached_tokens:
                if token_jti not in jti_set:
                    blacklist_entry = Blacklist(
                        token=token_jti,
                        user_id=user_id,
                        token_type=TokenType.ACCESS,
                        blacklisted_at=now(),
                        expires_at=now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
                    )
                    self.db.add(blacklist_entry)
        
        await self.db.commit()
        
        logger.info(f"Password changed successfully for user: {user.email}")
        
        cache_invalidation = CacheInvalidation(self.redis)
        await cache_invalidation.invalidate_user(user_id)
        
        await self.redis.delete(user_tokens_key)
        
        logger.warning(f"Password changed - all tokens blacklisted: {user.email}")
        
        ip_address = request.client.host if request and request.client else DefaultValue.UNKNOWN_IP
        try:
            await queue_email(
                recipient_email=user.email,
                subject=EmailSubject.PASSWORD_CHANGED,
                template_name="password_changed.html",
                context={
                    "user_name": user.full_name or user.email,
                    "changed_at": now().strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "ip_address": ip_address,
                    "app_name": settings.APP_NAME,
                },
                priority=7
            )
        except Exception as e:
            logger.error(f"Failed to queue password changed email: {e}", exc_info=True)
    
    async def request_password_reset(
        self,
        email: str,
        request: Optional[Request] = None
    ) -> str:
        """
        Generate password reset token and send email.
        
        Args:
            email: User email
            request: Optional Request object to get origin
            
        Returns:
            Success message (token not exposed for security)
            
        Raises:
            HTTPException: If user not found or inactive
        """
        user = await self.user_service.get_by_email(email)
        
        if not user:
            logger.warning(f"Password reset requested for non-existent email: {email}")
            return ResponseMessage.RESET_EMAIL_SENT
        
        if not user.is_active:
            logger.warning(f"Password reset requested for inactive user: {email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive. Please contact support."
            )
        
        if user.is_deleted:
            logger.warning(f"Password reset requested for deleted user: {email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account has been deleted. Please contact support."
            )
        
        current_time = now()
        expire = current_time + timedelta(hours=settings.PASSWORD_RESET_EXPIRE_HOURS)
        reset_token_data = {
            "sub": str(user.id),
            "email": user.email,
            "purpose": "password_reset",
            "exp": expire,
            "iat": current_time,
            "jti": str(uuid.uuid4())
        }
        
        reset_token = jwt.encode(
            reset_token_data,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        reset_key = f"{RedisKeyPrefix.PASSWORD_RESET}:{user.id}"
        ttl_seconds = settings.PASSWORD_RESET_EXPIRE_HOURS * 3600
        await self.cache.set(reset_key, {"token": reset_token, "used": False}, ttl=ttl_seconds)
        
        logger.info(f"Password reset token generated for user: {email}")
        
        frontend_origin = settings.FRONTEND_URL
        if request:
            try:
                frontend_origin = get_request_origin(request)
            except Exception:
                pass
        
        reset_url = f"{frontend_origin}{FrontendRoute.RESET_PASSWORD}#token={reset_token}"
        
        try:
            await queue_email(
                recipient_email=user.email,
                subject=EmailSubject.PASSWORD_RESET,
                template_name="password_reset.html",
                context={
                    "reset_url": reset_url,
                    "expire_hours": settings.PASSWORD_RESET_EXPIRE_HOURS,
                    "app_name": settings.APP_NAME,
                },
                priority=8
            )
            logger.info(f"Password reset email queued for: {email}")
        except Exception as e:
            logger.error(f"Failed to queue password reset email: {e}", exc_info=True)
        
        return ResponseMessage.RESET_EMAIL_SENT
    
    async def reset_password(
        self,
        reset_token: str,
        new_password: str,
        request: Optional[Request] = None
    ) -> None:
        """
        Reset password using reset token.
        
        Args:
            reset_token: Password reset token
            new_password: New password
            request: Optional Request object for IP tracking
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        
        try:
            payload = decode_token(reset_token)
            
            if payload.get("purpose") != "password_reset":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid reset token"
                )
            
            user_id = payload.get("sub")
            
            reset_key = f"{RedisKeyPrefix.PASSWORD_RESET}:{user_id}"
            token_data = await self.cache.get(reset_key)
            
            if not token_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Reset token expired or already used"
                )
            
            if token_data.get("used"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Reset token already used"
                )
            
            # Get user
            user = await self.user_service.get_by_id(user_id)
            
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found or inactive"
                )
            
            user.password_hash = self.hasher.hash_password(new_password)
            await self.db.flush()
            await self.db.commit()
            
            ttl_seconds = settings.PASSWORD_RESET_EXPIRE_HOURS * 3600
            await self.cache.set(reset_key, {"token": reset_token, "used": True}, ttl=ttl_seconds)
            
            jti = get_jti_from_token(reset_token)
            if jti:
                blacklist_entry = Blacklist(
                    token=jti,
                    user_id=user_id,
                    token_type=TokenType.PASSWORD_RESET,
                    reason="Password reset completed",
                    blacklisted_at=now(),
                    expires_at=now() + timedelta(hours=settings.PASSWORD_RESET_EXPIRE_HOURS)
                )
                self.db.add(blacklist_entry)
                await self.db.flush()
                
                cache_key = CacheKeys.blacklist(jti)
                await self.cache.set(cache_key, {"revoked": True}, ttl=ttl_seconds, as_json=True)
            
            cache_invalidation = CacheInvalidation(self.redis)
            await cache_invalidation.invalidate_user(user_id)
            
            logger.info(f"Password reset successfully for user: {user.email}")
            
            ip_address = request.client.host if request and request.client else DefaultValue.UNKNOWN_IP
            try:
                await queue_email(
                    recipient_email=user.email,
                    subject=EmailSubject.PASSWORD_CHANGED,
                    template_name="password_changed.html",
                    context={
                        "user_name": user.full_name or user.email,
                        "changed_at": now().strftime("%Y-%m-%d %H:%M:%S %Z"),
                        "ip_address": ip_address,
                        "app_name": settings.APP_NAME,
                    },
                    priority=7
                )
            except Exception as e:
                logger.error(f"Failed to queue password changed email: {e}", exc_info=True)
            
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired reset token"
            )


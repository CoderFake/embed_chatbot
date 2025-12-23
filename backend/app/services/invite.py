from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis
from fastapi import HTTPException, status, Request
import uuid
import secrets
import string

from app.models.user import Invite, User, InviteStatus, UserRole, Blacklist, TokenType
from app.core.security import create_invite_token, decode_token, get_jti_from_token
from app.services.user import UserService
from app.services.notification import NotificationService
from app.common.enums import NotificationType
from app.cache.service import CacheService
from app.cache.keys import CacheKeys
from app.config.settings import settings
from app.utils.logging import get_logger
from app.utils.email_queue import queue_email
from app.utils.request_utils import get_request_origin
from app.utils.datetime_utils import now
from app.utils.hasher import Hasher
from app.common.constants import ResponseMessage
from app.common.constants import EmailSubject, FrontendRoute, DefaultValue

logger = get_logger(__name__)


class InviteService:
    """
    Invite service for managing user invitations.
    """
    
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.cache = CacheService(redis)
        self.user_service = UserService(db, redis)
    
    def _generate_random_password(self, length: int = 12) -> str:
        """
        Generate secure random password.
        
        Args:
            length: Password length (default 12)
            
        Returns:
            Random password string
        """
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        
        if not any(c.islower() for c in password):
            password = password[:-1] + secrets.choice(string.ascii_lowercase)
        if not any(c.isupper() for c in password):
            password = password[:-2] + secrets.choice(string.ascii_uppercase) + password[-1]
        if not any(c.isdigit() for c in password):
            password = password[:-3] + secrets.choice(string.digits) + password[-2:]
        
        return password
    
    async def create_invite(
        self,
        email: str,
        role: str,
        invited_by_id: str,
        request: Optional[Request] = None
    ) -> Invite:
        """
        Create new invite and generate token.
        
        Args:
            email: Email to invite
            role: Role to assign
            invited_by_id: User ID who created the invite
            request: Optional Request object to get origin
            
        Returns:
            Created invite instance
            
        Raises:
            HTTPException: If user already exists
        """
        existing_user = await self.user_service.get_by_email(email, include_deleted=True)
        
        if existing_user:
            if existing_user.is_deleted:
                existing_user.is_deleted = False
                existing_user.deleted_at = None
                existing_user.is_active = True
                existing_user.last_login = None 
                existing_user.role = role
                
                await self.db.flush()
                logger.info(f"Reactivated deleted user: {email} with role {role}")
                
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User with this email already exists"
                )
        
        existing_invite = await self.get_by_email_pending(email)
        if existing_invite:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pending invite for this email already exists"
            )
        
        token = create_invite_token(email, role)
        
        random_password = self._generate_random_password()
        
        invite = Invite(
            email=email,
            token=token,
            role=role,
            invited_by=invited_by_id,
            status=InviteStatus.PENDING,
            expires_at=now() + timedelta(days=settings.INVITE_TOKEN_EXPIRE_DAYS)
        )
        
        self.db.add(invite)
        await self.db.flush()
        await self.db.refresh(invite)
        
        password_key = CacheKeys.invite_password(token)
        await self.redis.setex(
            password_key,
            timedelta(days=settings.INVITE_TOKEN_EXPIRE_DAYS),
            random_password
        )
        
        logger.info(f"Invite created for {email} with role {role}")
        
        inviter = await self.user_service.get_by_id(invited_by_id)
        inviter_name = inviter.full_name if inviter and inviter.full_name else DefaultValue.UNKNOWN_IP
        
        frontend_origin = settings.FRONTEND_URL
        if request:
            try:
                frontend_origin = get_request_origin(request)
            except Exception:
                pass
        
        accept_url = f"{frontend_origin}{FrontendRoute.ACCEPT_INVITE}#token={token}"
        
        try:
            await queue_email(
                recipient_email=email,
                subject=EmailSubject.INVITE_USER,
                template_name="invite.html",
                context={
                    "inviter_name": inviter_name,
                    "role": role.title(),
                    "email": email,
                    "password": random_password,
                    "accept_url": accept_url,
                    "expire_days": settings.INVITE_TOKEN_EXPIRE_DAYS,
                    "app_name": settings.APP_NAME,
                },
                priority=7
            )
        except Exception as e:
            logger.error(f"Failed to queue invite email: {e}", exc_info=True)
        
        logger.info(f"Invite email sent to: {email} with login credentials")
        
        return invite
    
    async def get_by_id(self, invite_id: str) -> Optional[Invite]:
        """
        Get invite by ID.
        
        Args:
            invite_id: Invite UUID
            
        Returns:
            Invite instance or None
        """
        result = await self.db.execute(
            select(Invite).where(Invite.id == invite_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_token(self, token: str) -> Optional[Invite]:
        """
        Get invite by token.
        
        Args:
            token: Invite token
            
        Returns:
            Invite instance or None
        """
        result = await self.db.execute(
            select(Invite).where(Invite.token == token)
        )
        return result.scalar_one_or_none()
    
    async def get_by_email_pending(self, email: str) -> Optional[Invite]:
        """
        Get pending invite by email.
        
        Args:
            email: User email
            
        Returns:
            Invite instance or None
        """
        result = await self.db.execute(
            select(Invite)
            .where(Invite.email == email)
            .where(Invite.status == InviteStatus.PENDING)
        )
        return result.scalar_one_or_none()
    
    async def get_all(
        self,
        status: Optional[InviteStatus] = None,
        skip: int = 0,
        limit: int = 100,
        invited_by_id: Optional[str] = None
    ) -> List[Invite]:
        """
        Get all invites with optional filtering.
        
        Args:
            status: Optional filter by status
            skip: Number of records to skip
            limit: Maximum number of records to return
            invited_by_id: Optional filter by who created the invite
            
        Returns:
            List of invites
        """
        query = select(Invite)
        
        if status:
            query = query.where(Invite.status == status)
        
        if invited_by_id:
            query = query.where(Invite.invited_by == invited_by_id)
        
        query = query.offset(skip).limit(limit).order_by(Invite.created_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def confirm_invite(self, token: str) -> dict:
        """
        Accept invite, create user account, and prepare for first login.
        
        Args:
            token: Invite token from email
            
        Returns:
            Dict with email and message
            
        Raises:
            HTTPException: If invite is invalid, expired, or already used
        """

        payload = decode_token(token)
        email = payload.get("sub")
        
        invite = await self.get_by_token(token)
        
        if not invite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite not found"
            )
        
        if invite.status != InviteStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invite is {invite.status.value}"
            )
        
        if invite.expires_at < now():
            invite.status = InviteStatus.EXPIRED
            await self.db.flush()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invite has expired"
            )
        
        password_key = CacheKeys.invite_password(token)
        password = await self.redis.get(password_key)
        
        if not password:
            logger.error(f"Invite password not found in Redis for: {email}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invite password expired. Please request a new invite."
            )

        existing_user = await self.user_service.get_by_email(email)
        
        if existing_user:
            if existing_user.last_login is None and not existing_user.is_deleted:
                hasher = Hasher()
                existing_user.password_hash = hasher.hash_password(
                    password.decode() if isinstance(password, bytes) else password
                )
                existing_user.last_login = None
                await self.db.flush()
                logger.info(f"Updated password for reactivated user: {email}")
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User already exists. Please login instead."
                )
        else:
            user = await self.user_service.create(
                email=email,
                password=password.decode() if isinstance(password, bytes) else password,
                full_name=email.split('@')[0], 
                role=invite.role.value
            )
            await self.db.flush()

        await self.redis.delete(password_key)
        
        invite.status = InviteStatus.ACCEPTED
        invite.accepted_at = now()
        await self.db.flush()
        
        try:
            jti = get_jti_from_token(token)
            user = await self.user_service.get_by_email(email)
            if user:
                blacklist_entry = Blacklist(
                    token=jti,
                    user_id=user.id,
                    token_type=TokenType.INVITE,
                    reason="Invite token used",
                    blacklisted_at=now(),
                    expires_at=invite.expires_at
                )
                self.db.add(blacklist_entry)
                await self.db.flush()
                logger.info(f"Invite token blacklisted: {email}")
        except Exception as e:
            logger.warning(f"Failed to blacklist invite token: {e}")
        
        notification_service = NotificationService(self.db, self.redis)
        try:
            await notification_service.create_notification(
                user_id=str(invite.invited_by),
                title="Invite Accepted",
                message=f"{email} has accepted your invitation",
                notification_type=NotificationType.INVITE_ACCEPTED,
                link="/dashboard/users"
            )
            logger.info(f"Notification sent to inviter: {invite.invited_by}")
        except Exception as e:
            logger.warning(f"Failed to create invite acceptance notification: {e}")
        
        logger.info(f"Invite confirmed and user created: {email}")
        
        return {
            "email": email,
            "message": ResponseMessage.INVITE_ACCEPTED
        }
    
    async def revoke_invite(self, invite_id: str) -> Invite:
        """
        Revoke pending invite.
        
        Args:
            invite_id: Invite UUID
            
        Returns:
            Updated invite instance
            
        Raises:
            HTTPException: If invite not found or already processed
        """
        invite = await self.get_by_id(invite_id)
        
        if not invite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite not found"
            )
        
        if invite.status != InviteStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot revoke invite with status: {invite.status.value}"
            )
        
        invite.status = InviteStatus.REVOKED
        await self.db.flush()
        await self.db.refresh(invite)
        
        logger.info(f"Invite revoked: {invite.email}")
        
        return invite
    
    async def resend_invite(
        self,
        invite_id: str,
        request: Optional[Request] = None
    ) -> Invite:
        """
        Resend invite email and extend expiration.
        
        Args:
            invite_id: Invite UUID
            request: Optional Request object to get origin
            
        Returns:
            Updated invite instance
            
        Raises:
            HTTPException: If invite not found or not pending
        """
        invite = await self.get_by_id(invite_id)
        
        if not invite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite not found"
            )
        
        if invite.status != InviteStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resend invite with status: {invite.status.value}"
            )
        
        invite.expires_at = now() + timedelta(days=settings.INVITE_TOKEN_EXPIRE_DAYS)
        await self.db.flush()
        await self.db.refresh(invite)
        
        new_password = self._generate_random_password()
        
        password_key = CacheKeys.invite_password(invite.token)
        await self.redis.setex(
            password_key,
            timedelta(days=settings.INVITE_TOKEN_EXPIRE_DAYS),
            new_password
        )
        
        logger.info(f"Invite resent with new password: {invite.email}")
        
        inviter = await self.user_service.get_by_id(invite.invited_by)
        inviter_name = inviter.full_name if inviter and inviter.full_name else DefaultValue.UNKNOWN_IP
        
        frontend_origin = settings.FRONTEND_URL
        if request:
            try:
                frontend_origin = get_request_origin(request)
            except Exception:
                pass
        
        accept_url = f"{frontend_origin}{FrontendRoute.ACCEPT_INVITE}#token={invite.token}"
        
        try:
            await queue_email(
                recipient_email=invite.email,
                subject=EmailSubject.INVITE_USER,
                template_name="invite.html",
                context={
                    "inviter_name": inviter_name,
                    "role": invite.role.title(),
                    "email": invite.email,
                    "password": new_password,
                    "accept_url": accept_url,
                    "expire_days": settings.INVITE_TOKEN_EXPIRE_DAYS,
                    "app_name": settings.APP_NAME,
                },
                priority=7
            )
        except Exception as e:
            logger.error(f"Failed to queue resend invite email: {e}", exc_info=True)
        
        logger.info(f"Invite email resent to: {invite.email} with new login credentials")
        
        return invite


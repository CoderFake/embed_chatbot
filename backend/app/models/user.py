from datetime import datetime
import uuid
from sqlalchemy import Column, String, Boolean, Enum as SQLEnum, ForeignKey, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin
from app.common.enums import UserRole, InviteStatus, TokenType


class User(Base, TimestampMixin):
    """
    User model for authentication and authorization.
    """
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.MEMBER, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class Invite(Base, TimestampMixin):
    """
    User invite model for invite-based registration.
    """
    __tablename__ = "invites"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, index=True)
    token = Column(Text, unique=True, nullable=False, index=True)
    role = Column(SQLEnum(UserRole), default=UserRole.MEMBER, nullable=False)
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(SQLEnum(InviteStatus), default=InviteStatus.PENDING, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self) -> str:
        return f"<Invite(id={self.id}, email={self.email}, status={self.status})>"


class Blacklist(Base):
    """
    Token blacklist for revoked JWT tokens.
    """
    __tablename__ = "blacklist"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(Text, unique=True, nullable=False, index=True)  # JTI from JWT
    token_type = Column(SQLEnum(TokenType), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reason = Column(Text, nullable=True)
    blacklisted_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    def __repr__(self) -> str:
        return f"<Blacklist(token_type={self.token_type}, user_id={self.user_id})>"


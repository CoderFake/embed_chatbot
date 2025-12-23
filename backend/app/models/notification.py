import uuid
from sqlalchemy import Column, String, Text, Boolean, Enum as SQLEnum, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base
from app.common.enums import NotificationType
from app.utils.datetime_utils import now


class Notification(Base):
    """
    User notification model.
    """
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(
        SQLEnum(
            NotificationType,
            name='notificationtype',
            values_callable=lambda x: [e.value for e in x],
            create_constraint=False
        ),
        nullable=False
    )
    link = Column(String(500), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    extra_data = Column(JSONB, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, user_id={self.user_id}, type={self.notification_type})>"


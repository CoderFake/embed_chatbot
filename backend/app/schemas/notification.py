from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from uuid import UUID

from app.models.notification import NotificationType


class NotificationResponse(BaseModel):
    """Schema for notification response."""
    id: UUID
    user_id: UUID
    title: str
    message: str
    notification_type: NotificationType
    link: Optional[str] = None
    is_read: bool
    extra_data: Dict[str, Any]
    created_at: datetime
    read_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


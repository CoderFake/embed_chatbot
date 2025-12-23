"""
Widget schemas for API request/response.
"""
from typing import Dict, List
from pydantic import BaseModel, Field, ConfigDict


class WidgetInitRequest(BaseModel):
    """Request schema for widget initialization."""
    bot_id: str = Field(..., description="Bot ID to connect to")
    session_token: str = Field(..., description="Unique session token from client")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "bot_id": "550e8400-e29b-41d4-a716-446655440000",
                "session_token": "sess_abc123xyz"
            }
        }
    )


class VisitorProfile(BaseModel):
    """Visitor profile information."""
    name: str | None = Field(None, description="Visitor name")
    email: str | None = Field(None, description="Visitor email")
    phone: str | None = Field(None, description="Visitor phone")
    address: str | None = Field(None, description="Visitor address")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "+1234567890",
                "address": "123 Main St"
            }
        }
    )


class WidgetInitResponse(BaseModel):
    """Response schema for widget initialization."""
    visitor_id: str = Field(..., description="Visitor UUID")
    session_id: str = Field(..., description="Chat session UUID")
    session_token: str = Field(..., description="Session token for subsequent requests")
    visitor_profile: VisitorProfile = Field(..., description="Current visitor profile")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "visitor_id": "550e8400-e29b-41d4-a716-446655440000",
                "session_id": "660e8400-e29b-41d4-a716-446655440001",
                "session_token": "sess_abc123xyz",
                "visitor_profile": {
                    "name": "John Doe",
                    "email": "john@example.com",
                    "phone": "+1234567890",
                    "address": "123 Main St"
                }
            }
        }
    )


class WidgetConfigResponse(BaseModel):
    """
    Widget configuration response.
    Returns complete display configuration from bot's display_config JSONB field.
    """
    bot_id: str = Field(..., description="Bot ID")
    bot_name: str = Field(..., description="Bot name")
    bot_key: str = Field(..., description="Bot key")
    language: str | None = Field(None, description="Bot language")
    display_config: dict = Field(..., description="Complete widget display configuration (see DisplayConfig model)")
    welcome_message: str | None = Field(None, description="Welcome message (extracted from display_config)")
    header_title: str | None = Field(None, description="Header title (extracted from display_config)")
    header_subtitle: str | None = Field(None, description="Header subtitle (extracted from display_config)")
    avatar_url: str | None = Field(None, description="Bot avatar URL (extracted from display_config)")
    placeholder: str | None = Field(None, description="Input placeholder (extracted from display_config)")
    primary_color: str | None = Field(None, description="Primary color (extracted from display_config.colors.header.background)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "bot_id": "550e8400-e29b-41d4-a716-446655440000",
                "bot_name": "Support Bot",
                "bot_key": "bot_550e8400",
                "language": "vi",
                "display_config": {
                    "position": {
                        "horizontal": "right",
                        "vertical": "bottom",
                        "offset_x": 20,
                        "offset_y": 20
                    },
                    "size": {
                        "width": 400,
                        "height": 600,
                        "mobile_width": 360,
                        "mobile_height": 500
                    },
                    "colors": {
                        "header": {
                            "background": "#4F46E5",
                            "text": "#FFFFFF",
                            "subtitle_text": "#E0E7FF",
                            "border": "#4338CA",
                            "icon": "#FFFFFF"
                        },
                        "background": {
                            "main": "#FFFFFF",
                            "chat_area": "#F9FAFB",
                            "message_container": "#FFFFFF"
                        },
                        "message": {
                            "user_background": "#4F46E5",
                            "user_text": "#FFFFFF",
                            "bot_background": "#F3F4F6",
                            "bot_text": "#1F2937",
                            "timestamp": "#6B7280",
                            "link": "#4F46E5",
                            "code_background": "#1F2937",
                            "code_text": "#F9FAFB"
                        },
                        "input": {
                            "background": "#FFFFFF",
                            "text": "#1F2937",
                            "placeholder": "#9CA3AF",
                            "border": "#E5E7EB",
                            "border_focus": "#4F46E5",
                            "icon": "#6B7280"
                        },
                        "button": {
                            "primary_background": "#4F46E5",
                            "primary_text": "#FFFFFF",
                            "primary_hover": "#4338CA",
                            "secondary_background": "#F3F4F6",
                            "secondary_text": "#1F2937",
                            "secondary_hover": "#E5E7EB",
                            "launcher_background": "#4F46E5",
                            "launcher_icon": "#FFFFFF",
                            "send_button": "#4F46E5",
                            "send_button_disabled": "#D1D5DB"
                        },
                        "scrollbar": {
                            "thumb": "#D1D5DB",
                            "thumb_hover": "#9CA3AF",
                            "track": "#F3F4F6"
                        },
                        "error": "#EF4444",
                        "success": "#10B981",
                        "warning": "#F59E0B",
                        "info": "#3B82F6",
                        "divider": "#E5E7EB",
                        "shadow": "rgba(0, 0, 0, 0.1)"
                    },
                    "button": {
                        "icon": "💬",
                        "text": "Chat with us",
                        "size": 60,
                        "show_notification_badge": True
                    },
                    "header": {
                        "title": "Chat with us",
                        "subtitle": "We typically reply in minutes",
                        "avatar_url": None,
                        "show_online_status": True,
                        "show_close_button": True
                    },
                    "welcome_message": {
                        "enabled": True,
                        "message": "Hi! How can I help you today?",
                        "quick_replies": ["Pricing", "Features", "Support"]
                    },
                    "input": {
                        "placeholder": "Type your message...",
                        "max_length": 1000,
                        "enable_file_upload": False,
                        "allowed_file_types": [".pdf", ".txt", ".doc", ".docx"],
                        "max_file_size_mb": 10,
                        "show_emoji_picker": True
                    },
                    "behavior": {
                        "auto_open": False,
                        "auto_open_delay": 3,
                        "minimize_on_outside_click": True,
                        "show_typing_indicator": True,
                        "enable_sound": True,
                        "persist_conversation": True
                    },
                    "branding": {
                        "show_powered_by": True,
                        "company_name": "Acme Inc.",
                        "company_logo_url": "https://example.com/logo.png",
                        "privacy_policy_url": "https://example.com/privacy",
                        "terms_url": "https://example.com/terms"
                    },
                    "custom_css": ".widget-header { border-radius: 10px; }",
                    "language": "en",
                    "timezone": "UTC"
                },
                "welcome_message": "Hi! How can I help you today?",
                "header_title": "Chat with us",
                "header_subtitle": "We typically reply in minutes",
                "avatar_url": None,
                "placeholder": "Type your message...",
                "primary_color": "#4F46E5"
            }
        }
    )


class WidgetChatRequest(BaseModel):
    """Request schema for widget chat."""
    session_token: str = Field(..., description="Session token from init")
    message: str = Field(..., description="User message")
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list,
        max_length=20,
        description="Previous conversation turns (role + content)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_token": "sess_abc123xyz",
                "message": "What are your hours?",
                "conversation_history": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi! How can I help you?"}
                ]
            }
        }
    )


class WidgetChatResponse(BaseModel):
    """Response schema for widget chat."""
    task_id: str = Field(..., description="Chat task ID")
    status: str = Field(..., description="Task status")
    stream_url: str = Field(..., description="SSE stream URL")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "task_abc123",
                "status": "queued",
                "stream_url": "/api/v1/chat/stream/task_abc123"
            }
        }
    )

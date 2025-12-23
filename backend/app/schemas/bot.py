from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from uuid import UUID

from app.common.enums import BotStatus


# ============================================================================
# Display Configuration Schemas (Widget UI Customization)
# ============================================================================

class WidgetPosition(BaseModel):
    """Widget position configuration."""
    horizontal: Literal["left", "right"] = Field(default="right", description="Horizontal position")
    vertical: Literal["top", "bottom"] = Field(default="bottom", description="Vertical position")
    offset_x: int = Field(default=20, ge=0, le=200, description="Horizontal offset in pixels")
    offset_y: int = Field(default=20, ge=0, le=200, description="Vertical offset in pixels")


class WidgetSize(BaseModel):
    """Widget size configuration."""
    width: int = Field(default=400, ge=300, le=800, description="Widget width in pixels")
    height: int = Field(default=600, ge=400, le=900, description="Widget height in pixels")
    mobile_width: Optional[int] = Field(default=None, ge=280, le=500, description="Width on mobile devices")
    mobile_height: Optional[int] = Field(default=None, ge=400, le=700, description="Height on mobile devices")


class HeaderColors(BaseModel):
    """Header color configuration."""
    background: str = Field(default="#4F46E5", description="Header background color (hex)")
    text: str = Field(default="#FFFFFF", description="Header text color (hex)")
    subtitle_text: str = Field(default="#E0E7FF", description="Header subtitle text color (hex)")
    border: Optional[str] = Field(default=None, description="Header border color (hex)")
    icon: str = Field(default="#FFFFFF", description="Header icon color (hex)")
    
    @field_validator("background", "text", "subtitle_text", "border", "icon")
    @classmethod
    def validate_hex_color(cls, v: Optional[str]) -> Optional[str]:
        """Validate hex color format."""
        if v is None:
            return v
        if not v.startswith("#") or len(v) not in [4, 7]:
            raise ValueError("Color must be a valid hex code (e.g., #FFF or #FFFFFF)")
        return v.upper()


class BackgroundColors(BaseModel):
    """Background and container color configuration."""
    main: str = Field(default="#FFFFFF", description="Main widget background color (hex)")
    chat_area: str = Field(default="#F9FAFB", description="Chat area background color (hex)")
    message_container: str = Field(default="#FFFFFF", description="Message container background (hex)")
    
    @field_validator("main", "chat_area", "message_container")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        """Validate hex color format."""
        if not v.startswith("#") or len(v) not in [4, 7]:
            raise ValueError("Color must be a valid hex code (e.g., #FFF or #FFFFFF)")
        return v.upper()


class MessageColors(BaseModel):
    """Message bubble color configuration."""
    user_background: str = Field(default="#4F46E5", description="User message background (hex)")
    user_text: str = Field(default="#FFFFFF", description="User message text color (hex)")
    bot_background: str = Field(default="#F3F4F6", description="Bot message background (hex)")
    bot_text: str = Field(default="#1F2937", description="Bot message text color (hex)")
    timestamp: str = Field(default="#6B7280", description="Timestamp text color (hex)")
    link: str = Field(default="#4F46E5", description="Link color in messages (hex)")
    code_background: str = Field(default="#1F2937", description="Code block background (hex)")
    code_text: str = Field(default="#F9FAFB", description="Code block text color (hex)")
    
    @field_validator("user_background", "user_text", "bot_background", "bot_text", "timestamp", "link", "code_background", "code_text")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        """Validate hex color format."""
        if not v.startswith("#") or len(v) not in [4, 7]:
            raise ValueError("Color must be a valid hex code (e.g., #FFF or #FFFFFF)")
        return v.upper()


class InputColors(BaseModel):
    """Input field color configuration."""
    background: str = Field(default="#FFFFFF", description="Input field background (hex)")
    text: str = Field(default="#1F2937", description="Input text color (hex)")
    placeholder: str = Field(default="#9CA3AF", description="Placeholder text color (hex)")
    border: str = Field(default="#E5E7EB", description="Input border color (hex)")
    border_focus: str = Field(default="#4F46E5", description="Input border color when focused (hex)")
    icon: str = Field(default="#6B7280", description="Input area icon color (hex)")
    
    @field_validator("background", "text", "placeholder", "border", "border_focus", "icon")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        """Validate hex color format."""
        if not v.startswith("#") or len(v) not in [4, 7]:
            raise ValueError("Color must be a valid hex code (e.g., #FFF or #FFFFFF)")
        return v.upper()


class ButtonColors(BaseModel):
    """Button and interactive element color configuration."""
    primary_background: str = Field(default="#4F46E5", description="Primary button background (hex)")
    primary_text: str = Field(default="#FFFFFF", description="Primary button text color (hex)")
    primary_hover: str = Field(default="#4338CA", description="Primary button hover background (hex)")
    secondary_background: str = Field(default="#F3F4F6", description="Secondary button background (hex)")
    secondary_text: str = Field(default="#1F2937", description="Secondary button text color (hex)")
    secondary_hover: str = Field(default="#E5E7EB", description="Secondary button hover background (hex)")
    launcher_background: str = Field(default="#4F46E5", description="Launcher button background (hex)")
    launcher_icon: str = Field(default="#FFFFFF", description="Launcher button icon color (hex)")
    send_button: str = Field(default="#4F46E5", description="Send button color (hex)")
    send_button_disabled: str = Field(default="#D1D5DB", description="Send button disabled color (hex)")
    
    @field_validator("primary_background", "primary_text", "primary_hover", "secondary_background", "secondary_text", "secondary_hover", "launcher_background", "launcher_icon", "send_button", "send_button_disabled")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        """Validate hex color format."""
        if not v.startswith("#") or len(v) not in [4, 7]:
            raise ValueError("Color must be a valid hex code (e.g., #FFF or #FFFFFF)")
        return v.upper()


class ScrollbarColors(BaseModel):
    """Scrollbar color configuration."""
    thumb: str = Field(default="#D1D5DB", description="Scrollbar thumb color (hex)")
    thumb_hover: str = Field(default="#9CA3AF", description="Scrollbar thumb hover color (hex)")
    track: str = Field(default="#F3F4F6", description="Scrollbar track color (hex)")
    
    @field_validator("thumb", "thumb_hover", "track")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        """Validate hex color format."""
        if not v.startswith("#") or len(v) not in [4, 7]:
            raise ValueError("Color must be a valid hex code (e.g., #FFF or #FFFFFF)")
        return v.upper()


class WidgetColors(BaseModel):
    """Comprehensive widget color scheme with detailed categorization."""
    header: HeaderColors = Field(default_factory=HeaderColors, description="Header colors")
    background: BackgroundColors = Field(default_factory=BackgroundColors, description="Background colors")
    message: MessageColors = Field(default_factory=MessageColors, description="Message bubble colors")
    input: InputColors = Field(default_factory=InputColors, description="Input field colors")
    button: ButtonColors = Field(default_factory=ButtonColors, description="Button colors")
    scrollbar: ScrollbarColors = Field(default_factory=ScrollbarColors, description="Scrollbar colors")
    
    # Additional accent colors
    error: str = Field(default="#EF4444", description="Error message color (hex)")
    success: str = Field(default="#10B981", description="Success message color (hex)")
    warning: str = Field(default="#F59E0B", description="Warning message color (hex)")
    info: str = Field(default="#3B82F6", description="Info message color (hex)")
    divider: str = Field(default="#E5E7EB", description="Divider line color (hex)")
    shadow: str = Field(default="rgba(0, 0, 0, 0.1)", description="Shadow color (rgba or hex)")
    
    @field_validator("error", "success", "warning", "info", "divider")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        """Validate hex color format."""
        if not v.startswith("#") or len(v) not in [4, 7]:
            raise ValueError("Color must be a valid hex code (e.g., #FFF or #FFFFFF)")
        return v.upper()


class WidgetButton(BaseModel):
    """Widget launcher button configuration."""
    icon: Optional[str] = Field(default=None, description="Button icon URL or emoji")
    text: Optional[str] = Field(default=None, max_length=50, description="Button text (shown on hover)")
    size: int = Field(default=60, ge=40, le=100, description="Button size in pixels")
    show_notification_badge: bool = Field(default=True, description="Show notification badge")


class WidgetHeader(BaseModel):
    """Widget header configuration."""
    title: str = Field(default="Chat with us", max_length=100, description="Header title")
    subtitle: Optional[str] = Field(default=None, max_length=200, description="Header subtitle")
    avatar_url: Optional[str] = Field(default=None, description="Bot avatar URL")
    show_online_status: bool = Field(default=True, description="Show online/offline indicator")
    show_close_button: bool = Field(default=True, description="Show close button")


class WidgetWelcomeMessage(BaseModel):
    """Welcome message configuration."""
    enabled: bool = Field(default=True, description="Show welcome message")
    message: str = Field(
        default="Hi! How can I help you today?",
        max_length=500,
        description="Welcome message text"
    )
    quick_replies: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Quick reply buttons (max 5)"
    )
    
    @field_validator("quick_replies")
    @classmethod
    def validate_quick_replies(cls, v: List[str]) -> List[str]:
        """Validate quick replies."""
        if len(v) > 5:
            raise ValueError("Maximum 5 quick replies allowed")
        return [reply[:100] for reply in v]  


class WidgetInput(BaseModel):
    """Input field configuration."""
    placeholder: str = Field(default="Type your message...", max_length=100)
    max_length: int = Field(default=1000, ge=100, le=5000, description="Max input length")
    enable_file_upload: bool = Field(default=False, description="Allow file uploads")
    allowed_file_types: List[str] = Field(
        default_factory=lambda: [".pdf", ".txt", ".doc", ".docx"],
        description="Allowed file extensions"
    )
    max_file_size_mb: int = Field(default=10, ge=1, le=50, description="Max file size in MB")
    show_emoji_picker: bool = Field(default=True, description="Show emoji picker button")


class WidgetBehavior(BaseModel):
    """Widget behavior settings."""
    auto_open: bool = Field(default=False, description="Auto-open widget on page load")
    auto_open_delay: int = Field(default=3, ge=0, le=60, description="Delay before auto-open (seconds)")
    minimize_on_outside_click: bool = Field(default=True, description="Minimize when clicking outside")
    show_typing_indicator: bool = Field(default=True, description="Show typing indicator")
    enable_sound: bool = Field(default=True, description="Enable notification sounds")
    persist_conversation: bool = Field(default=True, description="Save conversation in localStorage")


class WidgetBranding(BaseModel):
    """Widget branding configuration."""
    show_powered_by: bool = Field(default=True, description="Show 'Powered by' branding")
    company_name: Optional[str] = Field(default=None, max_length=100, description="Company name")
    company_logo_url: Optional[str] = Field(default=None, description="Company logo URL")
    privacy_policy_url: Optional[str] = Field(default=None, description="Privacy policy URL")
    terms_url: Optional[str] = Field(default=None, description="Terms of service URL")


class DisplayConfig(BaseModel):
    """
    Complete widget display configuration.
    This is the structured version of the bot's display_config JSONB field.
    """
    position: WidgetPosition = Field(default_factory=WidgetPosition)
    size: WidgetSize = Field(default_factory=WidgetSize)
    colors: WidgetColors = Field(default_factory=WidgetColors)
    button: WidgetButton = Field(default_factory=WidgetButton)
    header: WidgetHeader = Field(default_factory=WidgetHeader)
    welcome_message: WidgetWelcomeMessage = Field(default_factory=WidgetWelcomeMessage)
    input: WidgetInput = Field(default_factory=WidgetInput)
    behavior: WidgetBehavior = Field(default_factory=WidgetBehavior)
    branding: WidgetBranding = Field(default_factory=WidgetBranding)
    
    # Custom CSS
    custom_css: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Custom CSS for advanced styling"
    )
    
    # Language and localization
    language: str = Field(default="en", description="Widget language code")
    timezone: str = Field(default="UTC", description="Timezone for timestamps")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
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
                    "title": "Chat with Support",
                    "subtitle": "We typically reply in minutes",
                    "avatar_url": "https://example.com/avatar.png",
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
            }
        }
    )


class ApiKeyItem(BaseModel):
    """Single API key in pool"""
    key: str = Field(..., min_length=1, description="API key (will be encrypted)")
    name: str = Field(default="default", description="Key name for identification")
    active: bool = Field(default=True, description="Whether key is active")


class ProviderConfigCreate(BaseModel):
    """
    Schema for creating/updating provider configuration.
    
    Permissions:
    - Only ADMIN and ROOT can configure provider for bots
    - Only ROOT can modify api_base_url of providers
    
    API keys will be encrypted before storage.
    """
    provider_id: UUID = Field(..., description="Provider ID (OpenAI, Gemini, Ollama)")
    model_id: UUID = Field(..., description="Model ID from the selected provider")
    api_keys: List[ApiKeyItem] = Field(..., min_items=1, description="API keys pool (at least 1 required)")
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional configuration (temperature, max_tokens, etc.)"
    )


class ProviderConfigUpdate(BaseModel):
    """Schema for updating provider configuration."""
    provider_id: Optional[UUID] = None
    model_id: Optional[UUID] = None
    api_keys: Optional[List[ApiKeyItem]] = Field(None, min_items=1, description="Update API keys pool")
    is_active: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


class ApiKeyEncrypted(BaseModel):
    """Encrypted API key in response"""
    key: str = Field(..., description="Encrypted API key")
    name: str = Field(..., description="Key name")
    active: bool = Field(..., description="Whether key is active")


class ProviderConfigResponse(BaseModel):
    """
    Schema for provider configuration response.
    
    Note: API keys are encrypted in response.
    Use POST /bots/{bot_id}/reveal-api-key to decrypt a specific key.
    """
    id: UUID
    bot_id: UUID
    provider_id: UUID
    model_id: UUID
    is_active: bool
    config: Dict[str, Any]
    api_keys: List[ApiKeyEncrypted] = Field(default=[], description="Encrypted API keys pool")
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class RevealKeyRequest(BaseModel):
    """Request to reveal specific API key"""
    encrypted_key: str = Field(..., description="Encrypted key from provider config response")


class RevealKeyResponse(BaseModel):
    """Response with decrypted API key"""
    key: str = Field(..., description="Decrypted plain text API key")
    name: str = Field(..., description="Key name")
    active: bool = Field(..., description="Whether key is active")


# ============================================================================
# Bot Schemas
# ============================================================================

class BotBase(BaseModel):
    """Base bot schema."""
    name: str = Field(..., min_length=1, max_length=255, description="Bot name")
    language: Optional[str] = Field(None, max_length=50, description="Language code (e.g., 'en', 'vi')")
    desc: Optional[str] = Field(None, description="Bot description (e.g., 'You are customer support bot for...')")
    assessment_questions: List[str] = Field(default_factory=list, description="Assessment questions for chat history evaluation")


class BotCreate(BotBase):
    """
    Schema for creating a new bot.
    bot_key will be auto-generated as: bot_{uuid}
    
    origin: The allowed origin (website that can embed the bot widget).
    sitemap_urls: Optional list of specific URLs to crawl.
                  If empty/None → BFS crawl entire origin domain
                  If provided → crawl only these specific URLs
    
    Will trigger automatic web crawling for the origin.
    """
    origin: str = Field(..., description="The allowed origin for CORS (e.g., https://example.com)")
    sitemap_urls: List[str] = Field(
        default_factory=list,
        max_length=100,
        description="Optional sitemap URLs. If empty, will crawl entire domain."
    )
    
    @field_validator("origin")
    @classmethod
    def normalize_origin(cls, v: str) -> str:
        """Normalize origin URL by removing trailing slash."""
        if not v:
            raise ValueError("Origin cannot be empty")
        if not v.startswith(("http://", "https://")):
            raise ValueError("Origin must start with http:// or https://")
        return v.rstrip("/")
    
    @field_validator("sitemap_urls")
    @classmethod
    def validate_sitemap_urls(cls, v: List[str]) -> List[str]:
        """Validate sitemap URLs."""
        if len(v) > 100:
            raise ValueError("Maximum 100 sitemap URLs allowed")
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid URL: {url}")
        return v


class BotUpdate(BaseModel):
    """
    Schema for updating bot.
    
    All fields are optional - only send fields you want to update.
    To activate bot, ensure it has a provider_config set.
    
    Note: Use PUT /bots/{bot_id}/display-config to update display configuration separately.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Bot name (leave empty to keep current)")
    language: Optional[str] = Field(None, max_length=50, description="Language code (leave empty to keep current)")
    status: Optional[BotStatus] = Field(None, description="Bot status (leave empty to keep current)")
    desc: Optional[str] = Field(None, description="Bot description")
    assessment_questions: Optional[List[str]] = Field(None, description="Assessment questions")
    
    provider_config: Optional[ProviderConfigCreate] = Field(
        None,
        description="LLM provider configuration (OpenAI, Gemini, Ollama). Required to activate bot."
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "provider_config": {
                    "provider_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "model_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "api_keys": [
                        {
                            "key": "sk-proj-xxxxxxxxxxxxx",
                            "name": "Production Key",
                            "active": True
                        }
                    ],
                    "config": {
                        "temperature": 0.7,
                        "max_tokens": 2000
                    }
                }
            }
        }
    )


class BotResponse(BaseModel):
    """
    Schema for bot response with full origin details.
    
    Includes origin URL and sitemap_urls from AllowedOrigin relationship.
    """
    id: UUID
    name: str
    bot_key: str
    language: Optional[str] = None
    status: BotStatus
    display_config: DisplayConfig  
    collection_name: str 
    bucket_name: str
    desc: Optional[str] = None
    assessment_questions: List[str] = Field(default_factory=list)
    
    origin: Optional[str] = None
    sitemap_urls: List[str] = Field(default_factory=list, description="List of sitemap URLs if configured")
    
    provider_config: Optional[ProviderConfigResponse] = Field(None, description="Provider configuration (LLM settings)")
    
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class BotProcessing(BaseModel):
    """
    Schema for bot creation response with crawl task tracking.
    
    Used when creating a new bot to provide task_id for progress monitoring via SSE.
    """
    bot: BotResponse = Field(..., description="Created bot details")
    task_id: str = Field(..., description="Crawl task ID for progress tracking")
    sse_endpoint: str = Field(..., description="SSE endpoint URL to monitor crawl progress")
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Allowed Origin Schemas
# ============================================================================

class AllowedOriginCreate(BaseModel):
    """
    Schema for adding allowed origin with optional sitemap URLs.
    
    If sitemap_urls provided and not empty → crawl specific URLs
    If sitemap_urls empty or None → BFS crawl entire origin domain
    """
    origin: str = Field(..., min_length=1, max_length=255, description="Domain origin (e.g., https://example.com)")
    sitemap_urls: List[str] = Field(
        default_factory=list,
        max_length=100,
        description="Optional list of specific URLs to crawl. If empty, will BFS crawl entire domain."
    )
    
    @field_validator("origin")
    @classmethod
    def normalize_origin(cls, v: str) -> str:
        """Normalize origin URL by removing trailing slash."""
        if not v:
            raise ValueError("Origin cannot be empty")
        if not v.startswith(("http://", "https://")):
            raise ValueError("Origin must start with http:// or https://")
        return v.rstrip("/")
    
    @field_validator("sitemap_urls")
    @classmethod
    def validate_sitemap_urls(cls, v: List[str]) -> List[str]:
        """Validate sitemap URLs."""
        if len(v) > 100:
            raise ValueError("Maximum 100 sitemap URLs allowed")
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid URL: {url}")
        return v


class AllowedOriginUpdate(BaseModel):
    """Schema for updating allowed origin."""
    origin: Optional[str] = Field(None, min_length=1, max_length=255)
    sitemap_urls: Optional[List[str]] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    
    @field_validator("origin")
    @classmethod
    def normalize_origin(cls, v: Optional[str]) -> Optional[str]:
        """Normalize origin URL by removing trailing slash."""
        if v is None:
            return None
        if not v:
            raise ValueError("Origin cannot be empty")
        if not v.startswith(("http://", "https://")):
            raise ValueError("Origin must start with http:// or https://")
        return v.rstrip("/")
    
    @field_validator("sitemap_urls")
    @classmethod
    def validate_sitemap_urls(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate sitemap URLs."""
        if v is None:
            return None
        if len(v) > 100:
            raise ValueError("Maximum 100 sitemap URLs allowed")
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid URL: {url}")
        return v


class AllowedOriginResponse(BaseModel):
    """Schema for allowed origin response."""
    id: UUID
    bot_id: UUID
    origin: str
    sitemap_urls: List[str] 
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class RecrawlResponse(BaseModel):
    """Schema for recrawl operation response."""
    message: str
    job_id: str
    deleted_documents: int
    origin: str
    sse_endpoint: str


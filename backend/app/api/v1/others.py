"""
Other/Common API endpoints for shared resources.
"""
from fastapi import APIRouter

from app.schemas.common import RolesListResponse, LanguagesListResponse, RoleResponse, LanguageResponse
from app.models.user import UserRole
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/roles", response_model=RolesListResponse)
async def get_available_roles():
    """
    Get list of available user roles.
    
    Public endpoint - no authentication required.
    Used by frontend for role selection in invite forms.
    """
    roles = [
        RoleResponse(
            value=UserRole.ROOT.value,
            label="Root",
            description="System administrator with full access (only one root user allowed)"
        ),
        RoleResponse(
            value=UserRole.ADMIN.value,
            label="Admin",
            description="Can manage users, bots, and content"
        ),
        RoleResponse(
            value=UserRole.MEMBER.value,
            label="Member",
            description="Can view and interact with bots"
        )
    ]
    
    return RolesListResponse(roles=roles)


@router.get("/languages", response_model=LanguagesListResponse)
async def get_supported_languages():
    """
    Get list of supported languages.
    
    Public endpoint - no authentication required.
    Used by frontend for language selection.
    """
    languages = [
        LanguageResponse(
            code="en",
            name="English",
            native_name="English"
        ),
        LanguageResponse(
            code="vi",
            name="Vietnamese",
            native_name="Tiếng Việt"
        ),
        LanguageResponse(
            code="ja",
            name="Japanese",
            native_name="日本語"
        ),
        LanguageResponse(
            code="kr",
            name="Korean",
            native_name="한국어"
        )
    ]
    
    return LanguagesListResponse(languages=languages)


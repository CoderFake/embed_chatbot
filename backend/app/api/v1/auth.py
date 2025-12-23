from fastapi import APIRouter, Depends, HTTPException, status, Header, Request, Form
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from typing import Optional

from app.core.database import get_db, get_redis
from app.core.dependencies import get_current_user, Member
from app.common.types import CurrentUser
from app.services.auth import AuthService
from app.schemas.user import (
    UserLogin, 
    TokenResponseExtended, 
    PasswordChange,
    ForgotPasswordRequest,
    ResetPasswordRequest
)
from app.config.settings import settings
from app.common.constants import ResponseMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/login", response_model=TokenResponseExtended)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Login endpoint - authenticate user and return JWT tokens.
    
    - **email**: User email address
    - **password**: User password
    
    Returns access_token, refresh_token, and force_password_change flag.
    
    If force_password_change is True, frontend must redirect to change password screen.
    """
    auth_service = AuthService(db, redis)
    
    access_token, refresh_token, user, force_password_change = await auth_service.login(
        email=credentials.email,
        password=credentials.password
    )
    
    return TokenResponseExtended(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        force_password_change=force_password_change
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    authorization: Optional[str] = Header(None),
    refresh_token: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Logout endpoint - blacklist access and refresh tokens.
    
    Requires authentication. Provide refresh_token in request body to also blacklist it.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    access_token = authorization.replace("Bearer ", "")
    
    auth_service = AuthService(db, redis)
    await auth_service.logout(access_token, refresh_token)
    
    logger.info(f"User logged out: {current_user.email}")


@router.post("/refresh", response_model=dict)
async def refresh_token(
    refresh_token: str = Form(...),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Refresh access token using refresh token (rotating refresh token pattern).

    - **refresh_token**: Valid refresh token (form field)

    Returns new access_token AND new refresh_token.
    Old refresh_token is blacklisted.
    """
    auth_service = AuthService(db, redis)

    new_access_token, new_refresh_token = await auth_service.refresh_access_token(refresh_token)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    password_data: PasswordChange,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Change current user's password.
    
    Requires authentication.
    - **old_password**: Current password
    - **new_password**: New password (min 8 characters)
    
    A notification email will be sent to the user's email address.
    """
    auth_service = AuthService(db, redis)
    
    await auth_service.change_password(
        user_id=current_user.user_id,
        old_password=password_data.old_password,
        new_password=password_data.new_password,
        request=request
    )
    
    logger.info(f"Password changed for user: {current_user.email}")


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Request password reset email.
    
    - **email**: User email address
    
    An email with a password reset link will be sent if the email exists.
    For security, always returns success even if email doesn't exist.
    """
    auth_service = AuthService(db, redis)
    
    await auth_service.request_password_reset(
        email=data.email,
        request=request
    )
    
    return {"message": ResponseMessage.RESET_EMAIL_SENT}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    data: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Reset password using reset token from email.
    
    - **token**: Password reset token (from email link hash fragment)
    - **new_password**: New password (min 8 characters)
    
    A confirmation email will be sent after successful password reset.
    """
    auth_service = AuthService(db, redis)
    
    await auth_service.reset_password(
        reset_token=data.token,
        new_password=data.new_password,
        request=request
    )
    
    logger.info("Password reset successfully")


@router.get("/me", response_model=dict)
async def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Get current authenticated user information.
    
    Requires authentication.
    """
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role,
        "full_name": current_user.full_name
    }


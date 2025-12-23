from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db, get_redis
from app.core.dependencies import Admin
from app.common.types import CurrentUser
from app.services.invite import InviteService
from app.schemas.invite import InviteCreate, InviteResponse, BulkInviteResponse
from app.models.user import InviteStatus, UserRole
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("", response_model=BulkInviteResponse, dependencies=[Depends(Admin)])
async def create_invites(
    invite_data: InviteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Create bulk invites.
    
    **Required role:** root, admin
    
    **Permission rules:**
    - Root can invite: Root, Admin, Member
    - Admin can invite: Admin, Member (cannot invite Root)
    - Member cannot invite anyone
    
    **Constraints:**
    - Maximum 50 invites per request
    - Only one Root user allowed in the system
    - Admin can invite Admin but cannot delete Admin
    
    Each invite will:
    1. Create user account with random password
    2. Send email with login credentials
    3. User must login and change password on first login
    """
    invite_service = InviteService(db, redis)
    
    results = []
    created = 0
    failed = 0
    
    for invite_item in invite_data.invites:
        try:
            if current_user.role == UserRole.ADMIN.value and invite_item.role == UserRole.ROOT:
                results.append({
                    "email": invite_item.email,
                    "status": "failed",
                    "message": "Admin cannot invite Root users"
                })
                failed += 1
                continue
            
            invite = await invite_service.create_invite(
                email=invite_item.email,
                role=invite_item.role.value,
                invited_by_id=current_user.user_id,
                request=request
            )
            
            results.append({
                "email": invite_item.email,
                "status": "success",
                "invite_id": str(invite.id)
            })
            created += 1
            
            logger.info(f"Invite created for {invite_item.email} by {current_user.email}")
            
        except HTTPException as e:
            results.append({
                "email": invite_item.email,
                "status": "failed",
                "message": e.detail
            })
            failed += 1
        except Exception as e:
            results.append({
                "email": invite_item.email,
                "status": "failed",
                "message": str(e)
            })
            failed += 1
    
    await db.commit()
    
    logger.info(f"Bulk invite: {created} created, {failed} failed by {current_user.email}")
    
    return BulkInviteResponse(
        total=len(invite_data.invites),
        created=created,
        failed=failed,
        results=results
    )


@router.get("", response_model=List[InviteResponse], dependencies=[Depends(Admin)])
async def list_invites(
    status: Optional[InviteStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: CurrentUser = Depends(Admin),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    List invites created by current user with optional filtering.
    
    **Required role:** root, admin
    
    - **status**: Optional filter by status (pending, accepted, expired, revoked)
    - **skip**: Number of records to skip
    - **limit**: Maximum number of records to return
    
    **Note:** Only shows invites created by the logged-in user.
    """
    invite_service = InviteService(db, redis)
    
    invites = await invite_service.get_all(
        status=status,
        skip=skip,
        limit=limit,
        invited_by_id=current_user.user_id
    )
    
    return invites


@router.get("/{invite_id}", response_model=InviteResponse, dependencies=[Depends(Admin)])
async def get_invite(
    invite_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Get invite details by ID.
    
    **Required role:** root, admin
    """
    invite_service = InviteService(db, redis)
    
    invite = await invite_service.get_by_id(str(invite_id))
    
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found"
        )
    
    return invite


@router.post("/{invite_id}/revoke", response_model=InviteResponse, dependencies=[Depends(Admin)])
async def revoke_invite(
    invite_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Revoke pending invite.
    
    **Required role:** root, admin
    """
    invite_service = InviteService(db, redis)
    
    invite = await invite_service.revoke_invite(str(invite_id))
    
    await db.commit()
    
    logger.info(f"Invite revoked: {invite.email} by {current_user.email}")
    
    return invite


@router.post("/{invite_id}/resend", response_model=InviteResponse, dependencies=[Depends(Admin)])
async def resend_invite(
    invite_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Resend invite email and extend expiration.
    
    **Required role:** root, admin
    
    The invite email will be resent with an updated expiration date.
    """
    invite_service = InviteService(db, redis)
    
    invite = await invite_service.resend_invite(
        invite_id=str(invite_id),
        request=request
    )
    
    await db.commit()
    
    logger.info(f"Invite resent: {invite.email} by {current_user.email}")
    
    return invite


@router.post("/confirm", response_model=dict)
async def confirm_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Confirm invite token validity (public endpoint).
    
    User account is already created when invite is sent.
    User should login with credentials from email.
    On first login, user will be forced to change password.
    
    - **token**: Invite token from email link
    """
    invite_service = InviteService(db, redis)
    
    result = await invite_service.confirm_invite(token=token)
    
    await db.commit()
    
    logger.info(f"Invite confirmed: {result['email']}")
    
    return result


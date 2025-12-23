from typing import Optional
from app.common.enums import UserRole


class CurrentUser:
    """
    Current authenticated user data.
    """
    def __init__(
        self,
        user_id: str,
        email: str,
        role: str,
        full_name: Optional[str] = None
    ):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.full_name = full_name
    
    def is_root(self) -> bool:
        """Check if user has root role."""
        return self.role == UserRole.ROOT.value
    
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == UserRole.ADMIN.value
    
    def is_member(self) -> bool:
        """Check if user has member role."""
        return self.role == UserRole.MEMBER.value
    
    def has_role(self, *roles: str) -> bool:
        """Check if user has any of the specified roles."""
        return self.role in roles
    
    def __repr__(self) -> str:
        return f"<CurrentUser(id={self.user_id}, email={self.email}, role={self.role})>"


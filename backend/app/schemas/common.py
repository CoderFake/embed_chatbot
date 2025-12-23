"""
Common schemas for shared data across the application.
"""
from pydantic import BaseModel
from typing import List


class BaseRequest(BaseModel):
    """Base request schema"""
    pass


class BaseResponse(BaseModel):
    """Base response schema"""
    pass


class RoleResponse(BaseModel):
    """Available user roles"""
    value: str
    label: str
    description: str


class LanguageResponse(BaseModel):
    """Supported languages"""
    code: str
    name: str
    native_name: str


class RolesListResponse(BaseModel):
    """List of available roles"""
    roles: List[RoleResponse]


class LanguagesListResponse(BaseModel):
    """List of supported languages"""
    languages: List[LanguageResponse]


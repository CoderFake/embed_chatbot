from fastapi import HTTPException, Form, UploadFile, File
from typing import Optional, Any, Union
from pydantic import BaseModel, Field, field_validator
from fastapi import Request

from app.schemas.bot import DisplayConfig
from app.utils.image import detect_image_type
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaMode, JsonSchemaValue
from pydantic_core import CoreSchema
import io
import json


class SelfContaindGenerateSchema(GenerateJsonSchema):
    """
    Generate a JSON schema for a nested structure of Pydantic BaseModel.
    """
    def generate(self, schema: CoreSchema, mode: JsonSchemaMode = 'validation') -> JsonSchemaValue:
        js = super().generate(schema, mode)

        if '$defs' not in js:
            return js

        defs = js.pop('$defs')

        prefix = '#/$defs/'

        def walk(v: Union[list[Any], dict[str, Any], Any], memo: set[str]) -> Any:
            if isinstance(v, list):
                return [walk(i, memo) for i in v]
            elif isinstance(v, dict):
                if "$ref" in v:
                    key = v["$ref"][len(prefix):]
                    if key in memo:
                        return {}
                    ref = defs[key]
                    memo = set(memo)
                    ref = walk(ref, memo)
                    return ref
                else:
                    return {k: walk(u, memo) for k, u in v.items()}
            else:
                return v

        js = walk(js, set())

        return js # type: ignore



class UpdateDisplayConfigBody(BaseModel):
    """
    Request body for updating display config with file uploads.
    Supports multipart/form-data with optional JSON config and image files.
    """
    config: Optional[DisplayConfig] = Field(None, description="Display configuration (optional)")
    avatar: Optional[bytes] = Field(None, description="Bot avatar image file (optional, max 5MB)")
    logo: Optional[bytes] = Field(None, description="Company logo image file (optional, max 5MB)")

    @field_validator('avatar')
    @classmethod
    def validate_avatar(cls, v: Optional[bytes]) -> Optional[bytes]:
        if v is None:
            return v
        
        # Validate size
        if len(v) > 5 * 1024 * 1024:
            raise ValueError("Avatar file size must not exceed 5MB")
        
        # Validate image type
        img_type = detect_image_type(v)
        if not img_type:
            raise ValueError("Avatar must be a valid image (JPEG, PNG, GIF, or WebP)")
        
        return v
    
    @field_validator('logo')
    @classmethod
    def validate_logo(cls, v: Optional[bytes]) -> Optional[bytes]:
        if v is None:
            return v
        
        # Validate size
        if len(v) > 5 * 1024 * 1024:
            raise ValueError("Logo file size must not exceed 5MB")
        
        # Validate image type
        img_type = detect_image_type(v)
        if not img_type:
            raise ValueError("Logo must be a valid image (JPEG, PNG, GIF, or WebP)")
        
        return v

    @classmethod
    async def from_request(cls, request: Request) -> "UpdateDisplayConfigBody":
        """
        Parse multipart/form-data request.
        
        Expected form fields:
        - config: JSON string of DisplayConfig (optional)
        - avatar: Image file (optional)
        - logo: Image file (optional)
        """
        
        content_type, options = parse_content_type(request.headers.get("Content-Type", ""))
        
        if content_type != "multipart/form-data" or "boundary" not in options:
            raise HTTPException(
                status_code=400,
                detail="Content-Type must be multipart/form-data"
            )
        
        stream = io.BytesIO(await request.body())
        parser = MultipartParser(stream, options["boundary"])
        
        config_part = parser.get("config")
        avatar_part = parser.get("avatar")
        logo_part = parser.get("logo")
        
        config_obj = None
        if config_part:
            try:
                config_raw = config_part.raw
                if isinstance(config_raw, io.BytesIO):
                    config_raw = config_raw.read()
                elif not isinstance(config_raw, bytes):
                    config_raw = bytes(config_raw)
                
                config_dict = json.loads(config_raw.decode('utf-8'))
                config_obj = DisplayConfig(**config_dict)
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid JSON in config field"
                )
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid DisplayConfig: {str(e)}"
                )
        
        avatar_bytes = None
        if avatar_part:
            if isinstance(avatar_part.raw, io.BytesIO):
                avatar_bytes = avatar_part.raw.read()
            elif isinstance(avatar_part.raw, bytes):
                avatar_bytes = avatar_part.raw
            else:
                avatar_bytes = bytes(avatar_part.raw)
        
        logo_bytes = None
        if logo_part:
            if isinstance(logo_part.raw, io.BytesIO):
                logo_bytes = logo_part.raw.read()
            elif isinstance(logo_part.raw, bytes):
                logo_bytes = logo_part.raw
            else:
                logo_bytes = bytes(logo_part.raw)
        
        return UpdateDisplayConfigBody(
            config=config_obj,
            avatar=avatar_bytes,
            logo=logo_bytes,
        )

"""Base schemas for common patterns."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TimestampMixin(BaseModel):
    """Mixin for models with timestamps."""

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ResponseBase(BaseModel):
    """Base response schema."""

    success: bool = True
    message: Optional[str] = None


class ErrorResponse(ResponseBase):
    """Error response schema."""

    success: bool = False
    error_code: Optional[str] = None
    details: Optional[dict] = None


class PaginationParams(BaseModel):
    """Pagination parameters."""

    skip: int = 0
    limit: int = 100

    model_config = ConfigDict(validate_default=True)


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""

    items: list
    total: int
    skip: int
    limit: int
    has_more: bool

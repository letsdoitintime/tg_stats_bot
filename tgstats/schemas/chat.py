"""Chat-related schemas."""

from typing import Optional
from pydantic import Field

from .base import BaseSchema, TimestampMixin


class ChatBase(BaseSchema):
    """Base chat schema."""
    
    chat_id: int
    title: Optional[str] = None
    username: Optional[str] = None
    type: str
    is_forum: Optional[bool] = None


class ChatCreate(ChatBase):
    """Schema for creating a chat."""
    pass


class ChatUpdate(BaseSchema):
    """Schema for updating a chat."""
    
    title: Optional[str] = None
    description: Optional[str] = None


class ChatResponse(ChatBase, TimestampMixin):
    """Schema for chat responses."""
    
    description: Optional[str] = None
    invite_link: Optional[str] = None


class GroupSettingsBase(BaseSchema):
    """Base group settings schema."""
    
    store_text: bool = False
    text_retention_days: int = 90
    metadata_retention_days: int = 365
    timezone: str = "UTC"
    locale: str = "en"
    capture_reactions: bool = False


class GroupSettingsUpdate(BaseSchema):
    """Schema for updating group settings."""
    
    store_text: Optional[bool] = None
    text_retention_days: Optional[int] = Field(None, ge=1, le=3650)
    metadata_retention_days: Optional[int] = Field(None, ge=1, le=3650)
    timezone: Optional[str] = None
    locale: Optional[str] = None
    capture_reactions: Optional[bool] = None


class GroupSettingsResponse(GroupSettingsBase, TimestampMixin):
    """Schema for group settings responses."""
    
    chat_id: int

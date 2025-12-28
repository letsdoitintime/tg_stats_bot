"""Message-related schemas."""

from datetime import datetime
from typing import Optional

from .base import BaseSchema


class MessageBase(BaseSchema):
    """Base message schema."""

    chat_id: int
    msg_id: int
    user_id: Optional[int] = None
    date: datetime
    text_len: int = 0
    urls_cnt: int = 0
    emoji_cnt: int = 0
    has_media: bool = False
    media_type: str = "text"


class MessageCreate(MessageBase):
    """Schema for creating a message."""

    text_raw: Optional[str] = None
    thread_id: Optional[int] = None
    reply_to_msg_id: Optional[int] = None


class MessageResponse(MessageBase):
    """Schema for message responses."""

    edit_date: Optional[datetime] = None
    thread_id: Optional[int] = None
    reply_to_msg_id: Optional[int] = None
    forward_from_id: Optional[int] = None


class MessageStatsQuery(BaseSchema):
    """Query parameters for message statistics."""

    chat_id: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    user_id: Optional[int] = None
    media_type: Optional[str] = None

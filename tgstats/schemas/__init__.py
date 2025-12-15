"""Pydantic schemas for request/response validation."""

from .base import (
    BaseSchema,
    TimestampMixin,
    ResponseBase,
    ErrorResponse,
    PaginationParams,
    PaginatedResponse,
)
from .chat import (
    ChatBase,
    ChatCreate,
    ChatUpdate,
    ChatResponse,
    GroupSettingsBase,
    GroupSettingsUpdate,
    GroupSettingsResponse,
)
from .message import (
    MessageBase,
    MessageCreate,
    MessageResponse,
    MessageStatsQuery,
)

__all__ = [
    # Base
    "BaseSchema",
    "TimestampMixin",
    "ResponseBase",
    "ErrorResponse",
    "PaginationParams",
    "PaginatedResponse",
    # Chat
    "ChatBase",
    "ChatCreate",
    "ChatUpdate",
    "ChatResponse",
    "GroupSettingsBase",
    "GroupSettingsUpdate",
    "GroupSettingsResponse",
    # Message
    "MessageBase",
    "MessageCreate",
    "MessageResponse",
    "MessageStatsQuery",
]

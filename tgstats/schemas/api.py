"""API request/response schemas."""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class ChatSummary(BaseModel):
    """Chat summary response."""
    chat_id: int
    title: Optional[str]
    msg_count_30d: int
    avg_dau_30d: float


class ChatSettings(BaseModel):
    """Chat settings response."""
    chat_id: int
    store_text: bool
    text_retention_days: int
    metadata_retention_days: int
    timezone: str
    locale: str
    capture_reactions: bool


class PeriodSummary(BaseModel):
    """Period summary statistics."""
    total_messages: int
    unique_users: int
    avg_daily_users: float
    new_users: int
    left_users: int
    start_date: str
    end_date: str
    days: int


class TimeseriesPoint(BaseModel):
    """Single point in a timeseries."""
    day: str
    value: int


class UserStats(BaseModel):
    """User statistics."""
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    msg_count: int
    activity_percentage: float
    active_days_ratio: str
    last_message: Optional[str]
    days_since_joined: Optional[int]
    left: bool


class UserStatsResponse(BaseModel):
    """User statistics list response."""
    users: List[UserStats]
    total_messages: int
    period_days: int


class RetentionPreviewRequest(BaseModel):
    """Request for retention preview."""
    chat_id: int = Field(..., description="Chat ID to preview retention for")


class RetentionPreviewResponse(BaseModel):
    """Response for retention preview."""
    chat_id: int
    text_rows_to_delete: int
    metadata_rows_to_delete: int
    oldest_text_date: Optional[datetime]
    oldest_metadata_date: Optional[datetime]
    text_retention_days: int
    metadata_retention_days: int

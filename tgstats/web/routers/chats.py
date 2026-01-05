"""Chat management API endpoints."""

from typing import List

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db import get_session
from ...models import GroupSettings
from ...schemas.api import ChatSettings, ChatSummary
from ..auth import verify_admin_token
from ..query_utils import build_chat_stats_query, check_timescaledb_available

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.get("", response_model=List[ChatSummary])
async def get_chats(
    session: Session = Depends(get_session),
    _token: None = Depends(verify_admin_token),
):
    """
    Get list of known chats with 30-day statistics.

    Returns a list of all chats tracked by the bot, including:
    - Chat ID and title
    - Message count for the last 30 days
    - Average daily active users (DAU) for the last 30 days

    **Example Response:**
    ```json
    [
        {
            "chat_id": -1001234567890,
            "title": "My Awesome Group",
            "msg_count_30d": 1543,
            "avg_dau_30d": 42.5
        }
    ]
    ```

    Returns:
        List of chat summaries with message counts and DAU
    """
    is_timescale = check_timescaledb_available(session)
    query = build_chat_stats_query(is_timescale, days=30)
    result = session.execute(query).fetchall()

    return [
        ChatSummary(
            chat_id=row.chat_id,
            title=row.title or f"Chat {row.chat_id}",
            msg_count_30d=int(row.msg_count_30d),
            avg_dau_30d=float(row.avg_dau_30d),
        )
        for row in result
    ]


@router.get("/{chat_id}/settings", response_model=ChatSettings)
async def get_chat_settings(
    chat_id: int,
    session: Session = Depends(get_session),
    _token: None = Depends(verify_admin_token),
):
    """
    Get settings for a specific chat.

    Args:
        chat_id: Telegram chat ID

    Returns:
        Chat settings including timezone, retention policies, etc.

    Raises:
        HTTPException: 404 if chat settings not found
    """
    settings = session.query(GroupSettings).filter_by(chat_id=chat_id).first()
    if not settings:
        raise HTTPException(
            status_code=404,
            detail=f"Settings not found for chat {chat_id}. Run /setup in the chat first.",
        )

    return ChatSettings(
        chat_id=settings.chat_id,
        store_text=settings.store_text,
        text_retention_days=settings.text_retention_days,
        metadata_retention_days=settings.metadata_retention_days,
        timezone=settings.timezone,
        locale=settings.locale,
        capture_reactions=settings.capture_reactions,
    )

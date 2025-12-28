"""Analytics API endpoints."""

from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from ...db import get_session
from ...schemas.api import (
    PeriodSummary,
    TimeseriesPoint,
    UserStats,
    UserStatsResponse,
    RetentionPreviewResponse,
)
from ..auth import verify_admin_token
from ..query_utils import (
    check_timescaledb_available,
    get_group_tz,
    build_period_summary_query,
    build_timeseries_query,
    build_heatmap_query,
    build_user_stats_query_base,
)
from ..date_utils import parse_period, rotate_heatmap_rows
from ...celery_tasks import retention_preview

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/chats", tags=["analytics"])


@router.get("/{chat_id}/summary", response_model=PeriodSummary)
async def get_chat_summary(
    chat_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    session: Session = Depends(get_session),
    _token: None = Depends(verify_admin_token),
):
    """
    Get summary statistics for a chat over a time period.

    Args:
        chat_id: Telegram chat ID
        from_date: Start date (YYYY-MM-DD), defaults to 30 days ago
        to_date: End date (YYYY-MM-DD), defaults to today

    Returns:
        Summary with total messages, unique users, DAU, joins/leaves
    """
    tz = get_group_tz(chat_id, session)
    start_utc, end_utc, days = parse_period(from_date, to_date, tz)

    # Convert to local time for membership queries
    start_local = start_utc.replace(tzinfo=None)
    end_local = end_utc.replace(tzinfo=None)

    # Get message statistics
    query = build_period_summary_query()
    result = session.execute(
        query, {"chat_id": chat_id, "start_utc": start_utc, "end_utc": end_utc}
    ).fetchone()

    total_messages = int(result.total_messages) if result else 0
    unique_users = int(result.unique_users) if result else 0
    avg_daily_users = float(result.avg_daily_users) if result else 0.0

    # Get membership changes
    new_users_query = text(
        """
        SELECT COUNT(*) as new_users
        FROM memberships
        WHERE chat_id = :chat_id 
        AND joined_at >= :start_local 
        AND joined_at <= :end_local
    """
    )
    new_result = session.execute(
        new_users_query, {"chat_id": chat_id, "start_local": start_local, "end_local": end_local}
    ).fetchone()

    left_users_query = text(
        """
        SELECT COUNT(*) as left_users
        FROM memberships
        WHERE chat_id = :chat_id 
        AND left_at >= :start_local 
        AND left_at <= :end_local
    """
    )
    left_result = session.execute(
        left_users_query, {"chat_id": chat_id, "start_local": start_local, "end_local": end_local}
    ).fetchone()

    new_users = int(new_result.new_users) if new_result else 0
    left_users = int(left_result.left_users) if left_result else 0

    return PeriodSummary(
        total_messages=total_messages,
        unique_users=unique_users,
        avg_daily_users=avg_daily_users,
        new_users=new_users,
        left_users=left_users,
        start_date=start_utc.date().isoformat(),
        end_date=end_utc.date().isoformat(),
        days=days,
    )


@router.get("/{chat_id}/timeseries", response_model=List[TimeseriesPoint])
async def get_chat_timeseries(
    chat_id: int,
    metric: str = Query(..., regex="^(messages|dau)$"),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    session: Session = Depends(get_session),
    _token: None = Depends(verify_admin_token),
):
    """
    Get timeseries data for a chat.

    Args:
        chat_id: Telegram chat ID
        metric: Metric to retrieve ('messages' or 'dau')
        from_date: Start date (YYYY-MM-DD), defaults to 30 days ago
        to_date: End date (YYYY-MM-DD), defaults to today

    Returns:
        List of daily data points with date and value
    """
    tz = get_group_tz(chat_id, session)
    start_utc, end_utc, days = parse_period(from_date, to_date, tz)

    is_timescale = check_timescaledb_available(session)
    query = build_timeseries_query(is_timescale, metric)

    result = session.execute(
        query, {"chat_id": chat_id, "start_date": start_utc.date(), "end_date": end_utc.date()}
    ).fetchall()

    return [TimeseriesPoint(day=row.day.isoformat(), value=int(row.value)) for row in result]


@router.get("/{chat_id}/heatmap")
async def get_chat_heatmap(
    chat_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    session: Session = Depends(get_session),
    _token: None = Depends(verify_admin_token),
):
    """
    Get hourly heatmap data for a chat.

    Args:
        chat_id: Telegram chat ID
        from_date: Start date (YYYY-MM-DD), defaults to 30 days ago
        to_date: End date (YYYY-MM-DD), defaults to today

    Returns:
        Heatmap data with 7x24 matrix (weekdays x hours)
    """
    tz = get_group_tz(chat_id, session)
    start_utc, end_utc, days = parse_period(from_date, to_date, tz)

    is_timescale = check_timescaledb_available(session)
    query = build_heatmap_query(is_timescale)

    result = session.execute(
        query, {"chat_id": chat_id, "start_utc": start_utc, "end_utc": end_utc}
    ).fetchall()

    # Rotate to local timezone
    matrix = rotate_heatmap_rows(result, tz)

    return {
        "weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "hours": list(range(24)),
        "data": matrix,
    }


@router.get("/{chat_id}/users", response_model=UserStatsResponse)
async def get_chat_users(
    chat_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    sort: str = Query("act", regex="^(act|msg|ad|dsj|lm)$"),
    search: Optional[str] = Query(None),
    left: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
    _token: None = Depends(verify_admin_token),
):
    """
    Get user statistics for a chat with pagination and filtering.

    Args:
        chat_id: Telegram chat ID
        from_date: Start date (YYYY-MM-DD), defaults to 30 days ago
        to_date: End date (YYYY-MM-DD), defaults to today
        sort: Sort field (act=activity, msg=messages, ad=active days, dsj=days since join, lm=last message)
        search: Search users by username or name
        left: Filter by left status (true=left, false=active, null=all)
        page: Page number (1-indexed)
        per_page: Results per page (max 100)

    Returns:
        Paginated user statistics
    """
    tz = get_group_tz(chat_id, session)
    start_utc, end_utc, days = parse_period(from_date, to_date, tz)

    is_timescale = check_timescaledb_available(session)

    # Build the base query
    base_query = build_user_stats_query_base(is_timescale)

    # Add user details and membership info
    base_query += """
        SELECT 
            u.user_id,
            u.username,
            u.first_name,
            u.last_name,
            ps.msg_count,
            ps.active_days,
            ROUND((ps.msg_count::float / tm.total * 100)::numeric, 2) as activity_pct,
            m.joined_at,
            m.left_at,
            CASE WHEN m.left_at IS NULL THEN false ELSE true END as has_left,
            (SELECT MAX(date) FROM messages WHERE user_id = u.user_id AND chat_id = :chat_id) as last_message_at
        FROM users u
        INNER JOIN period_stats ps ON u.user_id = ps.user_id
        CROSS JOIN total_msgs tm
        LEFT JOIN memberships m ON u.user_id = m.user_id AND m.chat_id = :chat_id
        WHERE 1=1
    """

    # Add filters
    params = {"chat_id": chat_id, "start_date": start_utc.date(), "end_date": end_utc.date()}

    if search:
        base_query += """
            AND (
                LOWER(u.username) LIKE LOWER(:search) 
                OR LOWER(u.first_name) LIKE LOWER(:search)
                OR LOWER(u.last_name) LIKE LOWER(:search)
            )
        """
        params["search"] = f"%{search}%"

    if left is not None:
        if left:
            base_query += " AND m.left_at IS NOT NULL"
        else:
            base_query += " AND m.left_at IS NULL"

    # Add sorting
    sort_map = {
        "act": "activity_pct DESC",
        "msg": "msg_count DESC",
        "ad": "active_days DESC",
        "dsj": "joined_at DESC NULLS LAST",
        "lm": "last_message_at DESC NULLS LAST",
    }
    base_query += f" ORDER BY {sort_map.get(sort, 'activity_pct DESC')}"

    # Add pagination
    offset = (page - 1) * per_page
    base_query += f" LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = offset

    # Execute query
    result = session.execute(text(base_query), params).fetchall()

    # Get total count (without pagination)
    count_query = build_user_stats_query_base(is_timescale)
    count_query += """
        SELECT COUNT(*) as total
        FROM users u
        INNER JOIN period_stats ps ON u.user_id = ps.user_id
        LEFT JOIN memberships m ON u.user_id = m.user_id AND m.chat_id = :chat_id
        WHERE 1=1
    """
    if search:
        count_query += """
            AND (
                LOWER(u.username) LIKE LOWER(:search) 
                OR LOWER(u.first_name) LIKE LOWER(:search)
                OR LOWER(u.last_name) LIKE LOWER(:search)
            )
        """
    if left is not None:
        if left:
            count_query += " AND m.left_at IS NOT NULL"
        else:
            count_query += " AND m.left_at IS NULL"

    total = session.execute(text(count_query), params).fetchone().total

    users = [
        UserStats(
            user_id=row.user_id,
            username=row.username,
            first_name=row.first_name,
            last_name=row.last_name,
            msg_count=row.msg_count,
            active_days=row.active_days,
            activity_pct=float(row.activity_pct),
            joined_at=row.joined_at.isoformat() if row.joined_at else None,
            left_at=row.left_at.isoformat() if row.left_at else None,
            has_left=row.has_left,
            last_message_at=row.last_message_at.isoformat() if row.last_message_at else None,
        )
        for row in result
    ]

    return UserStatsResponse(
        users=users, total=total, page=page, per_page=per_page, pages=(total + per_page - 1) // per_page
    )


@router.get("/{chat_id}/retention/preview", response_model=RetentionPreviewResponse)
async def preview_retention(
    chat_id: int,
    session: Session = Depends(get_session),
    _token: None = Depends(verify_admin_token),
):
    """
    Preview what data would be deleted by retention policies.

    Args:
        chat_id: Telegram chat ID

    Returns:
        Preview of messages that would be deleted

    Raises:
        HTTPException: 404 if chat settings not found
    """
    result = retention_preview(chat_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return RetentionPreviewResponse(
        chat_id=result["chat_id"],
        text_retention_days=result["text_retention_days"],
        metadata_retention_days=result["metadata_retention_days"],
        messages_with_text_to_clear=result["messages_with_text_to_clear"],
        messages_to_delete=result["messages_to_delete"],
        oldest_message_date=result["oldest_message_date"],
        newest_message_date=result["newest_message_date"],
    )

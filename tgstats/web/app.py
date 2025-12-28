"""FastAPI application for webhook endpoint and analytics API."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
import uuid

import structlog
from fastapi import FastAPI, Request, HTTPException, Depends, Query, Header
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from telegram import Update
from telegram.ext import Application

from ..core.config import settings
from ..db import get_session
from ..models import Chat, GroupSettings
from sqlalchemy.ext.asyncio import AsyncSession
from ..celery_tasks import retention_preview
from ..schemas.api import (
    ChatSummary,
    ChatSettings,
    PeriodSummary,
    TimeseriesPoint,
    UserStats,
    UserStatsResponse,
    RetentionPreviewResponse,
)
from ..utils.sanitizer import sanitize_chat_id, is_safe_sql_input, is_safe_web_input
from .health import router as health_router
from .error_handlers import register_error_handlers
from .routers import webhook
from .routers.webhook import set_bot_application, get_bot_application

logger = structlog.get_logger(__name__)


# Create FastAPI app
app = FastAPI(
    title="Telegram Analytics Bot",
    description="Webhook endpoint and analytics API for Telegram bot",
    version="0.2.0",
)

# Parse CORS origins from comma-separated string
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,  # Configurable via CORS_ORIGINS env var
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# Request ID tracing middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID for tracing."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    # Bind request ID to logger context
    with structlog.contextvars.bound_contextvars(request_id=request_id):
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# Request size limit middleware
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Limit incoming request size to prevent DoS attacks."""
    if request.method in ["POST", "PUT", "PATCH"]:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_request_size:
            raise HTTPException(
                status_code=413,
                detail=f"Request too large. Max size: {settings.max_request_size} bytes",
            )
    return await call_next(request)


# Input validation middleware
@app.middleware("http")
async def validate_query_params(request: Request, call_next):
    """Validate query parameters for potential injection attacks."""
    # Check query string parameters
    for key, value in request.query_params.items():
        if isinstance(value, str):
            # Check for SQL injection patterns
            if not is_safe_sql_input(value):
                logger.warning(
                    "suspicious_query_param", key=key, value=value[:100], path=request.url.path
                )
                raise HTTPException(
                    status_code=400, detail=f"Invalid input detected in parameter: {key}"
                )

            # Check for XSS patterns
            if not is_safe_web_input(value):
                logger.warning(
                    "suspicious_xss_query_param", key=key, value=value[:100], path=request.url.path
                )
                raise HTTPException(
                    status_code=400, detail=f"Invalid input detected in parameter: {key}"
                )

    return await call_next(request)


# Include routers
app.include_router(health_router)
app.include_router(webhook.router)

# Register error handlers
register_error_handlers(app)

# Templates for minimal UI
templates = Jinja2Templates(directory="tgstats/web/templates")


# Auth dependency
async def verify_admin_token(x_admin_token: Optional[str] = Header(None)):
    """Verify admin API token if configured."""
    if settings.admin_api_token:
        if not x_admin_token or x_admin_token != settings.admin_api_token:
            raise HTTPException(status_code=401, detail="Invalid or missing admin token")


# Helper functions
def get_group_tz(chat_id: int, session: Session) -> ZoneInfo:
    """Get timezone for a group from settings."""
    settings_row = session.query(GroupSettings).filter_by(chat_id=chat_id).first()
    if settings_row and settings_row.timezone:
        try:
            return ZoneInfo(settings_row.timezone)
        except Exception:
            pass
    return ZoneInfo("UTC")


async def get_group_tz_async(chat_id: int, session: AsyncSession) -> ZoneInfo:
    """Get timezone for a group from settings (async version)."""
    from sqlalchemy import select

    stmt = select(GroupSettings).where(GroupSettings.chat_id == chat_id)
    result = await session.execute(stmt)
    settings_row = result.scalar_one_or_none()
    if settings_row and settings_row.timezone:
        try:
            return ZoneInfo(settings_row.timezone)
        except Exception:
            pass
    return ZoneInfo("UTC")


def parse_period(
    from_date: Optional[str] = None, to_date: Optional[str] = None, tz: ZoneInfo = ZoneInfo("UTC")
) -> Tuple[datetime, datetime, int]:
    """Parse period parameters and return UTC start, end, and days count."""
    if to_date:
        try:
            end_local = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=tz)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid to_date format. Use YYYY-MM-DD")
    else:
        # Default to end of today in local timezone
        now_local = datetime.now(tz)
        end_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)

    if from_date:
        try:
            start_local = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=tz)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid from_date format. Use YYYY-MM-DD")
    else:
        # Default to 30 days before end_local
        start_local = end_local - timedelta(days=30)
        start_local = start_local.replace(hour=0, minute=0, second=0, microsecond=0)

    # Convert to UTC
    start_utc = start_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    end_utc = end_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    days = (end_local.date() - start_local.date()).days + 1

    return start_utc, end_utc, days


def rotate_heatmap_rows(rows: List[Tuple], tz: ZoneInfo) -> List[List[int]]:
    """Rotate heatmap data from UTC to local timezone."""
    # Initialize 7x24 matrix (weekday x hour)
    matrix = [[0 for _ in range(24)] for _ in range(7)]

    for row in rows:
        hour_bucket, weekday_utc, hour_utc, msg_cnt = row

        # Convert UTC hour_bucket to local time
        utc_dt = hour_bucket.replace(tzinfo=ZoneInfo("UTC"))
        local_dt = utc_dt.astimezone(tz)

        local_weekday = local_dt.isoweekday() % 7  # Convert to 0=Monday, 6=Sunday
        local_hour = local_dt.hour

        matrix[local_weekday][local_hour] += msg_cnt

    return matrix


def check_timescaledb_available(session: Session) -> bool:
    """Check if TimescaleDB extension is available."""
    try:
        # Skip async check for coroutines
        if hasattr(session, "execute"):
            result = session.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
            ).fetchone()
            return result is not None
        else:
            return False
    except Exception:
        return False


# Analytics API endpoints
@app.get("/api/chats", response_model=List[ChatSummary])
async def get_chats(
    session: Session = Depends(get_session), _token: None = Depends(verify_admin_token)
):
    """Get list of known chats with 30-day stats."""
    is_timescale = check_timescaledb_available(session)

    if is_timescale:
        # Use continuous aggregate
        query = text(
            """
            WITH chat_stats AS (
                SELECT 
                    cd.chat_id,
                    SUM(cd.msg_cnt) as msg_count_30d,
                    AVG(cd.dau) as avg_dau_30d
                FROM chat_daily cd
                WHERE cd.day >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY cd.chat_id
            )
            SELECT c.chat_id, c.title, 
                   COALESCE(cs.msg_count_30d, 0) as msg_count_30d,
                   COALESCE(cs.avg_dau_30d, 0) as avg_dau_30d
            FROM chats c
            LEFT JOIN chat_stats cs ON c.chat_id = cs.chat_id
            ORDER BY cs.msg_count_30d DESC NULLS LAST
        """
        )
    else:
        # Use materialized view or compute on the fly
        query = text(
            """
            WITH chat_stats AS (
                SELECT 
                    cd.chat_id,
                    SUM(cd.msg_cnt) as msg_count_30d,
                    AVG(cd.dau) as avg_dau_30d
                FROM chat_daily_mv cd
                WHERE cd.day >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY cd.chat_id
                
                UNION ALL
                
                -- Fallback for chats not in materialized view
                SELECT 
                    m.chat_id,
                    COUNT(*) as msg_count_30d,
                    COUNT(DISTINCT DATE(m.date) || '-' || m.user_id) / 30.0 as avg_dau_30d
                FROM messages m
                WHERE m.date >= CURRENT_DATE - INTERVAL '30 days'
                  AND m.chat_id NOT IN (SELECT DISTINCT chat_id FROM chat_daily_mv WHERE day >= CURRENT_DATE - INTERVAL '30 days')
                GROUP BY m.chat_id
            )
            SELECT c.chat_id, c.title, 
                   COALESCE(SUM(cs.msg_count_30d), 0) as msg_count_30d,
                   COALESCE(AVG(cs.avg_dau_30d), 0) as avg_dau_30d
            FROM chats c
            LEFT JOIN chat_stats cs ON c.chat_id = cs.chat_id
            GROUP BY c.chat_id, c.title
            ORDER BY SUM(cs.msg_count_30d) DESC NULLS LAST
        """
        )

    result = session.execute(query).fetchall()

    return [
        ChatSummary(
            chat_id=row.chat_id,
            title=row.title,
            msg_count_30d=int(row.msg_count_30d),
            avg_dau_30d=float(row.avg_dau_30d),
        )
        for row in result
    ]


@app.get("/api/chats/{chat_id}/settings", response_model=ChatSettings)
async def get_chat_settings(
    chat_id: int,
    session: Session = Depends(get_session),
    _token: None = Depends(verify_admin_token),
):
    """Get settings for a specific chat."""
    # Validate chat_id
    validated_chat_id = sanitize_chat_id(chat_id)
    if validated_chat_id is None:
        raise HTTPException(status_code=400, detail="Invalid chat_id")

    settings_row = session.query(GroupSettings).filter_by(chat_id=validated_chat_id).first()

    if not settings_row:
        raise HTTPException(status_code=404, detail="Chat settings not found")

    return ChatSettings(
        chat_id=settings_row.chat_id,
        store_text=settings_row.store_text,
        text_retention_days=settings_row.text_retention_days,
        metadata_retention_days=settings_row.metadata_retention_days,
        timezone=settings_row.timezone,
        locale=settings_row.locale,
        capture_reactions=settings_row.capture_reactions,
    )


@app.get("/api/chats/{chat_id}/summary", response_model=PeriodSummary)
async def get_chat_summary(
    chat_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    session: Session = Depends(get_session),
    _token: None = Depends(verify_admin_token),
):
    """Get summary statistics for a chat over a period."""
    tz = get_group_tz(chat_id, session)
    start_utc, end_utc, days = parse_period(from_date, to_date, tz)

    is_timescale = check_timescaledb_available(session)
    table_name = "chat_daily" if is_timescale else "chat_daily_mv"

    # Get totals from aggregate table
    query = text(
        f"""
        SELECT 
            COALESCE(SUM(msg_cnt), 0) as total_messages,
            COALESCE(COUNT(DISTINCT day), 0) as active_days,
            COALESCE(AVG(dau), 0) as avg_daily_users
        FROM {table_name}
        WHERE chat_id = :chat_id 
        AND day >= :start_date 
        AND day <= :end_date
    """
    )

    result = session.execute(
        query, {"chat_id": chat_id, "start_date": start_utc.date(), "end_date": end_utc.date()}
    ).fetchone()

    total_messages = int(result.total_messages) if result else 0
    avg_daily_users = float(result.avg_daily_users) if result and result.avg_daily_users else 0

    # Get unique users over the period
    unique_users_query = text(
        """
        SELECT COUNT(DISTINCT user_id) as unique_users
        FROM messages
        WHERE chat_id = :chat_id 
        AND date >= :start_utc 
        AND date <= :end_utc
        AND user_id IS NOT NULL
    """
    )

    unique_result = session.execute(
        unique_users_query, {"chat_id": chat_id, "start_utc": start_utc, "end_utc": end_utc}
    ).fetchone()

    unique_users = int(unique_result.unique_users) if unique_result else 0

    # Get new/left users by checking membership dates
    start_local = start_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz).replace(tzinfo=None)
    end_local = end_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz).replace(tzinfo=None)

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


@app.get("/api/chats/{chat_id}/timeseries", response_model=List[TimeseriesPoint])
async def get_chat_timeseries(
    chat_id: int,
    metric: str = Query(..., regex="^(messages|dau)$"),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    session: Session = Depends(get_session),
    _token: None = Depends(verify_admin_token),
):
    """Get timeseries data for a chat."""
    tz = get_group_tz(chat_id, session)
    start_utc, end_utc, days = parse_period(from_date, to_date, tz)

    is_timescale = check_timescaledb_available(session)
    table_name = "chat_daily" if is_timescale else "chat_daily_mv"

    metric_column = "msg_cnt" if metric == "messages" else "dau"

    query = text(
        f"""
        SELECT day, {metric_column} as value
        FROM {table_name}
        WHERE chat_id = :chat_id 
        AND day >= :start_date 
        AND day <= :end_date
        ORDER BY day
    """
    )

    result = session.execute(
        query, {"chat_id": chat_id, "start_date": start_utc.date(), "end_date": end_utc.date()}
    ).fetchall()

    return [TimeseriesPoint(day=row.day.isoformat(), value=int(row.value)) for row in result]


@app.get("/api/chats/{chat_id}/heatmap")
async def get_chat_heatmap(
    chat_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    session: Session = Depends(get_session),
    _token: None = Depends(verify_admin_token),
):
    """Get hourly heatmap data for a chat."""
    tz = get_group_tz(chat_id, session)
    start_utc, end_utc, days = parse_period(from_date, to_date, tz)

    is_timescale = check_timescaledb_available(session)
    table_name = "chat_hourly_heatmap" if is_timescale else "chat_hourly_heatmap_mv"

    query = text(
        f"""
        SELECT hour_bucket, weekday, hour, msg_cnt
        FROM {table_name}
        WHERE chat_id = :chat_id 
        AND hour_bucket >= :start_utc 
        AND hour_bucket <= :end_utc
    """
    )

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


@app.get("/api/chats/{chat_id}/users", response_model=UserStatsResponse)
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
    """Get user statistics for a chat."""
    tz = get_group_tz(chat_id, session)
    start_utc, end_utc, days = parse_period(from_date, to_date, tz)

    is_timescale = check_timescaledb_available(session)
    table_name = "user_chat_daily" if is_timescale else "user_chat_daily_mv"

    # Build the base query
    base_query = f"""
        WITH period_stats AS (
            SELECT 
                ucd.user_id,
                SUM(ucd.msg_cnt) as msg_count,
                COUNT(DISTINCT ucd.day) as active_days
            FROM {table_name} ucd
            WHERE ucd.chat_id = :chat_id 
            AND ucd.day >= :start_date 
            AND ucd.day <= :end_date
            GROUP BY ucd.user_id
        ),
        total_msgs AS (
            SELECT SUM(msg_count) as total FROM period_stats
        ),
        user_stats AS (
            SELECT 
                u.user_id,
                u.username,
                u.first_name,
                u.last_name,
                COALESCE(ps.msg_count, 0) as msg_count,
                CASE 
                    WHEN tm.total > 0 THEN (ps.msg_count * 100.0 / tm.total)
                    ELSE 0 
                END as activity_percentage,
                CONCAT(COALESCE(ps.active_days, 0), '/', :days) as active_days_ratio,
                (
                    SELECT MAX(m.date)
                    FROM messages m 
                    WHERE m.chat_id = :chat_id 
                    AND m.user_id = u.user_id
                    AND m.date >= :start_utc 
                    AND m.date <= :end_utc
                ) as last_message,
                CASE 
                    WHEN mem.joined_at IS NOT NULL THEN
                        EXTRACT(DAY FROM (NOW() AT TIME ZONE :timezone) - (mem.joined_at AT TIME ZONE :timezone))
                    ELSE NULL 
                END as days_since_joined,
                mem.left_at IS NOT NULL as left
            FROM users u
            LEFT JOIN period_stats ps ON u.user_id = ps.user_id
            LEFT JOIN memberships mem ON u.user_id = mem.user_id AND mem.chat_id = :chat_id
            CROSS JOIN total_msgs tm
            WHERE u.user_id IN (
                SELECT DISTINCT user_id 
                FROM messages 
                WHERE chat_id = :chat_id 
                AND date >= :start_utc 
                AND date <= :end_utc
                AND user_id IS NOT NULL
            )
    """

    # Add filters
    filters = []
    params = {
        "chat_id": chat_id,
        "start_date": start_utc.date(),
        "end_date": end_utc.date(),
        "start_utc": start_utc,
        "end_utc": end_utc,
        "days": days,
        "timezone": str(tz),
    }

    if search:
        filters.append(
            "(u.username ILIKE :search OR u.first_name ILIKE :search OR u.last_name ILIKE :search)"
        )
        params["search"] = f"%{search}%"

    if left is not None:
        if left:
            filters.append("mem.left_at IS NOT NULL")
        else:
            filters.append("mem.left_at IS NULL")

    if filters:
        base_query += " AND " + " AND ".join(filters)

    # Add sorting
    sort_columns = {
        "act": "activity_percentage DESC",
        "msg": "msg_count DESC",
        "ad": "active_days_ratio DESC",
        "dsj": "days_since_joined ASC",
        "lm": "last_message DESC",
    }

    base_query += f" ORDER BY {sort_columns[sort]}, u.user_id"
    base_query += ")"

    # Count total
    count_query = f"SELECT COUNT(*) as total FROM ({base_query}) as counted"
    count_result = session.execute(text(count_query), params).fetchone()
    total = int(count_result.total) if count_result else 0

    # Add pagination
    offset = (page - 1) * per_page
    paginated_query = f"{base_query} LIMIT :limit OFFSET :offset"
    params.update({"limit": per_page, "offset": offset})

    result = session.execute(text(paginated_query), params).fetchall()

    users = []
    for row in result:
        users.append(
            UserStats(
                user_id=row.user_id,
                username=row.username,
                first_name=row.first_name,
                last_name=row.last_name,
                msg_count=int(row.msg_count),
                activity_percentage=float(row.activity_percentage),
                active_days_ratio=row.active_days_ratio,
                last_message=row.last_message.isoformat() if row.last_message else None,
                days_since_joined=int(row.days_since_joined) if row.days_since_joined else None,
                left=bool(row.left),
            )
        )

    return UserStatsResponse(items=users, page=page, per_page=per_page, total=total)


@app.get("/api/chats/{chat_id}/retention/preview", response_model=RetentionPreviewResponse)
async def get_retention_preview(
    chat_id: int,
    session: Session = Depends(get_session),
    _token: None = Depends(verify_admin_token),
):
    """Get preview of what would be deleted by retention policies."""
    # Start the Celery task
    task = retention_preview.delay(chat_id)
    result = task.get(timeout=30)  # Wait up to 30 seconds

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return RetentionPreviewResponse(**result)


# Internal API endpoints for UI (no auth required)
@app.get("/internal/chats/{chat_id}/summary")
async def ui_get_chat_summary(
    chat_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
):
    """Get chat summary for UI (no auth required)."""
    # First check if chat exists
    chat = await session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Reuse the existing logic from get_chat_summary but without auth
    tz = await get_group_tz_async(chat_id, session)
    start_utc, end_utc, days = parse_period(from_date, to_date, tz)

    # Get summary data - simplified version without complex date arithmetic
    query = text(
        """
        SELECT 
            COUNT(*) as total_messages,
            COUNT(DISTINCT messages.user_id) as unique_users,
            COUNT(DISTINCT messages.user_id)::float as avg_daily_users,
            COUNT(DISTINCT CASE WHEN memberships.joined_at BETWEEN :start_utc AND :end_utc THEN memberships.user_id END) as new_users,
            COUNT(DISTINCT CASE WHEN memberships.left_at BETWEEN :start_utc AND :end_utc THEN memberships.user_id END) as left_users
        FROM messages 
        LEFT JOIN memberships ON messages.user_id = memberships.user_id AND messages.chat_id = memberships.chat_id
        WHERE messages.chat_id = :chat_id 
        AND messages.date BETWEEN :start_utc AND :end_utc
    """
    )

    result = (
        await session.execute(
            query, {"chat_id": chat_id, "start_utc": start_utc, "end_utc": end_utc}
        )
    ).fetchone()

    # Even if no messages found, return zeros instead of 404
    if not result or result[0] is None:
        return {
            "total_messages": 0,
            "unique_users": 0,
            "avg_daily_users": 0.0,
            "new_users": 0,
            "left_users": 0,
            "start_date": start_utc.isoformat(),
            "end_date": end_utc.isoformat(),
            "days": (end_utc - start_utc).days + 1,
        }

    return {
        "total_messages": result[0] or 0,
        "unique_users": result[1] or 0,
        "avg_daily_users": float(result[2] or 0),
        "new_users": result[3] or 0,
        "left_users": result[4] or 0,
        "start_date": start_utc.isoformat(),
        "end_date": end_utc.isoformat(),
        "days": (end_utc - start_utc).days + 1,
    }


@app.get("/internal/chats/{chat_id}/timeseries")
async def ui_get_chat_timeseries(
    chat_id: int,
    metric: str = Query(..., pattern="^(messages|dau)$"),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
):
    """Get chat timeseries for UI (no auth required)."""
    # First check if chat exists
    chat = await session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    tz = await get_group_tz_async(chat_id, session)
    start_utc, end_utc, days = parse_period(from_date, to_date, tz)

    if metric == "messages":
        query = text(
            """
            SELECT DATE(date) as day, COUNT(*) as value
            FROM messages 
            WHERE chat_id = :chat_id 
            AND date BETWEEN :start_utc AND :end_utc
            GROUP BY DATE(date)
            ORDER BY day
        """
        )
    else:  # dau
        query = text(
            """
            SELECT DATE(date) as day, COUNT(DISTINCT user_id) as value
            FROM messages 
            WHERE chat_id = :chat_id 
            AND date BETWEEN :start_utc AND :end_utc
            GROUP BY DATE(date)
            ORDER BY day
        """
        )

    result = await session.execute(
        query, {"chat_id": chat_id, "start_utc": start_utc, "end_utc": end_utc}
    )

    return [{"day": str(row[0]), "value": row[1]} for row in result]


@app.get("/internal/chats/{chat_id}/heatmap")
async def ui_get_chat_heatmap(
    chat_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
):
    """Get chat heatmap for UI (no auth required)."""
    # First check if chat exists
    chat = await session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    tz = await get_group_tz_async(chat_id, session)
    start_utc, end_utc, days = parse_period(from_date, to_date, tz)

    query = text(
        """
        SELECT 
            EXTRACT(dow FROM date) as day_of_week,
            EXTRACT(hour FROM date) as hour,
            COUNT(*) as message_count
        FROM messages 
        WHERE chat_id = :chat_id 
        AND date BETWEEN :start_utc AND :end_utc
        GROUP BY EXTRACT(dow FROM date), EXTRACT(hour FROM date)
        ORDER BY day_of_week, hour
    """
    )

    result = await session.execute(
        query, {"chat_id": chat_id, "start_utc": start_utc, "end_utc": end_utc}
    )

    # Initialize matrix with zeros
    matrix = [[0 for _ in range(24)] for _ in range(7)]

    # Fill in the actual data
    for row in result:
        dow = int(row[0])  # 0=Sunday, 1=Monday, etc.
        hour = int(row[1])
        count = row[2]

        # Rotate: Sunday (0) -> 6, Monday (1) -> 0, etc.
        rotated_dow = (dow + 6) % 7
        matrix[rotated_dow][hour] = count

    return {
        "weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "hours": list(range(24)),
        "data": matrix,
    }


# Minimal Web UI
@app.get("/ui", response_class=HTMLResponse)
async def ui_chat_list(request: Request, session: AsyncSession = Depends(get_session)):
    """List all chats in a simple web interface."""
    # Get chats (reuse API logic but without auth)
    # For simplicity, use a basic query that works with both TimescaleDB and PostgreSQL
    query = text(
        """
        SELECT c.chat_id, c.title, 0 as msg_count_30d, 0 as avg_dau_30d
        FROM chats c
        ORDER BY c.chat_id
    """
    )

    chats = (await session.execute(query)).fetchall()

    return templates.TemplateResponse("chat_list.html", {"request": request, "chats": chats})


@app.get("/ui/chat/{chat_id}", response_class=HTMLResponse)
async def ui_chat_detail(
    request: Request, chat_id: int, session: AsyncSession = Depends(get_session)
):
    """Show chat details with analytics."""
    # Get chat info
    chat = await session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    return templates.TemplateResponse(
        "chat_detail.html", {"request": request, "chat": chat, "chat_id": chat_id}
    )


@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint."""
    return {
        "service": "Telegram Analytics Bot",
        "version": "0.2.0",
        "status": "running",
        "api_docs": "/docs",
        "ui": "/ui",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8010)

"""Database query utilities for web API.

This module provides reusable query builders to reduce SQL duplication
across API endpoints and ensure consistent query patterns.
"""

from datetime import datetime
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ..models import GroupSettings


def check_timescaledb_available(session: Session) -> bool:
    """
    Check if TimescaleDB extension is available in the database.

    Args:
        session: SQLAlchemy session

    Returns:
        True if TimescaleDB is available, False otherwise
    """
    try:
        if hasattr(session, "execute"):
            result = session.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
            ).fetchone()
            return result is not None
        else:
            return False
    except Exception:
        return False


def get_aggregate_table_name(is_timescale: bool, base_name: str) -> str:
    """
    Get the appropriate table name for aggregates based on TimescaleDB availability.

    Args:
        is_timescale: Whether TimescaleDB is available
        base_name: Base table name (e.g., 'chat_daily', 'user_chat_daily')

    Returns:
        Table name with appropriate suffix (_mv for materialized views)
    """
    return base_name if is_timescale else f"{base_name}_mv"


def get_group_tz(chat_id: int, session: Session) -> ZoneInfo:
    """
    Get timezone for a group from settings.

    Args:
        chat_id: Telegram chat ID
        session: SQLAlchemy session

    Returns:
        ZoneInfo object for the group's timezone, defaults to UTC
    """
    settings_row = session.query(GroupSettings).filter_by(chat_id=chat_id).first()
    if settings_row and settings_row.timezone:
        try:
            return ZoneInfo(settings_row.timezone)
        except Exception:
            pass
    return ZoneInfo("UTC")


async def get_group_tz_async(chat_id: int, session: AsyncSession) -> ZoneInfo:
    """
    Get timezone for a group from settings (async version).

    Args:
        chat_id: Telegram chat ID
        session: Async SQLAlchemy session

    Returns:
        ZoneInfo object for the group's timezone, defaults to UTC
    """
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


def build_chat_stats_query(is_timescale: bool, days: int = 30) -> text:
    """
    Build query to get chat statistics for a period.

    Args:
        is_timescale: Whether TimescaleDB is available
        days: Number of days to look back

    Returns:
        SQLAlchemy text query
    """
    table_name = get_aggregate_table_name(is_timescale, "chat_daily")

    if is_timescale:
        # Use continuous aggregate
        return text(
            f"""
            WITH chat_stats AS (
                SELECT 
                    cd.chat_id,
                    SUM(cd.msg_cnt) as msg_count_{days}d,
                    AVG(cd.dau) as avg_dau_{days}d
                FROM {table_name} cd
                WHERE cd.day >= CURRENT_DATE - INTERVAL '{days} days'
                GROUP BY cd.chat_id
            )
            SELECT c.chat_id, c.title, 
                   COALESCE(cs.msg_count_{days}d, 0) as msg_count_{days}d,
                   COALESCE(cs.avg_dau_{days}d, 0) as avg_dau_{days}d
            FROM chats c
            LEFT JOIN chat_stats cs ON c.chat_id = cs.chat_id
            ORDER BY cs.msg_count_{days}d DESC NULLS LAST
        """
        )
    else:
        # Use materialized view with fallback
        return text(
            f"""
            WITH chat_stats AS (
                SELECT 
                    cd.chat_id,
                    SUM(cd.msg_cnt) as msg_count_{days}d,
                    AVG(cd.dau) as avg_dau_{days}d
                FROM {table_name} cd
                WHERE cd.day >= CURRENT_DATE - INTERVAL '{days} days'
                GROUP BY cd.chat_id
                
                UNION ALL
                
                -- Fallback for chats not in materialized view
                SELECT 
                    m.chat_id,
                    COUNT(*) as msg_count_{days}d,
                    COUNT(DISTINCT DATE(m.date) || '-' || m.user_id) / {days}.0 as avg_dau_{days}d
                FROM messages m
                WHERE m.date >= CURRENT_DATE - INTERVAL '{days} days'
                  AND m.chat_id NOT IN (
                      SELECT DISTINCT chat_id FROM {table_name} 
                      WHERE day >= CURRENT_DATE - INTERVAL '{days} days'
                  )
                GROUP BY m.chat_id
            )
            SELECT c.chat_id, c.title, 
                   COALESCE(SUM(cs.msg_count_{days}d), 0) as msg_count_{days}d,
                   COALESCE(AVG(cs.avg_dau_{days}d), 0) as avg_dau_{days}d
            FROM chats c
            LEFT JOIN chat_stats cs ON c.chat_id = cs.chat_id
            GROUP BY c.chat_id, c.title
            ORDER BY SUM(cs.msg_count_{days}d) DESC NULLS LAST
        """
        )


def build_period_summary_query() -> text:
    """
    Build query to get period summary statistics.

    Returns:
        SQLAlchemy text query
    """
    return text(
        """
        SELECT 
            COUNT(*) as total_messages,
            COUNT(DISTINCT user_id) as unique_users,
            COUNT(DISTINCT user_id)::float as avg_daily_users
        FROM messages 
        WHERE chat_id = :chat_id 
        AND date >= :start_utc 
        AND date <= :end_utc
    """
    )


def build_timeseries_query(is_timescale: bool, metric: str) -> text:
    """
    Build query to get timeseries data.

    Args:
        is_timescale: Whether TimescaleDB is available
        metric: Metric to query ('messages' or 'dau')

    Returns:
        SQLAlchemy text query
    """
    table_name = get_aggregate_table_name(is_timescale, "chat_daily")
    metric_column = "msg_cnt" if metric == "messages" else "dau"

    return text(
        f"""
        SELECT day, {metric_column} as value
        FROM {table_name}
        WHERE chat_id = :chat_id 
        AND day >= :start_date 
        AND day <= :end_date
        ORDER BY day
    """
    )


def build_heatmap_query(is_timescale: bool) -> text:
    """
    Build query to get heatmap data.

    Args:
        is_timescale: Whether TimescaleDB is available

    Returns:
        SQLAlchemy text query
    """
    table_name = get_aggregate_table_name(is_timescale, "chat_hourly_heatmap")

    return text(
        f"""
        SELECT hour_bucket, weekday, hour, msg_cnt
        FROM {table_name}
        WHERE chat_id = :chat_id 
        AND hour_bucket >= :start_utc 
        AND hour_bucket <= :end_utc
    """
    )


def build_user_stats_query_base(is_timescale: bool) -> str:
    """
    Build base query string for user statistics.

    This returns just the CTE part that can be combined with other clauses.

    Args:
        is_timescale: Whether TimescaleDB is available

    Returns:
        SQL query string with CTEs
    """
    table_name = get_aggregate_table_name(is_timescale, "user_chat_daily")

    return f"""
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
        )
"""

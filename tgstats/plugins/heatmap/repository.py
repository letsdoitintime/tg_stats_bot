"""Heatmap repository for activity analysis queries."""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import Message
from ...repositories.base import BaseRepository


class HeatmapRepository(BaseRepository[Message]):
    """Repository for heatmap-related database operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Message, session)

    async def get_message_count_by_chat(self, chat_id: int, days: int = 7) -> int:
        """
        Get total message count for a chat in the specified time period.

        Args:
            chat_id: Chat ID
            days: Number of days to look back

        Returns:
            Total message count
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        query = select(func.count(Message.msg_id)).where(
            Message.chat_id == chat_id, Message.date >= cutoff_date
        )

        result = await self.session.execute(query)
        return result.scalar() or 0

    async def get_hourly_activity(
        self, chat_id: int, days: int = 7, limit: int = 10000
    ) -> List[Tuple[int, int, int]]:
        """
        Get message counts grouped by hour and day of week.

        Uses pre-computed materialized views for optimal performance.
        This avoids expensive EXTRACT operations on millions of rows.

        Args:
            chat_id: Chat ID
            days: Number of days to look back
            limit: Maximum number of aggregated groups to return

        Returns:
            List of tuples (hour, day_of_week, count)
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Use materialized view for instant results instead of scanning messages table
        # This reduces CPU from 200% to near zero by avoiding EXTRACT() on every row
        is_timescale = await self._is_timescaledb_available()
        view_name = "chat_hourly_heatmap" if is_timescale else "chat_hourly_heatmap_mv"

        # Query pre-computed aggregates - weekday is 1-7, convert to 0-6 for dow
        # Note: PostgreSQL dow is 0=Sunday, ISODOW is 1=Monday
        query = text(
            f"""
            SELECT
                CAST(hour AS INTEGER) as hour,
                CAST(CASE
                    WHEN weekday = 7 THEN 0  -- Sunday: ISODOW 7 -> dow 0
                    ELSE weekday             -- Mon-Sat: ISODOW 1-6 -> dow 1-6
                END AS INTEGER) as dow,
                CAST(SUM(msg_cnt) AS INTEGER) as count
            FROM {view_name}
            WHERE chat_id = :chat_id
              AND hour_bucket >= :cutoff_date
            GROUP BY hour, weekday
            ORDER BY weekday, hour
            LIMIT :limit
        """
        )

        result = await self.session.execute(
            query, {"chat_id": chat_id, "cutoff_date": cutoff_date, "limit": limit}
        )
        return result.all()

    async def _is_timescaledb_available(self) -> bool:
        """Check if TimescaleDB extension is available."""
        try:
            result = await self.session.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
            )
            return result.scalar() is not None
        except Exception:
            return False

    async def get_peak_activity_hour(
        self, chat_id: int, days: int = 30
    ) -> Optional[Tuple[int, int]]:
        """
        Get the most active hour in the specified period.

        Args:
            chat_id: Chat ID
            days: Number of days to look back

        Returns:
            Tuple of (hour, message_count) or None
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Use materialized view for performance
        is_timescale = await self._is_timescaledb_available()
        view_name = "chat_hourly_heatmap" if is_timescale else "chat_hourly_heatmap_mv"

        query = text(
            f"""
            SELECT
                CAST(hour AS INTEGER) as hour,
                CAST(SUM(msg_cnt) AS INTEGER) as count
            FROM {view_name}
            WHERE chat_id = :chat_id
              AND hour_bucket >= :cutoff_date
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 1
        """
        )

        result = await self.session.execute(query, {"chat_id": chat_id, "cutoff_date": cutoff_date})
        return result.first()

    async def get_peak_activity_day(
        self, chat_id: int, days: int = 30
    ) -> Optional[Tuple[int, int]]:
        """
        Get the most active day of week in the specified period.

        Args:
            chat_id: Chat ID
            days: Number of days to look back

        Returns:
            Tuple of (day_of_week, message_count) or None
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Use materialized view for performance
        is_timescale = await self._is_timescaledb_available()
        view_name = "chat_hourly_heatmap" if is_timescale else "chat_hourly_heatmap_mv"

        # Convert ISODOW (1-7) to dow (0-6) for consistency
        query = text(
            f"""
            SELECT
                CAST(CASE
                    WHEN weekday = 7 THEN 0  -- Sunday
                    ELSE weekday
                END AS INTEGER) as dow,
                CAST(SUM(msg_cnt) AS INTEGER) as count
            FROM {view_name}
            WHERE chat_id = :chat_id
              AND hour_bucket >= :cutoff_date
            GROUP BY weekday
            ORDER BY count DESC
            LIMIT 1
        """
        )

        result = await self.session.execute(query, {"chat_id": chat_id, "cutoff_date": cutoff_date})
        return result.first()

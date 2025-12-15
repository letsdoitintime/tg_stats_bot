"""Heatmap repository for activity analysis queries."""

from datetime import datetime, timedelta
from typing import List, Tuple, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import Message
from ...repositories.base import BaseRepository


class HeatmapRepository(BaseRepository[Message]):
    """Repository for heatmap-related database operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Message, session)
    
    async def get_message_count_by_chat(
        self,
        chat_id: int,
        days: int = 7
    ) -> int:
        """
        Get total message count for a chat in the specified time period.
        
        Args:
            chat_id: Chat ID
            days: Number of days to look back
            
        Returns:
            Total message count
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(func.count(Message.msg_id)).where(
            Message.chat_id == chat_id,
            Message.date >= cutoff_date
        )
        
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def get_hourly_activity(
        self,
        chat_id: int,
        days: int = 7,
        limit: int = 10000
    ) -> List[Tuple[int, int, int]]:
        """
        Get message counts grouped by hour and day of week.
        
        Note: The LIMIT is applied to aggregated results (hour/dow groups),
        not raw messages. For very large chats, consider pre-filtering
        by date range or using materialized views.
        
        Args:
            chat_id: Chat ID
            days: Number of days to look back
            limit: Maximum number of aggregated groups to return
            
        Returns:
            List of tuples (hour, day_of_week, count)
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Optimized query with aggregation at database level
        # Note: For production with millions of messages, consider:
        # 1. Adding a subquery with LIMIT on raw messages
        # 2. Using materialized views for common time ranges
        # 3. Partitioning messages table by date
        query = select(
            func.extract('hour', Message.date).label('hour'),
            func.extract('dow', Message.date).label('dow'),
            func.count(Message.msg_id).label('count')
        ).where(
            Message.chat_id == chat_id,
            Message.date >= cutoff_date
        ).group_by('hour', 'dow').limit(limit)
        
        result = await self.session.execute(query)
        return result.all()
    
    async def get_peak_activity_hour(
        self,
        chat_id: int,
        days: int = 30
    ) -> Optional[Tuple[int, int]]:
        """
        Get the most active hour in the specified period.
        
        Args:
            chat_id: Chat ID
            days: Number of days to look back
            
        Returns:
            Tuple of (hour, message_count) or None
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            func.extract('hour', Message.date).label('hour'),
            func.count(Message.msg_id).label('count')
        ).where(
            Message.chat_id == chat_id,
            Message.date >= cutoff_date
        ).group_by('hour').order_by(func.count(Message.msg_id).desc()).limit(1)
        
        result = await self.session.execute(query)
        return result.first()
    
    async def get_peak_activity_day(
        self,
        chat_id: int,
        days: int = 30
    ) -> Optional[Tuple[int, int]]:
        """
        Get the most active day of week in the specified period.
        
        Args:
            chat_id: Chat ID
            days: Number of days to look back
            
        Returns:
            Tuple of (day_of_week, message_count) or None
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            func.extract('dow', Message.date).label('dow'),
            func.count(Message.msg_id).label('count')
        ).where(
            Message.chat_id == chat_id,
            Message.date >= cutoff_date
        ).group_by('dow').order_by(func.count(Message.msg_id).desc()).limit(1)
        
        result = await self.session.execute(query)
        return result.first()

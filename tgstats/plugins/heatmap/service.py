"""Heatmap service for activity analysis."""

from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional
import hashlib
import json

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from .repository import HeatmapRepository
from ...utils.cache import cache_manager

logger = structlog.get_logger(__name__)


class HeatmapService:
    """
    Service for generating activity heatmaps.
    
    Performance: Uses pre-computed materialized views (chat_hourly_heatmap_mv)
    for instant results. Queries complete in <100ms even for millions of messages.
    """
    
    # Thresholds for large chats
    LARGE_CHAT_THRESHOLD = 10000  # messages
    MAX_MESSAGES_TO_PROCESS = 50000
    CACHE_TTL = 300  # 5 minutes
    
    def __init__(self, session: AsyncSession):
        self.repo = HeatmapRepository(session)
    
    def _get_cache_key(self, chat_id: int, days: int) -> str:
        """Generate cache key for heatmap data."""
        key_data = f"heatmap:{chat_id}:{days}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def is_large_chat(self, chat_id: int, days: int = 7) -> bool:
        """
        Check if a chat has a large number of messages.
        
        Args:
            chat_id: Chat ID
            days: Number of days to check
            
        Returns:
            True if chat has more than LARGE_CHAT_THRESHOLD messages
        """
        count = await self.repo.get_message_count_by_chat(chat_id, days)
        return count > self.LARGE_CHAT_THRESHOLD
    
    async def get_hourly_activity(
        self,
        chat_id: int,
        days: int = 7,
        use_cache: bool = True
    ) -> List[Tuple[int, int, int]]:
        """
        Get hourly activity data with caching.
        
        Args:
            chat_id: Chat ID
            days: Number of days to analyze
            use_cache: Whether to use cached results
            
        Returns:
            List of tuples (hour, day_of_week, count)
        """
        # Try cache first
        if use_cache:
            cache_key = self._get_cache_key(chat_id, days)
            cached_data = await cache_manager.get(cache_key)
            if cached_data:
                logger.info(
                    "heatmap_cache_hit",
                    chat_id=chat_id,
                    days=days
                )
                return json.loads(cached_data)
        
        # Check message count before processing
        message_count = await self.repo.get_message_count_by_chat(chat_id, days)
        
        logger.info(
            "heatmap_query_started",
            chat_id=chat_id,
            days=days,
            message_count=message_count
        )
        
        # Limit messages for very large chats
        limit = min(message_count, self.MAX_MESSAGES_TO_PROCESS)
        
        # Get data from database
        data = await self.repo.get_hourly_activity(chat_id, days, limit)
        
        # Convert to serializable format for caching
        serializable_data = [(int(h), int(d), int(c)) for h, d, c in data]
        
        # Cache the results
        if use_cache:
            cache_key = self._get_cache_key(chat_id, days)
            await cache_manager.set(
                cache_key,
                json.dumps(serializable_data),
                ttl=self.CACHE_TTL
            )
            logger.info(
                "heatmap_cached",
                chat_id=chat_id,
                days=days,
                data_points=len(serializable_data)
            )
        
        return serializable_data
    
    async def get_activity_summary(
        self,
        chat_id: int,
        days: int = 30
    ) -> Dict[str, Optional[Tuple[int, int]]]:
        """
        Get activity summary with peak hours and days.
        
        Args:
            chat_id: Chat ID
            days: Number of days to analyze
            
        Returns:
            Dictionary with 'peak_hour' and 'peak_day' data
        """
        peak_hour = await self.repo.get_peak_activity_hour(chat_id, days)
        peak_day = await self.repo.get_peak_activity_day(chat_id, days)
        
        return {
            'peak_hour': peak_hour,
            'peak_day': peak_day
        }
    
    def format_heatmap(self, data: List[Tuple[int, int, int]]) -> str:
        """
        Format heatmap data as text visualization.
        
        Args:
            data: List of tuples (hour, day_of_week, count)
            
        Returns:
            Formatted text heatmap
        """
        # Create a matrix for the heatmap
        matrix = [[0 for _ in range(24)] for _ in range(7)]
        
        for hour, dow, count in data:
            matrix[int(dow)][int(hour)] = count
        
        # Find max value for normalization (with safety checks)
        max_count = 1  # Default to 1 to avoid division by zero
        for row in matrix:
            if row:  # Check row is not empty
                row_max = max(row)
                if row_max > max_count:
                    max_count = row_max
        
        # Create text visualization
        days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        
        text = "📊 **Activity Heatmap (Last 7 Days)**\n\n"
        text += "```\n"
        text += "     00 04 08 12 16 20\n"
        text += "     ==================\n"
        
        for i, row in enumerate(matrix):
            text += f"{days[i]} |"
            for j in range(0, 24, 4):
                # Average counts in 4-hour blocks
                block_avg = sum(row[j:j+4]) / 4 / max_count
                
                if block_avg > 0.75:
                    char = '█'
                elif block_avg > 0.5:
                    char = '▓'
                elif block_avg > 0.25:
                    char = '▒'
                elif block_avg > 0:
                    char = '░'
                else:
                    char = ' '
                
                text += char + ' '
            text += '\n'
        
        text += "```\n"
        text += "Legend: █ Very Active, ▓ Active, ▒ Moderate, ░ Light\n"
        
        return text

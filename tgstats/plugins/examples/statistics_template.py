"""
Template for creating a new statistics plugin.

Copy this file to ../enabled/ and customize it for your needs.
"""

from typing import Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.ext import Application

from ..base import StatisticsPlugin, PluginMetadata
from ...models import Message  # Import models as needed


class MyStatisticsPlugin(StatisticsPlugin):
    """
    TODO: Add your plugin description here.
    
    This plugin calculates: [describe what statistics you calculate]
    """
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_statistics",  # TODO: Change this
            version="1.0.0",
            description="TODO: Describe what statistics you calculate",
            author="Your Name",  # TODO: Add your name
            dependencies=[]  # TODO: Add Python packages if needed
        )
    
    async def initialize(self, app: Application) -> None:
        """Initialize the plugin."""
        self._logger.info("my_statistics_plugin_initialized")
        
        # TODO: Add initialization logic here
        # Example:
        # self.config = load_config()
        # self.model = load_ml_model()
    
    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        self._logger.info("my_statistics_plugin_shutdown")
        
        # TODO: Add cleanup logic here
    
    def get_stat_name(self) -> str:
        """Return the name/key for this statistic."""
        return "my_stat"  # TODO: Change this
    
    def get_stat_description(self) -> str:
        """Return a human-readable description."""
        return "TODO: Describe your statistic"
    
    async def calculate_stats(
        self,
        session: AsyncSession,
        chat_id: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate custom statistics for a chat.
        
        Args:
            session: Database session for queries
            chat_id: The chat ID to analyze
            **kwargs: Additional parameters (define your own!)
                     Examples: days=30, limit=100, start_date=..., etc.
        
        Returns:
            Dictionary with your statistics results.
            Structure is up to you!
        """
        # TODO: Implement your statistics calculation
        
        # Example: Get parameters with defaults
        days = kwargs.get('days', 30)
        limit = kwargs.get('limit', 100)
        
        # Example: Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Example: Query messages
        query = select(Message).where(
            Message.chat_id == chat_id,
            Message.date >= start_date,
            Message.date <= end_date
        ).limit(limit)
        
        result = await session.execute(query)
        messages = result.scalars().all()
        
        # TODO: Process the data
        # Example calculations:
        # - Count something
        # - Aggregate data
        # - Run ML model
        # - Generate insights
        
        # Example: Return results
        return {
            'total_messages': len(messages),
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': days
            },
            # TODO: Add your calculated metrics here
            'my_metric_1': 0,
            'my_metric_2': 0.0,
            'my_list_metric': [],
            'my_nested_data': {
                'sub_metric': 0
            }
        }

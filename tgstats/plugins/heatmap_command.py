"""
Activity Heatmap Command Plugin.

Provides a /heatmap command to show when users are most active.
"""

from typing import Dict, Callable
import asyncio

from telegram import Update
from telegram.ext import Application, ContextTypes

from .base import CommandPlugin, PluginMetadata
from ..utils.decorators import with_db_session, group_only
from ..utils.telegram_helpers import send_message_with_retry
from ..services.heatmap_service import HeatmapService


class HeatmapCommandPlugin(CommandPlugin):
    """Command plugin that shows activity heatmap."""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="heatmap_command",
            version="2.0.0",
            description="Provides /heatmap command for activity visualization",
            author="TgStats Team",
            dependencies=[]
        )
    
    async def initialize(self, app: Application) -> None:
        """Initialize the plugin."""
        self._logger.info("heatmap_command_plugin_initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        self._logger.info("heatmap_command_plugin_shutdown")
    
    def get_commands(self) -> Dict[str, Callable]:
        return {
            'heatmap': self._heatmap_command,
            'activity': self._activity_command,
        }
    
    def get_command_descriptions(self) -> Dict[str, str]:
        return {
            'heatmap': 'Show hourly activity heatmap for the last 7 days',
            'activity': 'Show activity summary by day of week and hour',
        }
    
    @with_db_session
    @group_only
    async def _heatmap_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session
    ) -> None:
        """Generate activity heatmap using database queries only."""
        if not update.effective_chat or not update.message:
            return
        
        chat = update.effective_chat
        
        # Initial status message
        await send_message_with_retry(
            update, 
            "🔄 Analyzing activity patterns...",
            delay_before_send=0
        )
        
        try:
            # Use service layer for all analytics - NO Telegram API calls for data
            heatmap_service = HeatmapService(session)
            
            # Check if this is a large chat
            is_large = await heatmap_service.is_large_chat(chat.id, days=7)
            
            if is_large:
                self._logger.info(
                    "heatmap_large_chat_detected",
                    chat_id=chat.id
                )
                # Add delay for large chats to prevent API flooding
                await asyncio.sleep(0.5)
            
            # Get activity data from database (no Telegram API calls)
            data = await heatmap_service.get_hourly_activity(
                chat_id=chat.id,
                days=7,
                use_cache=True
            )
            
            if not data:
                await send_message_with_retry(
                    update,
                    "📊 No messages found in the last 7 days.",
                    delay_before_send=0.5
                )
                return
            
            # Format heatmap visualization
            heatmap_text = heatmap_service.format_heatmap(data)
            
            # Send with delay to prevent flooding
            await send_message_with_retry(
                update,
                heatmap_text,
                parse_mode="Markdown",
                delay_before_send=0.5
            )
            
        except Exception as e:
            self._logger.error(
                "heatmap_command_error",
                chat_id=chat.id,
                error=str(e),
                exc_info=True
            )
            # Try to send error message with delay
            await send_message_with_retry(
                update,
                "❌ An error occurred while generating the heatmap.",
                delay_before_send=0.5
            )
    
    @with_db_session
    @group_only
    async def _activity_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session
    ) -> None:
        """Show activity summary using database queries only."""
        if not update.effective_chat or not update.message:
            return
        
        chat = update.effective_chat
        
        try:
            # Use service layer for all analytics - NO Telegram API calls for data
            heatmap_service = HeatmapService(session)
            
            # Get activity summary from database
            summary = await heatmap_service.get_activity_summary(
                chat_id=chat.id,
                days=30
            )
            
            top_hour = summary.get('peak_hour')
            top_dow = summary.get('peak_day')
            
            # Check if we have data
            if not top_hour or not top_dow:
                await send_message_with_retry(
                    update,
                    "📊 No messages found in the last 30 days.",
                    delay_before_send=0.5
                )
                return
            
            days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 
                   'Thursday', 'Friday', 'Saturday']
            
            activity_text = f"""
📈 **Activity Summary (Last 30 Days)**

🕐 **Most Active Hour:** {int(top_hour[0]):02d}:00 ({top_hour[1]} messages)
📅 **Most Active Day:** {days[int(top_dow[0])]} ({top_dow[1]} messages)

💡 Use `/heatmap` to see detailed hourly breakdown
            """.strip()
            
            await send_message_with_retry(
                update,
                activity_text,
                parse_mode="Markdown",
                delay_before_send=0.5
            )
            
        except Exception as e:
            self._logger.error(
                "activity_command_error",
                chat_id=chat.id,
                error=str(e),
                exc_info=True
            )
            await send_message_with_retry(
                update,
                "❌ An error occurred while fetching activity data.",
                delay_before_send=0.5
            )

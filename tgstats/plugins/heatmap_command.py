"""
Activity Heatmap Command Plugin.

Provides a /heatmap command to show when users are most active.
"""

from typing import Dict, Callable
import asyncio

from telegram import Update
from telegram.ext import Application, ContextTypes
from telegram.error import RetryAfter, TimedOut, NetworkError

from .base import CommandPlugin, PluginMetadata
from ..utils.decorators import with_db_session, group_only
from ..services.heatmap_service import HeatmapService


class HeatmapCommandPlugin(CommandPlugin):
    """Command plugin that shows activity heatmap."""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="heatmap_command",
            version="1.0.0",
            description="Provides /heatmap command for activity visualization",
            author="TgStats Team",
            dependencies=[]
        )
    
    async def initialize(self, app: Application) -> None:
        """Initialize the plugin."""
        self._logger.info("heatmap_command_plugin_initialized")
    
    async def _send_message_with_retry(
        self,
        update: Update,
        text: str,
        max_retries: int = 3,
        delay_between_messages: float = 1.0,
        **kwargs
    ) -> bool:
        """
        Send a message with automatic retry on flood control errors.
        
        Args:
            update: Telegram update object
            text: Message text to send
            max_retries: Maximum number of retry attempts
            delay_between_messages: Delay in seconds before sending (prevents flooding)
            **kwargs: Additional arguments for reply_text
            
        Returns:
            True if message sent successfully, False otherwise
        """
        # Add delay before sending to prevent flooding
        if delay_between_messages > 0:
            await asyncio.sleep(delay_between_messages)
        
        for attempt in range(max_retries):
            try:
                await update.message.reply_text(text, **kwargs)
                return True
            except RetryAfter as e:
                retry_after = e.retry_after
                self._logger.warning(
                    "flood_control_hit",
                    chat_id=update.effective_chat.id if update.effective_chat else None,
                    retry_after=retry_after,
                    attempt=attempt + 1,
                    max_retries=max_retries
                )
                
                if attempt < max_retries - 1:
                    # Wait for the specified time plus a small buffer
                    await asyncio.sleep(retry_after + 1)
                else:
                    self._logger.error(
                        "flood_control_max_retries",
                        chat_id=update.effective_chat.id if update.effective_chat else None
                    )
                    return False
            except (TimedOut, NetworkError) as e:
                self._logger.warning(
                    "network_error_retry",
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=max_retries
                )
                
                if attempt < max_retries - 1:
                    # Exponential backoff: 2^attempt seconds
                    await asyncio.sleep(2 ** attempt)
                else:
                    return False
            except Exception as e:
                self._logger.error(
                    "message_send_error",
                    error=str(e),
                    exc_info=True
                )
                return False
        
        return False
    
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
        await self._send_message_with_retry(
            update, 
            "🔄 Analyzing activity patterns...",
            delay_between_messages=0
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
                await self._send_message_with_retry(
                    update,
                    "📊 No messages found in the last 7 days.",
                    delay_between_messages=0.5
                )
                return
            
            # Format heatmap visualization
            heatmap_text = heatmap_service.format_heatmap(data)
            
            # Send with delay to prevent flooding
            await self._send_message_with_retry(
                update,
                heatmap_text,
                parse_mode="Markdown",
                delay_between_messages=0.5
            )
            
        except Exception as e:
            self._logger.error(
                "heatmap_command_error",
                chat_id=chat.id,
                error=str(e),
                exc_info=True
            )
            # Try to send error message with delay
            await self._send_message_with_retry(
                update,
                "❌ An error occurred while generating the heatmap.",
                delay_between_messages=0.5
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
                await self._send_message_with_retry(
                    update,
                    "📊 No messages found in the last 30 days.",
                    delay_between_messages=0.5
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
            
            await self._send_message_with_retry(
                update,
                activity_text,
                parse_mode="Markdown",
                delay_between_messages=0.5
            )
            
        except Exception as e:
            self._logger.error(
                "activity_command_error",
                chat_id=chat.id,
                error=str(e),
                exc_info=True
            )
            await self._send_message_with_retry(
                update,
                "❌ An error occurred while fetching activity data.",
                delay_between_messages=0.5
            )
    
    def _format_heatmap(self, data) -> str:
        """
        DEPRECATED: Moved to HeatmapService.format_heatmap()
        Kept for backward compatibility only.
        """
        # This method is deprecated and kept only for reference
        # All formatting is now done in the service layer
        from ..services.heatmap_service import HeatmapService
        service = HeatmapService(None)
        return service.format_heatmap(data)

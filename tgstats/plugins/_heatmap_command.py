"""
Activity Heatmap Command Plugin.

Provides a /heatmap command to show when users are most active.
"""

from typing import Dict, Callable
from datetime import datetime, timedelta
import asyncio

from telegram import Update
from telegram.ext import Application, ContextTypes
from telegram.error import RetryAfter, TimedOut, NetworkError
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .base import CommandPlugin, PluginMetadata
from ..db import async_session
from ..models import Message


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
        **kwargs
    ) -> bool:
        """
        Send a message with automatic retry on flood control errors.
        
        Args:
            update: Telegram update object
            text: Message text to send
            max_retries: Maximum number of retry attempts
            **kwargs: Additional arguments for reply_text
            
        Returns:
            True if message sent successfully, False otherwise
        """
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
    
    async def _heatmap_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Generate activity heatmap."""
        if not update.effective_chat or not update.message:
            return
        
        chat = update.effective_chat
        
        # Only work in groups
        # Note: Telegram uses lowercase strings for chat types
        if chat.type not in ["group", "supergroup"]:
            await self._send_message_with_retry(
                update,
                "This command can only be used in groups."
            )
            return
        
        await self._send_message_with_retry(update, "🔄 Generating activity heatmap...")
        
        async with async_session() as session:
            try:
                # Get message counts by hour for last 7 days
                seven_days_ago = datetime.utcnow() - timedelta(days=7)
                
                # Query messages grouped by hour
                query = select(
                    func.extract('hour', Message.date).label('hour'),
                    func.extract('dow', Message.date).label('dow'),
                    func.count(Message.msg_id).label('count')
                ).where(
                    Message.chat_id == chat.id,
                    Message.date >= seven_days_ago
                ).group_by('hour', 'dow')
                
                result = await session.execute(query)
                data = result.all()
                
                if not data:
                    await self._send_message_with_retry(
                        update,
                        "📊 No messages found in the last 7 days."
                    )
                    return
                
                # Create heatmap visualization
                heatmap_text = self._format_heatmap(data)
                
                await self._send_message_with_retry(
                    update,
                    heatmap_text,
                    parse_mode="Markdown"
                )
                
            except Exception as e:
                self._logger.error(
                    "heatmap_command_error",
                    chat_id=chat.id,
                    error=str(e),
                    exc_info=True
                )
                # Try to send error message
                if update.message:
                    await self._send_message_with_retry(
                        update,
                        "❌ An error occurred while generating the heatmap."
                    )
    
    async def _activity_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Show activity summary."""
        if not update.effective_chat or not update.message:
            return
        
        chat = update.effective_chat
        
        # Only work in groups
        # Note: Telegram uses lowercase strings for chat types
        if chat.type not in ["group", "supergroup"]:
            await update.message.reply_text(
                "This command can only be used in groups."
            )
            return
        
        async with async_session() as session:
            try:
                # Get activity stats
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                
                # Most active hour
                hour_query = select(
                    func.extract('hour', Message.date).label('hour'),
                    func.count(Message.msg_id).label('count')
                ).where(
                    Message.chat_id == chat.id,
                    Message.date >= thirty_days_ago
                ).group_by('hour').order_by(func.count(Message.msg_id).desc()).limit(1)
                
                hour_result = await session.execute(hour_query)
                top_hour = hour_result.first()
                
                # Most active day
                dow_query = select(
                    func.extract('dow', Message.date).label('dow'),
                    func.count(Message.msg_id).label('count')
                ).where(
                    Message.chat_id == chat.id,
                    Message.date >= thirty_days_ago
                ).group_by('dow').order_by(func.count(Message.msg_id).desc()).limit(1)
                
                dow_result = await session.execute(dow_query)
                top_dow = dow_result.first()
                
                # Check if we have data
                if not top_hour or not top_dow:
                    await self._send_message_with_retry(
                        update,
                        "📊 No messages found in the last 30 days."
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
                    parse_mode="Markdown"
                )
                
            except Exception as e:
                self._logger.error(
                    "activity_command_error",
                    chat_id=chat.id,
                    error=str(e),
                    exc_info=True
                )
                if update.message:
                    await self._send_message_with_retry(
                        update,
                        "❌ An error occurred while fetching activity data."
                    )
    
    def _format_heatmap(self, data) -> str:
        """Format heatmap data as text visualization."""
        # Create a matrix for the heatmap
        matrix = [[0 for _ in range(24)] for _ in range(7)]
        
        for hour, dow, count in data:
            matrix[int(dow)][int(hour)] = count
        
        # Find max value for normalization
        max_count = max(max(row) for row in matrix)
        
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
                block_avg = sum(row[j:j+4]) / 4 / max(max_count, 1)
                
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

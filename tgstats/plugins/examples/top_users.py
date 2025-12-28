"""
User Activity Summary Plugin.

Provides detailed user activity statistics and a /topusers command.
"""

from typing import Dict, Callable, Any
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import Application, ContextTypes

from ..base import CommandPlugin, StatisticsPlugin, PluginMetadata
from ...db import async_session
from ...models import Message, User
from ...enums import ChatType


class TopUsersPlugin(CommandPlugin, StatisticsPlugin):
    """
    A plugin that combines command and statistics functionality.

    Provides:
    - /topusers command to show most active users
    - Statistics API for user activity metrics
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="top_users",
            version="1.0.0",
            description="Shows most active users and provides user activity stats",
            author="TgStats Team",
            dependencies=[],
        )

    async def initialize(self, app: Application) -> None:
        """Initialize the plugin."""
        self._logger.info("top_users_plugin_initialized")

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        self._logger.info("top_users_plugin_shutdown")

    # CommandPlugin methods
    def get_commands(self) -> Dict[str, Callable]:
        return {
            "topusers": self._top_users_command,
        }

    def get_command_descriptions(self) -> Dict[str, str]:
        return {
            "topusers": "Show the most active users in the group",
        }

    # StatisticsPlugin methods
    def get_stat_name(self) -> str:
        return "user_activity"

    def get_stat_description(self) -> str:
        return "User activity rankings and statistics"

    async def calculate_stats(
        self, session: AsyncSession, chat_id: int, days: int = 30, limit: int = 10, **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate user activity statistics.

        Args:
            session: Database session
            chat_id: Chat ID to analyze
            days: Number of days to look back (default: 30)
            limit: Number of top users to return (default: 10)

        Returns:
            User activity statistics
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        # Query top users by message count
        query = (
            select(
                User.user_id,
                User.username,
                User.first_name,
                User.last_name,
                func.count(Message.msg_id).label("message_count"),
            )
            .join(Message, Message.user_id == User.user_id)
            .where(
                and_(
                    Message.chat_id == chat_id, Message.date >= start_date, Message.date <= end_date
                )
            )
            .group_by(User.user_id, User.username, User.first_name, User.last_name)
            .order_by(func.count(Message.msg_id).desc())
            .limit(limit)
        )

        result = await session.execute(query)
        top_users = result.all()

        # Format results
        users = []
        total_messages = 0

        for user in top_users:
            users.append(
                {
                    "user_id": user.user_id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "display_name": self._get_display_name(user),
                    "message_count": user.message_count,
                }
            )
            total_messages += user.message_count

        return {
            "top_users": users,
            "total_messages": total_messages,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days,
            },
            "limit": limit,
        }

    async def _top_users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /topusers command."""
        if not update.effective_chat or not update.message:
            return

        chat = update.effective_chat

        # Only work in groups
        if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await update.message.reply_text("This command can only be used in groups.")
            return

        # Parse arguments
        days = 30
        limit = 10

        if context.args:
            try:
                if len(context.args) >= 1:
                    days = int(context.args[0])
                if len(context.args) >= 2:
                    limit = int(context.args[1])

                # Validate ranges
                if days < 1 or days > 365:
                    raise ValueError("Days must be between 1 and 365")
                if limit < 1 or limit > 50:
                    raise ValueError("Limit must be between 1 and 50")

            except ValueError as e:
                await update.message.reply_text(
                    f"❌ Invalid arguments: {e}\n"
                    f"Usage: /topusers [days] [limit]\n"
                    f"Example: /topusers 7 5"
                )
                return

        await update.message.reply_text("🔄 Calculating top users...")

        async with async_session() as session:
            try:
                # Use the statistics calculation
                stats = await self.calculate_stats(
                    session=session, chat_id=chat.id, days=days, limit=limit
                )

                if not stats["top_users"]:
                    await update.message.reply_text(
                        f"📊 No messages found in the last {days} days."
                    )
                    return

                # Format response
                response = f"👥 **Top {len(stats['top_users'])} Users (Last {days} Days)**\n\n"

                for i, user in enumerate(stats["top_users"], 1):
                    percentage = (user["message_count"] / stats["total_messages"]) * 100
                    response += f"{i}. {user['display_name']}: "
                    response += f"{user['message_count']} messages ({percentage:.1f}%)\n"

                response += f"\n📈 Total: {stats['total_messages']} messages"

                await update.message.reply_text(response, parse_mode="Markdown")

            except Exception as e:
                self._logger.error(
                    "top_users_command_error", chat_id=chat.id, error=str(e), exc_info=True
                )
                await update.message.reply_text("❌ An error occurred while calculating top users.")

    def _get_display_name(self, user) -> str:
        """Get a display name for a user."""
        if user.username:
            return f"@{user.username}"
        elif user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}"
        elif user.first_name:
            return user.first_name
        else:
            return f"User {user.user_id}"

"""Engagement plugin implementation module.

This file contains the `EngagementPlugin` class moved out of the package
`__init__` to keep the package entry thin and allow easier testing and
maintenance.
"""

from html import escape as html_escape

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from tgstats.core.exceptions import ChatNotSetupError
from tgstats.plugins.base import CommandPlugin, PluginMetadata
from tgstats.repositories.chat_repository import ChatRepository
from tgstats.services.engagement_service import EngagementScoringService
from tgstats.utils.decorators import group_only, with_db_session

logger = structlog.get_logger(__name__)


class EngagementPlugin(CommandPlugin):
    """Plugin for user engagement scoring and leaderboards."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="engagement_scores",
            version="1.0.0",
            description="Calculate and display user engagement scores",
            author="TG Stats Bot",
            dependencies=[],
        )

    async def initialize(self, app: Application) -> None:
        """Register command handlers and read plugin config."""
        # Read plugin-specific config (set by PluginManager)
        config = getattr(self, "_config", {}) or {}
        self._include_message_count = config.get("include_message_count", True)

        app.add_handler(CommandHandler("engagement", self.engagement_command))
        app.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
        app.add_handler(CommandHandler("leaderboard_thread", self.leaderboard_thread_command))
        app.add_handler(CommandHandler("myscore", self.my_score_command))

        # Register commands in Telegram's command menu
        commands = [
            BotCommand(command, description)
            for command, description in self.get_command_descriptions().items()
        ]

        try:
            await app.bot.set_my_commands(commands)
            logger.info("Engagement commands registered in Telegram menu", commands=commands)
        except Exception as e:
            logger.warning("Failed to set bot commands", error=str(e))

        logger.info("Engagement plugin initialized")

    async def shutdown(self) -> None:
        """Cleanup when plugin unloads."""
        logger.info("Engagement plugin shutting down")

    def get_commands(self) -> dict:
        """Return command handlers."""
        return {
            "engagement": self.engagement_command,
            "leaderboard": self.leaderboard_command,
            "leaderboard_thread": self.leaderboard_thread_command,
            "myscore": self.my_score_command,
        }

    def get_command_descriptions(self) -> dict:
        """Return command descriptions."""
        return {
            "engagement": "Show your engagement score",
            "leaderboard": "Show top engaged users (chat-wide)",
            "leaderboard_thread": "Show top engaged users in current thread/topic",
            "myscore": "Show detailed score breakdown",
        }

    @with_db_session
    @group_only
    async def engagement_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession
    ) -> None:
        """Show user's engagement score."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        thread_id = getattr(update.effective_message, "message_thread_id", None)

        # Check if chat is set up
        chat_repo = ChatRepository(session)
        chat = await chat_repo.get_by_chat_id(chat_id)
        if not chat or not chat.settings:
            raise ChatNotSetupError("This chat hasn't been set up yet. Use /setup first.")

        # Calculate engagement score
        engagement_service = EngagementScoringService(session)
        score = await engagement_service.calculate_engagement_score(
            chat_id=chat_id,
            user_id=user_id,
            days=30,
            thread_id=thread_id,
        )

        # Format message
        message = (
            f"📊 *Your Engagement Score*\n\n"
            f"Total Score: *{score.total_score}/100*\n\n"
            f"Breakdown:\n"
            f"• Activity: {score.activity_score:.1f}/100\n"
            f"• Consistency: {score.consistency_score:.1f}/100\n"
            f"• Quality: {score.quality_score:.1f}/100\n"
            f"• Interaction: {score.interaction_score:.1f}/100\n\n"
        )

        if score.percentile:
            message += f"You're in the top {100 - score.percentile:.0f}% of active users! 🎉"

        await update.message.reply_text(message, parse_mode="Markdown")

        logger.info(
            "User engagement score displayed",
            chat_id=chat_id,
            user_id=user_id,
            score=score.total_score,
        )

    @with_db_session
    @group_only
    async def my_score_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession
    ) -> None:
        """Show detailed engagement score breakdown."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        thread_id = getattr(update.effective_message, "message_thread_id", None)

        # Check if chat is set up
        chat_repo = ChatRepository(session)
        chat = await chat_repo.get_by_chat_id(chat_id)
        if not chat or not chat.settings:
            raise ChatNotSetupError("This chat hasn't been set up yet. Use /setup first.")

        # Calculate engagement score
        engagement_service = EngagementScoringService(session)
        score = await engagement_service.calculate_engagement_score(
            chat_id=chat_id,
            user_id=user_id,
            days=30,
            thread_id=thread_id,
        )

        # Get detailed metrics
        metrics = await engagement_service.get_engagement_metrics(chat_id, user_id, 30, thread_id)

        # Format detailed message
        message = (
            f"📈 *Detailed Engagement Report (Last 30 Days)*\n\n"
            f"*Overall Score: {score.total_score}/100*\n\n"
            f"*Activity Score: {score.activity_score:.1f}/100*\n"
            f"• Messages sent: {metrics.message_count}\n"
            f"• Avg per day: {metrics.message_count / 30:.1f}\n\n"
            f"*Consistency Score: {score.consistency_score:.1f}/100*\n"
            f"• Days active: {metrics.days_active}/30\n"
            f"• Participation: {metrics.days_active/30*100:.0f}%\n\n"
            f"*Quality Score: {score.quality_score:.1f}/100*\n"
            f"• Avg message length: {metrics.avg_message_length:.0f} chars\n"
            f"• URLs shared: {metrics.url_count}\n"
            f"• Media shared: {metrics.media_count}\n"
            f"• Reactions received: {metrics.reactions_received}\n"
            f"• Replies received: {metrics.replies_received}\n\n"
            f"*Interaction Score: {score.interaction_score:.1f}/100*\n"
            f"• Replies sent: {metrics.reply_count}\n"
            f"• Reactions given: {metrics.reactions_given}\n"
        )

        if score.percentile:
            message += f"\n🏆 Top {100 - score.percentile:.0f}% of active users!"

        await update.message.reply_text(message, parse_mode="Markdown")

    @with_db_session
    @group_only
    async def leaderboard_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession
    ) -> None:
        """Show engagement leaderboard (top 10 users)."""
        chat_id = update.effective_chat.id

        # Check if chat is set up
        chat_repo = ChatRepository(session)
        chat = await chat_repo.get_by_chat_id(chat_id)
        if not chat or not chat.settings:
            raise ChatNotSetupError("This chat hasn't been set up yet. Use /setup first.")

        # Leaderboard is public - no admin check needed
        # Anyone in the group can view engagement scores

        # Use optimized method to get leaderboard with user details
        engagement_service = EngagementScoringService(session)
        include_metrics = getattr(self, "_include_message_count", False)

        leaderboard_data = await engagement_service.get_leaderboard_with_details(
            chat_id=chat_id,
            days=30,
            min_messages=5,
            limit=10,
            include_metrics=include_metrics,
        )

        if not leaderboard_data:
            await update.message.reply_text("No active users found in the last 30 days.")
            return

        # Format leaderboard (top 10)
        message = "🏆 Engagement Leaderboard (Last 30 Days)\n\n"

        # Build list with detailed logging to debug parsing issues
        leaderboard_entries = []
        for idx, (score, user, metrics) in enumerate(leaderboard_data, 1):
            if user:
                username = user.username or user.first_name or f"User {user.user_id}"
                username_html = html_escape(username)
                medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
                entry = f"{medal} <b>{username_html}</b>: {score.total_score:.1f}"

                # Optionally include message/reply counts
                if metrics:
                    entry += (
                        f" ({metrics.message_count} msgs, {metrics.reply_count} 🔁, "
                        f"{metrics.replies_received} 📥)"
                    )

                leaderboard_entries.append(entry)
                logger.info(
                    "Leaderboard entry",
                    idx=idx,
                    user_id=score.user_id,
                    username=username,
                    score=score.total_score,
                    entry_length=len(entry),
                )

        # Log the full message before sending
        message = message + "\n".join(leaderboard_entries)

        # Count total users by recalculating (cached from previous call)
        scores = await engagement_service.calculate_chat_engagement_scores(
            chat_id=chat_id, days=30, min_messages=5
        )
        message += f"\n\n{len(scores)} active users total"

        logger.info(
            "Sending leaderboard",
            chat_id=chat_id,
            message_length=len(message),
            entries_count=len(leaderboard_entries),
        )

        # Send as HTML so usernames are bolded
        await update.message.reply_text(message, parse_mode="HTML")

        logger.info("Leaderboard displayed", chat_id=chat_id, total_users=len(scores))

    @with_db_session
    @group_only
    async def leaderboard_thread_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession
    ) -> None:
        """Show engagement leaderboard limited to the current thread/topic."""
        chat_id = update.effective_chat.id
        thread_id = getattr(update.effective_message, "message_thread_id", None)

        if thread_id is None:
            await update.message.reply_text(
                "This command must be used inside a forum topic (thread)."
            )
            return

        # Check if chat is set up
        chat_repo = ChatRepository(session)
        chat = await chat_repo.get_by_chat_id(chat_id)
        if not chat or not chat.settings:
            raise ChatNotSetupError("This chat hasn't been set up yet. Use /setup first.")

        # Use optimized method to get thread-scoped leaderboard
        engagement_service = EngagementScoringService(session)
        include_metrics = getattr(self, "_include_message_count", False)

        leaderboard_data = await engagement_service.get_leaderboard_with_details(
            chat_id=chat_id,
            days=30,
            min_messages=5,
            thread_id=thread_id,
            limit=10,
            include_metrics=include_metrics,
        )

        if not leaderboard_data:
            await update.message.reply_text(
                "No active users found in this thread in the last 30 days."
            )
            return

        message = "🏆 Topic Engagement Leaderboard (Last 30 Days)\n\n"
        leaderboard_entries = []
        for idx, (score, user, metrics) in enumerate(leaderboard_data, 1):
            if user:
                username = user.username or user.first_name or f"User {user.user_id}"
                username_html = html_escape(username)
                medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
                entry = f"{medal} <b>{username_html}</b>: {score.total_score:.1f}"

                if metrics:
                    entry += (
                        f" ({metrics.message_count} msgs, {metrics.reply_count} 🔁, "
                        f"{metrics.replies_received} 📥)"
                    )

                leaderboard_entries.append(entry)

        message = message + "\n".join(leaderboard_entries)

        # Count total users in thread
        scores = await engagement_service.calculate_chat_engagement_scores(
            chat_id=chat_id, days=30, min_messages=5, thread_id=thread_id
        )
        message += f"\n\n{len(scores)} active users in thread"

        await update.message.reply_text(message, parse_mode="HTML")

        logger.info(
            "Thread leaderboard displayed",
            chat_id=chat_id,
            thread_id=thread_id,
            total_users=len(scores),
        )

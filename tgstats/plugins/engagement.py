"""Engagement scores plugin.

Provides commands to view user engagement scores and leaderboards.
"""

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, Application
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from ..base import CommandPlugin, PluginMetadata
from ...utils.decorators import with_db_session, group_only
from ...services.engagement_service import EngagementScoringService
from ...repositories.user_repository import UserRepository
from ...repositories.chat_repository import ChatRepository
from ...core.exceptions import ChatNotSetupError

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
            dependencies=[]
        )

    async def initialize(self, app: Application) -> None:
        """Register command handlers."""
        app.add_handler(CommandHandler("engagement", self.engagement_command))
        app.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
        app.add_handler(CommandHandler("myscore", self.my_score_command))
        logger.info("Engagement plugin initialized")

    async def shutdown(self) -> None:
        """Cleanup when plugin unloads."""
        logger.info("Engagement plugin shutting down")

    @property
    def commands(self) -> dict:
        """Return command descriptions."""
        return {
            'engagement': 'Show your engagement score',
            'leaderboard': 'Show top engaged users (admin only)',
            'myscore': 'Show detailed score breakdown'
        }

    @with_db_session
    @group_only
    async def engagement_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession
    ) -> None:
        """Show user's engagement score."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
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
            days=30
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
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
        logger.info(
            "User engagement score displayed",
            chat_id=chat_id,
            user_id=user_id,
            score=score.total_score
        )

    @with_db_session
    @group_only
    async def my_score_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession
    ) -> None:
        """Show detailed engagement score breakdown."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
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
            days=30
        )
        
        # Get detailed metrics
        metrics = await engagement_service._get_engagement_metrics(
            chat_id, user_id, 30
        )
        
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
            f"• Reactions received: {metrics.reactions_received}\n\n"
            
            f"*Interaction Score: {score.interaction_score:.1f}/100*\n"
            f"• Replies sent: {metrics.reply_count}\n"
            f"• Reactions given: {metrics.reactions_given}\n"
        )
        
        if score.percentile:
            message += f"\n🏆 Top {100 - score.percentile:.0f}% of active users!"
        
        await update.message.reply_text(message, parse_mode='Markdown')

    @with_db_session
    @group_only
    async def leaderboard_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession
    ) -> None:
        """Show engagement leaderboard (top 10 users)."""
        chat_id = update.effective_chat.id
        
        # Check if chat is set up
        chat_repo = ChatRepository(session)
        chat = await chat_repo.get_by_chat_id(chat_id)
        if not chat or not chat.settings:
            raise ChatNotSetupError("This chat hasn't been set up yet. Use /setup first.")
        
        # Check if user is admin
        chat_member = await context.bot.get_chat_member(chat_id, update.effective_user.id)
        if chat_member.status not in ['creator', 'administrator']:
            await update.message.reply_text(
                "⛔ Only administrators can view the leaderboard."
            )
            return
        
        # Calculate scores for all users
        await update.message.reply_text("🔄 Calculating engagement scores...")
        
        engagement_service = EngagementScoringService(session)
        scores = await engagement_service.calculate_chat_engagement_scores(
            chat_id=chat_id,
            days=30,
            min_messages=5
        )
        
        if not scores:
            await update.message.reply_text("No active users found in the last 30 days.")
            return
        
        # Get user details
        user_repo = UserRepository(session)
        
        # Format leaderboard (top 10)
        message = "🏆 *Engagement Leaderboard (Last 30 Days)*\n\n"
        
        for idx, score in enumerate(scores[:10], 1):
            user = await user_repo.get_by_user_id(score.user_id)
            if user:
                username = user.username or user.first_name or f"User {user.user_id}"
                medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
                message += f"{medal} {username}: *{score.total_score:.1f}*\n"
        
        message += f"\n_{len(scores)} active users total_"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
        logger.info(
            "Leaderboard displayed",
            chat_id=chat_id,
            total_users=len(scores)
        )

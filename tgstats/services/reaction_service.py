"""Reaction processing service."""

from typing import TYPE_CHECKING, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import MessageReactionUpdated, ReactionType

from .base import BaseService

if TYPE_CHECKING:
    from ..repositories.factory import RepositoryFactory

logger = structlog.get_logger(__name__)


class ReactionService(BaseService):
    """Service for reaction-related operations."""

    def __init__(self, session: AsyncSession, repo_factory: "RepositoryFactory" = None):
        """Initialize reaction service with database session."""
        super().__init__(session, repo_factory)

    def _extract_emoji(self, reaction: ReactionType) -> Optional[str]:
        """Extract emoji string from reaction type."""
        if hasattr(reaction, "emoji"):
            return reaction.emoji
        elif hasattr(reaction, "custom_emoji_id"):
            return f"custom:{reaction.custom_emoji_id}"
        return None

    async def process_reaction_update(self, reaction_update: MessageReactionUpdated) -> None:
        """
        Process a reaction update (add or remove).

        Args:
            reaction_update: Telegram reaction update object
        """
        chat = reaction_update.chat
        user = reaction_update.user

        if not chat or not reaction_update.message_id:
            logger.debug("Skipping reaction - missing chat or message_id")
            return

        # Check if reactions are enabled for this chat
        from .chat_service import ChatService

        chat_service = ChatService(self.session, self.repos)
        settings = await chat_service.get_chat_settings(chat.id)

        if not settings or not settings.capture_reactions:
            logger.debug("Reactions not enabled", chat_id=chat.id)
            return

        # Upsert chat and user
        await chat_service.get_or_create_chat(chat)
        if user:
            from .user_service import UserService

            user_service = UserService(self.session, self.repos)
            await user_service.get_or_create_user(user)

        reaction_date = reaction_update.date

        # Process removed reactions
        if reaction_update.old_reaction:
            for old_reaction in reaction_update.old_reaction:
                emoji = self._extract_emoji(old_reaction)
                if emoji:
                    count = await self.repos.reaction.mark_as_removed(
                        chat.id,
                        reaction_update.message_id,
                        user.id if user else None,
                        emoji,
                        reaction_date,
                    )
                    logger.debug("Reaction marked as removed", emoji=emoji, count=count)

        # Process added reactions
        if reaction_update.new_reaction:
            for new_reaction in reaction_update.new_reaction:
                emoji = self._extract_emoji(new_reaction)
                if emoji:
                    await self.repos.reaction.upsert_reaction(
                        chat.id,
                        reaction_update.message_id,
                        user.id if user else None,
                        emoji,
                        getattr(new_reaction, "is_big", False),
                        reaction_date,
                    )
                    logger.debug("Reaction added/updated", emoji=emoji)

        await self.session.commit()

        logger.info(
            "Reaction update processed",
            chat_id=chat.id,
            user_id=user.id if user else None,
            msg_id=reaction_update.message_id,
            old_count=len(reaction_update.old_reaction) if reaction_update.old_reaction else 0,
            new_count=len(reaction_update.new_reaction) if reaction_update.new_reaction else 0,
        )

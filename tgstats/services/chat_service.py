"""Chat management service."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Chat as TelegramChat

from ..core.exceptions import ChatNotSetupError
from ..models import Chat, GroupSettings
from .base import BaseService

if TYPE_CHECKING:
    from ..repositories.factory import RepositoryFactory


class ChatService(BaseService):
    """Service for chat-related operations."""

    def __init__(self, session: AsyncSession, repo_factory: "RepositoryFactory" = None):
        """Initialize chat service with database session."""
        super().__init__(session, repo_factory)

    async def get_or_create_chat(self, tg_chat: TelegramChat) -> Chat:
        """Get or create a chat from Telegram chat object."""
        chat = await self.repos.chat.upsert_from_telegram(tg_chat)
        self.logger.info("Chat upserted", chat_id=chat.chat_id, title=chat.title)
        return chat

    async def get_chat_settings(self, chat_id: int) -> Optional[GroupSettings]:
        """Get settings for a chat."""
        return await self.repos.settings.get_by_chat_id(chat_id)

    async def get_chat_settings_or_raise(self, chat_id: int) -> GroupSettings:
        """Get settings for a chat or raise exception if not found."""
        settings = await self.get_chat_settings(chat_id)
        if not settings:
            raise ChatNotSetupError(f"Chat {chat_id} has not been set up yet")
        return settings

    async def setup_chat(self, chat_id: int) -> GroupSettings:
        """Set up a chat with default settings."""
        settings = await self.repos.settings.create_default(chat_id)
        await self.commit()
        self.logger.info("Chat setup completed", chat_id=chat_id)
        return settings

    async def update_text_storage(self, chat_id: int, store_text: bool) -> Optional[GroupSettings]:
        """Update text storage setting for a chat."""
        settings = await self.repos.settings.update_setting(chat_id, "store_text", store_text)
        if settings:
            await self.commit()
            self.logger.info("Text storage updated", chat_id=chat_id, store_text=store_text)
        return settings

    async def update_reaction_capture(
        self, chat_id: int, capture_reactions: bool
    ) -> Optional[GroupSettings]:
        """Update reaction capture setting for a chat."""
        settings = await self.repos.settings.update_setting(
            chat_id, "capture_reactions", capture_reactions
        )
        if settings:
            await self.commit()
            self.logger.info(
                "Reaction capture updated", chat_id=chat_id, capture_reactions=capture_reactions
            )
        return settings

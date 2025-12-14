"""Chat management service."""

import structlog
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Chat as TelegramChat

from ..models import Chat, GroupSettings
from ..repositories.chat_repository import ChatRepository, GroupSettingsRepository
from ..core.exceptions import ChatNotSetupError

logger = structlog.get_logger(__name__)


class ChatService:
    """Service for chat-related operations."""
    
    def __init__(self, session: AsyncSession):
        """Initialize chat service with database session."""
        self.session = session
        self.chat_repo = ChatRepository(session)
        self.settings_repo = GroupSettingsRepository(session)
    
    async def get_or_create_chat(self, tg_chat: TelegramChat) -> Chat:
        """Get or create a chat from Telegram chat object."""
        chat = await self.chat_repo.upsert_from_telegram(tg_chat)
        logger.info("Chat upserted", chat_id=chat.chat_id, title=chat.title)
        return chat
    
    async def get_chat_settings(self, chat_id: int) -> Optional[GroupSettings]:
        """Get settings for a chat."""
        return await self.settings_repo.get_by_chat_id(chat_id)
    
    async def get_chat_settings_or_raise(self, chat_id: int) -> GroupSettings:
        """Get settings for a chat or raise exception if not found."""
        settings = await self.get_chat_settings(chat_id)
        if not settings:
            raise ChatNotSetupError(f"Chat {chat_id} has not been set up yet")
        return settings
    
    async def setup_chat(self, chat_id: int) -> GroupSettings:
        """Set up a chat with default settings."""
        settings = await self.settings_repo.create_default(chat_id)
        await self.session.commit()
        logger.info("Chat setup completed", chat_id=chat_id)
        return settings
    
    async def update_text_storage(
        self, chat_id: int, store_text: bool
    ) -> Optional[GroupSettings]:
        """Update text storage setting for a chat."""
        settings = await self.settings_repo.update_setting(
            chat_id, "store_text", store_text
        )
        if settings:
            await self.session.commit()
            logger.info(
                "Text storage updated",
                chat_id=chat_id,
                store_text=store_text
            )
        return settings
    
    async def update_reaction_capture(
        self, chat_id: int, capture_reactions: bool
    ) -> Optional[GroupSettings]:
        """Update reaction capture setting for a chat."""
        settings = await self.settings_repo.update_setting(
            chat_id, "capture_reactions", capture_reactions
        )
        if settings:
            await self.session.commit()
            logger.info(
                "Reaction capture updated",
                chat_id=chat_id,
                capture_reactions=capture_reactions
            )
        return settings

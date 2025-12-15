"""Message processing service."""

from typing import Optional, Dict, Any, TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Message as TelegramMessage

from ..models import Message
from ..utils.features import extract_message_features, get_media_type_from_message
from .base import BaseService

if TYPE_CHECKING:
    from ..repositories.factory import RepositoryFactory
    from .chat_service import ChatService
    from .user_service import UserService


class MessageService(BaseService):
    """Service for message-related operations."""
    
    def __init__(
        self, 
        session: AsyncSession,
        repo_factory: "RepositoryFactory" = None,
        chat_service: "ChatService" = None,
        user_service: "UserService" = None
    ):
        """Initialize message service with database session and optional dependencies."""
        super().__init__(session, repo_factory)
        self._chat_service = chat_service
        self._user_service = user_service
    
    @property
    def chat_service(self) -> "ChatService":
        """Lazy-load chat service."""
        if self._chat_service is None:
            from .chat_service import ChatService
            self._chat_service = ChatService(self.session, self.repos)
        return self._chat_service
    
    @property
    def user_service(self) -> "UserService":
        """Lazy-load user service."""
        if self._user_service is None:
            from .user_service import UserService
            self._user_service = UserService(self.session, self.repos)
        return self._user_service
    
    async def process_message(self, tg_message: TelegramMessage) -> Optional[Message]:
        """
        Process and store a Telegram message.
        
        Args:
            tg_message: Telegram message object
            
        Returns:
            Message model instance or None if user info missing
        """
        if not tg_message.from_user:
            self.logger.warning("Message without user info, skipping")
            return None
        
        # Upsert chat and user
        await self.chat_service.get_or_create_chat(tg_message.chat)
        await self.user_service.get_or_create_user(tg_message.from_user)
        
        # Ensure membership exists
        await self.user_service.ensure_membership(
            tg_message.chat.id,
            tg_message.from_user.id,
            tg_message.date
        )
        
        # Get group settings to check if we should store text
        settings = await self.chat_service.get_chat_settings(tg_message.chat.id)
        store_text = settings.store_text if settings else True
        
        # Extract message features
        text_raw, text_len, urls_cnt, emoji_cnt = extract_message_features(
            tg_message, store_text
        )
        
        # Determine media type
        media_type = get_media_type_from_message(tg_message)
        has_media = media_type != "text"
        
        # Prepare entities JSON
        entities_json = None
        if tg_message.entities:
            entities_json = [
                {
                    "type": entity.type,
                    "offset": entity.offset,
                    "length": entity.length,
                    "url": entity.url,
                    "user": entity.user.to_dict() if entity.user else None,
                    "language": entity.language,
                }
                for entity in tg_message.entities
            ]
        
        # Create message record
        from ..repositories.message_repository import MessageRepository
        message_repo = MessageRepository(self.session)
        message = await message_repo.create_from_telegram(
            tg_message,
            text_raw,
            text_len,
            urls_cnt,
            emoji_cnt,
            media_type,
            has_media,
            entities_json
        )
        
        await self.commit()
        
        self.logger.info(
            "Message processed",
            chat_id=tg_message.chat.id,
            user_id=tg_message.from_user.id,
            msg_id=tg_message.message_id,
            text_len=text_len,
            media_type=media_type
        )
        
        return message

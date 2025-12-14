"""Message processing service."""

import structlog
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Message as TelegramMessage

from ..models import Message
from ..repositories.message_repository import MessageRepository
from ..features import extract_message_features, get_media_type_from_message
from .chat_service import ChatService
from .user_service import UserService

logger = structlog.get_logger(__name__)


class MessageService:
    """Service for message-related operations."""
    
    def __init__(self, session: AsyncSession):
        """Initialize message service with database session."""
        self.session = session
        self.message_repo = MessageRepository(session)
        self.chat_service = ChatService(session)
        self.user_service = UserService(session)
    
    async def process_message(self, tg_message: TelegramMessage) -> Optional[Message]:
        """
        Process and store a Telegram message.
        
        Args:
            tg_message: Telegram message object
            
        Returns:
            Message model instance or None if user info missing
        """
        if not tg_message.from_user:
            logger.warning("Message without user info, skipping")
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
        message = await self.message_repo.create_from_telegram(
            tg_message,
            text_raw,
            text_len,
            urls_cnt,
            emoji_cnt,
            media_type,
            has_media,
            entities_json
        )
        
        await self.session.commit()
        
        logger.info(
            "Message processed",
            chat_id=tg_message.chat.id,
            user_id=tg_message.from_user.id,
            msg_id=tg_message.message_id,
            text_len=text_len,
            media_type=media_type
        )
        
        return message

"""Chat repository for database operations."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from telegram import Chat as TelegramChat

from ..models import Chat, GroupSettings
from ..enums import ChatType
from .base import BaseRepository


class ChatRepository(BaseRepository[Chat]):
    """Repository for chat-related database operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Chat, session)
    
    async def get_by_chat_id(self, chat_id: int) -> Optional[Chat]:
        """Get chat by Telegram chat ID with settings eagerly loaded."""
        result = await self.session.execute(
            select(Chat)
            .where(Chat.chat_id == chat_id)
            .options(selectinload(Chat.settings))
        )
        return result.scalar_one_or_none()
    
    async def upsert_from_telegram(self, tg_chat: TelegramChat) -> Chat:
        """
        Upsert a chat record from Telegram chat object.
        
        Args:
            tg_chat: Telegram chat object
            
        Returns:
            Chat model instance
        """
        # Extract photo information
        photo_small_file_id = None
        photo_big_file_id = None
        if hasattr(tg_chat, "photo") and tg_chat.photo:
            photo_small_file_id = tg_chat.photo.small_file_id
            photo_big_file_id = tg_chat.photo.big_file_id
        
        # Extract permissions
        permissions_json = None
        if hasattr(tg_chat, "permissions") and tg_chat.permissions:
            permissions_json = {
                "can_send_messages": getattr(tg_chat.permissions, "can_send_messages", None),
                "can_send_audios": getattr(tg_chat.permissions, "can_send_audios", None),
                "can_send_documents": getattr(tg_chat.permissions, "can_send_documents", None),
                "can_send_photos": getattr(tg_chat.permissions, "can_send_photos", None),
                "can_send_videos": getattr(tg_chat.permissions, "can_send_videos", None),
                "can_send_video_notes": getattr(tg_chat.permissions, "can_send_video_notes", None),
                "can_send_voice_notes": getattr(tg_chat.permissions, "can_send_voice_notes", None),
                "can_send_polls": getattr(tg_chat.permissions, "can_send_polls", None),
                "can_send_other_messages": getattr(tg_chat.permissions, "can_send_other_messages", None),
                "can_add_web_page_previews": getattr(tg_chat.permissions, "can_add_web_page_previews", None),
                "can_change_info": getattr(tg_chat.permissions, "can_change_info", None),
                "can_invite_users": getattr(tg_chat.permissions, "can_invite_users", None),
                "can_pin_messages": getattr(tg_chat.permissions, "can_pin_messages", None),
                "can_manage_topics": getattr(tg_chat.permissions, "can_manage_topics", None),
            }
        
        chat_data = {
            "chat_id": tg_chat.id,
            "title": tg_chat.title,
            "username": tg_chat.username,
            "type": ChatType(tg_chat.type),
            "is_forum": getattr(tg_chat, "is_forum", False),
            "description": getattr(tg_chat, "description", None),
            "photo_small_file_id": photo_small_file_id,
            "photo_big_file_id": photo_big_file_id,
            "invite_link": getattr(tg_chat, "invite_link", None),
            "pinned_message_id": getattr(tg_chat.pinned_message, "message_id", None) if hasattr(tg_chat, "pinned_message") and tg_chat.pinned_message else None,
            "permissions_json": permissions_json,
            "slow_mode_delay": getattr(tg_chat, "slow_mode_delay", None),
            "message_auto_delete_time": getattr(tg_chat, "message_auto_delete_time", None),
            "has_protected_content": getattr(tg_chat, "has_protected_content", None),
            "linked_chat_id": getattr(tg_chat, "linked_chat_id", None),
            "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }
        
        stmt = insert(Chat).values(**chat_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Chat.chat_id],
            set_={
                "title": stmt.excluded.title,
                "username": stmt.excluded.username,
                "type": stmt.excluded.type,
                "is_forum": stmt.excluded.is_forum,
                "description": stmt.excluded.description,
                "photo_small_file_id": stmt.excluded.photo_small_file_id,
                "photo_big_file_id": stmt.excluded.photo_big_file_id,
                "invite_link": stmt.excluded.invite_link,
                "pinned_message_id": stmt.excluded.pinned_message_id,
                "permissions_json": stmt.excluded.permissions_json,
                "slow_mode_delay": stmt.excluded.slow_mode_delay,
                "message_auto_delete_time": stmt.excluded.message_auto_delete_time,
                "has_protected_content": stmt.excluded.has_protected_content,
                "linked_chat_id": stmt.excluded.linked_chat_id,
                "updated_at": stmt.excluded.updated_at,
            }
        )
        
        await self.session.execute(stmt)
        await self.session.flush()
        
        return await self.get_by_chat_id(tg_chat.id)


class GroupSettingsRepository(BaseRepository[GroupSettings]):
    """Repository for group settings operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(GroupSettings, session)
    
    async def get_by_chat_id(self, chat_id: int) -> Optional[GroupSettings]:
        """Get settings by chat ID."""
        result = await self.session.execute(
            select(GroupSettings).where(GroupSettings.chat_id == chat_id)
        )
        return result.scalar_one_or_none()
    
    async def create_default(self, chat_id: int) -> GroupSettings:
        """Create default settings for a chat."""
        from ..core.constants import (
            DEFAULT_STORE_TEXT,
            DEFAULT_TEXT_RETENTION_DAYS,
            DEFAULT_METADATA_RETENTION_DAYS,
            DEFAULT_TIMEZONE,
            DEFAULT_LOCALE,
            DEFAULT_CAPTURE_REACTIONS,
        )
        
        settings_data = {
            "chat_id": chat_id,
            "store_text": DEFAULT_STORE_TEXT,
            "text_retention_days": DEFAULT_TEXT_RETENTION_DAYS,
            "metadata_retention_days": DEFAULT_METADATA_RETENTION_DAYS,
            "timezone": DEFAULT_TIMEZONE,
            "locale": DEFAULT_LOCALE,
            "capture_reactions": DEFAULT_CAPTURE_REACTIONS,
        }
        
        stmt = insert(GroupSettings).values(**settings_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=[GroupSettings.chat_id])
        
        await self.session.execute(stmt)
        await self.session.flush()
        
        return await self.get_by_chat_id(chat_id)
    
    async def update_setting(
        self, chat_id: int, setting_name: str, value: any
    ) -> Optional[GroupSettings]:
        """Update a specific setting."""
        settings = await self.get_by_chat_id(chat_id)
        if settings:
            setattr(settings, setting_name, value)
            await self.session.flush()
        return settings

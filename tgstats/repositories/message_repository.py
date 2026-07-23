"""Message repository for database operations."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Message as TelegramMessage

from ..models import Message
from .base import BaseRepository


def extract_forward_origin(
    tg_message: TelegramMessage,
) -> Tuple[
    Optional[int], Optional[int], Optional[int], Optional[str], Optional[str], Optional[datetime]
]:
    """Map Bot API 7.0's `forward_origin` onto this table's forward_* columns.

    Returns (from_user_id, from_chat_id, from_message_id, signature,
    sender_name, date) — the same six values the pre-7.0 flat attributes used
    to supply, so the stored schema is unchanged.

    The four origin variants carry different information, which is why a single
    flat mapping was replaced upstream:
      MessageOriginUser        sender_user      -> a visible user
      MessageOriginHiddenUser  sender_user_name -> user hid their account, name only
      MessageOriginChat        sender_chat      -> sent on behalf of a group
      MessageOriginChannel     chat + message_id -> a channel post, linkable back

    `date` is present on every variant and is timezone-aware; it is normalised
    to naive UTC to match how every other datetime is stored here.
    """
    origin = getattr(tg_message, "forward_origin", None)
    if origin is None:
        return (None, None, None, None, None, None)

    from_user_id = getattr(getattr(origin, "sender_user", None), "id", None)
    # A channel post exposes `chat`; a group-on-behalf-of post exposes
    # `sender_chat`. Both land in the same column, as before.
    chat_obj = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
    from_chat_id = getattr(chat_obj, "id", None)
    from_message_id = getattr(origin, "message_id", None)
    signature = getattr(origin, "author_signature", None)
    sender_name = getattr(origin, "sender_user_name", None)

    date = getattr(origin, "date", None)
    if date is not None and date.tzinfo:
        date = date.astimezone(timezone.utc).replace(tzinfo=None)

    return (from_user_id, from_chat_id, from_message_id, signature, sender_name, date)


class MessageRepository(BaseRepository[Message]):
    """Repository for message-related database operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Message, session)

    async def get_by_chat_and_msg_id(self, chat_id: int, msg_id: int) -> Optional[Message]:
        """Get message by chat ID and message ID."""
        result = await self.session.execute(
            select(Message).where(Message.chat_id == chat_id, Message.msg_id == msg_id)
        )
        return result.scalar_one_or_none()

    async def create_from_telegram(
        self,
        tg_message: TelegramMessage,
        text_raw: Optional[str],
        text_len: int,
        urls_cnt: int,
        emoji_cnt: int,
        media_type: str,
        has_media: bool,
        entities_json: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """
        Create a message record from Telegram message object.

        Args:
            tg_message: Telegram message object
            text_raw: Raw text content (None if not storing)
            text_len: Length of text
            urls_cnt: Number of URLs
            emoji_cnt: Number of emojis
            media_type: Type of media
            has_media: Whether message has media
            entities_json: Message entities as JSON

        Returns:
            Message model instance
        """
        # Convert timezone-aware datetime to UTC naive
        msg_date = tg_message.date
        if msg_date and msg_date.tzinfo:
            msg_date = msg_date.astimezone(timezone.utc).replace(tzinfo=None)

        edit_date = tg_message.edit_date
        if edit_date and edit_date.tzinfo:
            edit_date = edit_date.astimezone(timezone.utc).replace(tzinfo=None)

        # Extract forward information from forward_origin.
        #
        # This used to read tg_message.forward_from / .forward_from_chat /
        # .forward_from_message_id / .forward_signature / .forward_sender_name /
        # .forward_date. Bot API 7.0 replaced all six with a single
        # `forward_origin` object, and python-telegram-bot removed the legacy
        # attributes entirely — so every hasattr()/getattr() guard above
        # silently evaluated to None and NOTHING was ever stored. Confirmed on
        # production: 0 of 107,089 messages had any forward metadata, including
        # 175 that is_automatic_forward marks as channel auto-forwards.
        (
            forward_from_user_id,
            forward_from_chat_id,
            forward_from_message_id,
            forward_signature,
            forward_sender_name,
            forward_date,
        ) = extract_forward_origin(tg_message)

        # Extract caption entities
        caption_entities_json = None
        if tg_message.caption_entities:
            caption_entities_json = [
                {
                    "type": entity.type,
                    "offset": entity.offset,
                    "length": entity.length,
                    "url": entity.url,
                    "user": entity.user.to_dict() if entity.user else None,
                    "language": entity.language,
                }
                for entity in tg_message.caption_entities
            ]

        # Extract web page data
        web_page_json = None
        if hasattr(tg_message, "web_page") and tg_message.web_page:
            wp = tg_message.web_page
            web_page_json = {
                "url": getattr(wp, "url", None),
                "display_url": getattr(wp, "display_url", None),
                "type": getattr(wp, "type", None),
                "site_name": getattr(wp, "site_name", None),
                "title": getattr(wp, "title", None),
                "description": getattr(wp, "description", None),
            }

        # Extract file/media metadata
        file_id = None
        file_unique_id = None
        file_size = None
        file_name = None
        mime_type = None
        duration = None
        width = None
        height = None
        thumbnail_file_id = None

        # Check different media types for file info
        media_obj = None
        if tg_message.photo:
            # Get largest photo
            media_obj = max(tg_message.photo, key=lambda p: p.file_size or 0)
        elif tg_message.video:
            media_obj = tg_message.video
        elif tg_message.document:
            media_obj = tg_message.document
        elif tg_message.audio:
            media_obj = tg_message.audio
        elif tg_message.voice:
            media_obj = tg_message.voice
        elif tg_message.video_note:
            media_obj = tg_message.video_note
        elif tg_message.animation:
            media_obj = tg_message.animation
        elif tg_message.sticker:
            media_obj = tg_message.sticker

        if media_obj:
            file_id = getattr(media_obj, "file_id", None)
            file_unique_id = getattr(media_obj, "file_unique_id", None)
            file_size = getattr(media_obj, "file_size", None)
            file_name = getattr(media_obj, "file_name", None)
            mime_type = getattr(media_obj, "mime_type", None)
            duration = getattr(media_obj, "duration", None)
            width = getattr(media_obj, "width", None)
            height = getattr(media_obj, "height", None)

            if hasattr(media_obj, "thumbnail") and media_obj.thumbnail:
                thumbnail_file_id = media_obj.thumbnail.file_id

        message_data = {
            "chat_id": tg_message.chat.id,
            "msg_id": tg_message.message_id,
            "user_id": tg_message.from_user.id if tg_message.from_user else None,
            "date": msg_date,
            "edit_date": edit_date,
            "thread_id": getattr(tg_message, "message_thread_id", None),
            "reply_to_msg_id": (
                tg_message.reply_to_message.message_id if tg_message.reply_to_message else None
            ),
            "has_media": has_media,
            "media_type": media_type,
            "text_raw": text_raw,
            "text_len": text_len,
            "urls_cnt": urls_cnt,
            "emoji_cnt": emoji_cnt,
            "entities_json": entities_json,
            "caption_entities_json": caption_entities_json,
            # Forward information
            "forward_from_user_id": forward_from_user_id,
            "forward_from_chat_id": forward_from_chat_id,
            "forward_from_message_id": forward_from_message_id,
            "forward_signature": forward_signature,
            "forward_sender_name": forward_sender_name,
            "forward_date": forward_date,
            "is_automatic_forward": getattr(tg_message, "is_automatic_forward", None),
            # Additional metadata
            "via_bot_id": (
                tg_message.via_bot.id
                if hasattr(tg_message, "via_bot") and tg_message.via_bot
                else None
            ),
            "author_signature": getattr(tg_message, "author_signature", None),
            "media_group_id": getattr(tg_message, "media_group_id", None),
            "has_protected_content": getattr(tg_message, "has_protected_content", None),
            "web_page_json": web_page_json,
            # File metadata
            "file_id": file_id,
            "file_unique_id": file_unique_id,
            "file_size": file_size,
            "file_name": file_name,
            "mime_type": mime_type,
            "duration": duration,
            "width": width,
            "height": height,
            "thumbnail_file_id": thumbnail_file_id,
        }

        # Use UPSERT to handle potential duplicates
        stmt = insert(Message).values(**message_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=[Message.chat_id, Message.msg_id])

        await self.session.execute(stmt)
        await self.session.flush()

        return await self.get_by_chat_and_msg_id(tg_message.chat.id, tg_message.message_id)

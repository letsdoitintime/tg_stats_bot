"""Message feature extraction functions."""

import re
from typing import Optional, Tuple

import emoji
from telegram import Message

from .enums import MediaType

# URL regex pattern
URL_PATTERN = re.compile(
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)


def extract_message_features(
    message: Message, store_text: bool = True
) -> Tuple[Optional[str], int, int, int]:
    """
    Extract features from a Telegram message.
    
    Args:
        message: Telegram message object
        store_text: Whether to return the raw text (based on group settings)
        
    Returns:
        Tuple of (text_raw_or_none, text_len, urls_cnt, emoji_cnt)
    """
    # Get the text content (message text or caption)
    text_content = message.text or message.caption or ""
    
    # Calculate text length
    text_len = len(text_content)
    
    # Count URLs
    urls_cnt = len(URL_PATTERN.findall(text_content))
    
    # Count emojis using emoji library
    emoji_cnt = len([char for char in text_content if emoji.is_emoji(char)])
    
    # Return text based on store_text setting
    text_raw = text_content if store_text else None
    
    return text_raw, text_len, urls_cnt, emoji_cnt


def get_media_type_from_message(message: Message) -> str:
    """Determine the media type of a message."""
    if message.photo:
        return MediaType.PHOTO
    elif message.video:
        return MediaType.VIDEO
    elif message.document:
        return MediaType.DOCUMENT
    elif message.audio:
        return MediaType.AUDIO
    elif message.voice:
        return MediaType.VOICE
    elif message.video_note:
        return MediaType.VIDEO_NOTE
    elif message.sticker:
        return MediaType.STICKER
    elif message.animation:
        return MediaType.ANIMATION
    elif message.location:
        return MediaType.LOCATION
    elif message.contact:
        return MediaType.CONTACT
    elif message.poll:
        return MediaType.POLL
    elif message.venue:
        return MediaType.VENUE
    elif message.dice:
        return MediaType.DICE
    elif message.game:
        return MediaType.GAME
    elif message.text or message.caption:
        return MediaType.TEXT
    else:
        return MediaType.OTHER

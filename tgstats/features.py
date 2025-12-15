"""Message feature extraction functions.

This module provides utilities to extract analytics features from Telegram messages,
including text statistics, URL counting, emoji detection, and media type classification.
"""

import re
from typing import Optional, Tuple

import emoji
from telegram import Message

from .enums import MediaType

# Compiled regex pattern for URL detection
# Matches http:// or https:// URLs with common characters
URL_PATTERN = re.compile(
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)


def extract_message_features(
    message: Message, store_text: bool = True
) -> Tuple[Optional[str], int, int, int]:
    """Extract analytics features from a Telegram message.
    
    This function analyzes a Telegram message to extract various features
    for analytics and storage:
    - Text content (optionally stored based on privacy settings)
    - Text length in characters
    - Number of URLs found in the text
    - Number of emoji characters
    
    Args:
        message: Telegram message object to analyze
        store_text: Whether to return the raw text content.
                   Set to False for privacy-conscious groups that only
                   want to track metadata without storing message text.
        
    Returns:
        A tuple containing:
        - text_raw: The full text content if store_text=True, None otherwise
        - text_len: Length of the text in characters
        - urls_cnt: Number of URLs found in the text
        - emoji_cnt: Number of emoji characters found
        
    Example:
        >>> text, length, urls, emojis = extract_message_features(message, True)
        >>> print(f"Message has {length} chars, {urls} URLs, {emojis} emojis")
    """
    # Get the text content (prefer message.text, fallback to caption for media)
    text_content = message.text or message.caption or ""
    
    # Calculate text length in characters
    text_len = len(text_content)
    
    # Count URLs using regex pattern
    urls_cnt = len(URL_PATTERN.findall(text_content))
    
    # Count emojis using the emoji library's detection
    # This properly handles multi-byte emoji sequences
    emoji_cnt = len([char for char in text_content if emoji.is_emoji(char)])
    
    # Return text based on store_text setting (privacy control)
    text_raw = text_content if store_text else None
    
    return text_raw, text_len, urls_cnt, emoji_cnt


def get_media_type_from_message(message: Message) -> str:
    """Determine the media type of a Telegram message.
    
    Analyzes a message to determine what type of media it contains.
    The check order matters: we check specific media types first,
    then fall back to text, and finally 'other' for unknown types.
    
    Args:
        message: Telegram message object to classify
        
    Returns:
        MediaType enum value as string indicating the primary media type
        
    Media Type Priority (checked in this order):
        1. photo - Static images
        2. video - Video files
        3. document - Generic file attachments
        4. audio - Audio files
        5. voice - Voice messages
        6. video_note - Circular video messages
        7. sticker - Stickers (including animated)
        8. animation - GIF animations
        9. location - Location sharing
        10. contact - Contact cards
        11. poll - Polls
        12. venue - Venue information
        13. dice - Dice/slot machine animations
        14. game - Telegram games
        15. text - Plain text messages (default for messages with text/caption)
        16. other - Unknown or unsupported types
        
    Note:
        Messages can have multiple types (e.g., photo with caption),
        but we return only the primary media type.
    """
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

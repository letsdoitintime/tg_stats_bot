"""Tests for message feature extraction."""

import pytest
from unittest.mock import Mock

from tgstats.utils.features import extract_message_features, get_media_type_from_message
from tgstats.enums import MediaType


class TestExtractMessageFeatures:
    """Test message feature extraction functions."""

    def test_text_message_with_text_storage(self):
        """Test feature extraction from text message with text storage enabled."""
        # Create mock message
        message = Mock()
        message.text = "Hello! This is a test message with https://example.com and 😀😊"
        message.caption = None

        text_raw, text_len, urls_cnt, emoji_cnt = extract_message_features(message, store_text=True)

        assert text_raw == "Hello! This is a test message with https://example.com and 😀😊"
        assert text_len == 63
        assert urls_cnt == 1
        assert emoji_cnt == 2

    def test_text_message_without_text_storage(self):
        """Test feature extraction from text message with text storage disabled."""
        message = Mock()
        message.text = "Hello! This is a test message with https://example.com and 😀😊"
        message.caption = None

        text_raw, text_len, urls_cnt, emoji_cnt = extract_message_features(
            message, store_text=False
        )

        assert text_raw is None
        assert text_len == 63
        assert urls_cnt == 1
        assert emoji_cnt == 2

    def test_caption_message(self):
        """Test feature extraction from message with caption."""
        message = Mock()
        message.text = None
        message.caption = "Photo caption with 🎉 emoji and https://test.com link"

        text_raw, text_len, urls_cnt, emoji_cnt = extract_message_features(message, store_text=True)

        assert text_raw == "Photo caption with 🎉 emoji and https://test.com link"
        assert text_len == 54
        assert urls_cnt == 1
        assert emoji_cnt == 1

    def test_empty_message(self):
        """Test feature extraction from empty message."""
        message = Mock()
        message.text = None
        message.caption = None

        text_raw, text_len, urls_cnt, emoji_cnt = extract_message_features(message, store_text=True)

        assert text_raw == ""
        assert text_len == 0
        assert urls_cnt == 0
        assert emoji_cnt == 0

    def test_multiple_urls(self):
        """Test URL counting with multiple URLs."""
        message = Mock()
        message.text = "Check out https://example.com and http://test.org/path?param=value"
        message.caption = None

        _, text_len, urls_cnt, emoji_cnt = extract_message_features(message)

        assert urls_cnt == 2

    def test_multiple_emojis(self):
        """Test emoji counting with multiple emojis."""
        message = Mock()
        message.text = "🎉🎊🔥💯⚡🌟"
        message.caption = None

        _, text_len, urls_cnt, emoji_cnt = extract_message_features(message)

        assert emoji_cnt == 6


class TestGetMediaTypeFromMessage:
    """Test media type detection from messages."""

    def test_text_message(self):
        """Test text message type detection."""
        message = Mock()
        message.photo = None
        message.video = None
        message.document = None
        message.audio = None
        message.voice = None
        message.video_note = None
        message.sticker = None
        message.animation = None
        message.location = None
        message.contact = None
        message.poll = None
        message.venue = None
        message.dice = None
        message.game = None
        message.text = "Hello"
        message.caption = None

        media_type = get_media_type_from_message(message)
        assert media_type == MediaType.TEXT

    def test_photo_message(self):
        """Test photo message type detection."""
        message = Mock()
        message.photo = [Mock()]  # Photo is a list
        message.video = None
        message.document = None
        message.audio = None
        message.voice = None
        message.video_note = None
        message.sticker = None
        message.animation = None
        message.location = None
        message.contact = None
        message.poll = None
        message.venue = None
        message.dice = None
        message.game = None
        message.text = None
        message.caption = "Photo caption"

        media_type = get_media_type_from_message(message)
        assert media_type == MediaType.PHOTO

    def test_video_message(self):
        """Test video message type detection."""
        message = Mock()
        message.photo = None
        message.video = Mock()
        message.document = None
        message.audio = None
        message.voice = None
        message.video_note = None
        message.sticker = None
        message.animation = None
        message.location = None
        message.contact = None
        message.poll = None
        message.venue = None
        message.dice = None
        message.game = None
        message.text = None
        message.caption = None

        media_type = get_media_type_from_message(message)
        assert media_type == MediaType.VIDEO

    def test_unknown_message(self):
        """Test unknown message type detection."""
        message = Mock()
        message.photo = None
        message.video = None
        message.document = None
        message.audio = None
        message.voice = None
        message.video_note = None
        message.sticker = None
        message.animation = None
        message.location = None
        message.contact = None
        message.poll = None
        message.venue = None
        message.dice = None
        message.game = None
        message.text = None
        message.caption = None

        media_type = get_media_type_from_message(message)
        assert media_type == MediaType.OTHER

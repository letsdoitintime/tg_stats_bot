"""Comprehensive tests for service layer."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from tgstats.services.factory import ServiceFactory
from tgstats.models import Chat, User, Message
from tgstats.enums import ChatType


@pytest.mark.asyncio
class TestChatService:
    """Test ChatService functionality."""

    async def test_get_or_create_chat_new(self, test_session):
        """Test creating a new chat."""
        from telegram import Chat as TelegramChat

        telegram_chat = Mock(spec=TelegramChat)
        telegram_chat.id = 123456
        telegram_chat.title = "Test Group"
        telegram_chat.type = "group"
        telegram_chat.username = None

        services = ServiceFactory(test_session)
        chat = await services.chat.get_or_create_chat(telegram_chat)
        await test_session.commit()

        assert chat.chat_id == 123456
        assert chat.title == "Test Group"

    async def test_setup_chat_creates_settings(self, test_session):
        """Test setup_chat creates default settings."""
        # Create chat first
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        test_session.add(chat)
        await test_session.commit()

        services = ServiceFactory(test_session)
        settings = await services.chat.setup_chat(123)
        await test_session.commit()

        assert settings is not None
        assert settings.chat_id == 123
        assert settings.store_text is False
        assert settings.timezone == "UTC"

    async def test_update_text_storage(self, test_session):
        """Test updating text storage setting."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        test_session.add(chat)
        await test_session.commit()

        services = ServiceFactory(test_session)
        await services.chat.setup_chat(123)

        # Update setting
        updated = await services.chat.update_text_storage(123, True)
        await test_session.commit()

        assert updated is not None
        assert updated.store_text is True


@pytest.mark.asyncio
class TestUserService:
    """Test UserService functionality."""

    async def test_handle_user_join(self, test_session):
        """Test handling user join."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user = User(user_id=456, first_name="Test")
        test_session.add_all([chat, user])
        await test_session.commit()

        services = ServiceFactory(test_session)
        join_time = datetime.now(timezone.utc)
        membership = await services.user.handle_user_join(123, 456, join_time)
        await test_session.commit()

        assert membership is not None
        assert membership.chat_id == 123
        assert membership.user_id == 456

    async def test_handle_user_leave(self, test_session):
        """Test handling user leave."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user = User(user_id=456, first_name="Test")
        test_session.add_all([chat, user])
        await test_session.commit()

        services = ServiceFactory(test_session)

        # User joins first
        join_time = datetime.now(timezone.utc)
        await services.user.handle_user_join(123, 456, join_time)

        # User leaves
        leave_time = datetime.now(timezone.utc)
        membership = await services.user.handle_user_leave(123, 456, leave_time)
        await test_session.commit()

        assert membership is not None
        assert membership.left_at is not None


@pytest.mark.asyncio
class TestMessageService:
    """Test MessageService functionality."""

    async def test_process_message(self, test_session):
        """Test processing a Telegram message."""
        from telegram import Chat as TelegramChat, User as TelegramUser

        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user = User(user_id=456, first_name="Test")
        test_session.add_all([chat, user])
        await test_session.commit()

        # Mock Telegram message
        telegram_msg = Mock()
        telegram_msg.chat = Mock(spec=TelegramChat)
        telegram_msg.chat.id = 123
        telegram_msg.message_id = 789
        telegram_msg.from_user = Mock(spec=TelegramUser)
        telegram_msg.from_user.id = 456
        telegram_msg.date = datetime.now(timezone.utc)
        telegram_msg.text = "Test message"
        telegram_msg.edit_date = None
        telegram_msg.forward_from = None
        telegram_msg.forward_from_chat = None
        telegram_msg.reply_to_message = None
        telegram_msg.entities = None
        telegram_msg.caption_entities = None
        telegram_msg.photo = None
        telegram_msg.video = None
        telegram_msg.document = None
        telegram_msg.audio = None
        telegram_msg.voice = None
        telegram_msg.animation = None
        telegram_msg.sticker = None

        services = ServiceFactory(test_session)
        message = await services.message.process_message(telegram_msg)
        await test_session.commit()

        assert message is not None
        assert message.chat_id == 123
        assert message.msg_id == 789


@pytest.mark.asyncio
class TestReactionService:
    """Test ReactionService functionality."""

    async def test_process_reaction_added(self, test_session):
        """Test processing reaction addition."""
        from telegram import Chat as TelegramChat, User as TelegramUser

        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user = User(user_id=456, first_name="Test")
        message = Message(
            chat_id=123, msg_id=789, user_id=456, date=datetime.now(timezone.utc), text_len=0
        )
        test_session.add_all([chat, user, message])
        await test_session.commit()

        # Mock reaction update
        reaction_update = Mock()
        reaction_update.chat = Mock(spec=TelegramChat)
        reaction_update.chat.id = 123
        reaction_update.message_id = 789
        reaction_update.user = Mock(spec=TelegramUser)
        reaction_update.user.id = 456
        reaction_update.date = datetime.now(timezone.utc)

        # Mock new reactions
        new_reaction = Mock()
        new_reaction.emoji = "👍"
        reaction_update.new_reaction = [new_reaction]
        reaction_update.old_reaction = []

        services = ServiceFactory(test_session)
        reactions = await services.reaction.process_reaction_update(reaction_update)
        await test_session.commit()

        assert len(reactions) > 0

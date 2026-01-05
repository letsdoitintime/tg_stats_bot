"""Comprehensive tests for repository layer."""

from datetime import datetime, timezone

import pytest

from tgstats.enums import ChatType, MediaType, MembershipStatus
from tgstats.models import Chat, Message, User
from tgstats.repositories.factory import RepositoryFactory


@pytest.mark.asyncio
class TestChatRepository:
    """Test ChatRepository functionality."""

    async def test_get_by_chat_id(self, test_session):
        """Test getting chat by chat_id."""
        # Create test chat
        chat = Chat(chat_id=123456, title="Test Chat", type=ChatType.GROUP)
        test_session.add(chat)
        await test_session.commit()

        # Test retrieval
        repo_factory = RepositoryFactory(test_session)
        result = await repo_factory.chat.get_by_chat_id(123456)

        assert result is not None
        assert result.chat_id == 123456
        assert result.title == "Test Chat"

    async def test_get_by_chat_id_not_found(self, test_session):
        """Test getting non-existent chat."""
        repo_factory = RepositoryFactory(test_session)
        result = await repo_factory.chat.get_by_chat_id(999999)

        assert result is None

    async def test_get_all_chats(self, test_session):
        """Test getting all chats with pagination."""
        # Create multiple chats
        for i in range(5):
            chat = Chat(chat_id=100 + i, title=f"Chat {i}", type=ChatType.GROUP)
            test_session.add(chat)
        await test_session.commit()

        # Test retrieval
        repo_factory = RepositoryFactory(test_session)
        result = await repo_factory.chat.get_all(skip=0, limit=3)

        assert len(result) == 3


@pytest.mark.asyncio
class TestUserRepository:
    """Test UserRepository functionality."""

    async def test_get_or_create_user_new(self, test_session):
        """Test creating a new user."""
        from telegram import User as TelegramUser

        telegram_user = TelegramUser(
            id=12345, first_name="Test", last_name="User", username="testuser", is_bot=False
        )

        repo_factory = RepositoryFactory(test_session)
        user = await repo_factory.user.get_or_create_user(telegram_user)
        await test_session.commit()

        assert user.user_id == 12345
        assert user.first_name == "Test"
        assert user.username == "testuser"

    async def test_get_or_create_user_existing(self, test_session):
        """Test getting existing user."""
        # Create existing user
        existing = User(user_id=12345, first_name="Test", username="testuser")
        test_session.add(existing)
        await test_session.commit()

        from telegram import User as TelegramUser

        telegram_user = TelegramUser(
            id=12345, first_name="Updated", username="testuser", is_bot=False
        )

        repo_factory = RepositoryFactory(test_session)
        user = await repo_factory.user.get_or_create_user(telegram_user)

        # Should update existing user
        assert user.user_id == 12345
        assert user.first_name == "Updated"


@pytest.mark.asyncio
class TestMessageRepository:
    """Test MessageRepository functionality."""

    async def test_create_message(self, test_session):
        """Test creating a message."""
        # Create required chat and user
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user = User(user_id=456, first_name="Test")
        test_session.add_all([chat, user])
        await test_session.commit()

        repo_factory = RepositoryFactory(test_session)
        message = await repo_factory.message.create(
            chat_id=123,
            msg_id=789,
            user_id=456,
            date=datetime.now(timezone.utc),
            text_raw="Test message",
            text_len=12,
            media_type=MediaType.TEXT,
        )
        await test_session.commit()

        assert message.chat_id == 123
        assert message.msg_id == 789
        assert message.text_raw == "Test message"

    async def test_get_message_by_composite_key(self, test_session):
        """Test getting message by composite primary key."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user = User(user_id=456, first_name="Test")
        message = Message(
            chat_id=123,
            msg_id=789,
            user_id=456,
            date=datetime.now(timezone.utc),
            text_raw="Test",
            text_len=4,
        )
        test_session.add_all([chat, user, message])
        await test_session.commit()

        # Test retrieval
        repo_factory = RepositoryFactory(test_session)
        result = await repo_factory.message.get_by_pk(chat_id=123, msg_id=789)

        assert result is not None
        assert result.chat_id == 123
        assert result.msg_id == 789


@pytest.mark.asyncio
class TestMembershipRepository:
    """Test MembershipRepository functionality."""

    async def test_get_or_create_membership(self, test_session):
        """Test membership creation."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user = User(user_id=456, first_name="Test")
        test_session.add_all([chat, user])
        await test_session.commit()

        repo_factory = RepositoryFactory(test_session)
        membership = await repo_factory.membership.get_or_create(
            chat_id=123,
            user_id=456,
            status_current=MembershipStatus.MEMBER,
            joined_at=datetime.now(timezone.utc),
        )
        await test_session.commit()

        assert membership.chat_id == 123
        assert membership.user_id == 456
        assert membership.status_current == MembershipStatus.MEMBER


@pytest.mark.asyncio
class TestReactionRepository:
    """Test ReactionRepository functionality."""

    async def test_create_reaction(self, test_session):
        """Test reaction creation."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user = User(user_id=456, first_name="Test")
        message = Message(
            chat_id=123, msg_id=789, user_id=456, date=datetime.now(timezone.utc), text_len=0
        )
        test_session.add_all([chat, user, message])
        await test_session.commit()

        repo_factory = RepositoryFactory(test_session)
        reaction = await repo_factory.reaction.create(
            chat_id=123,
            msg_id=789,
            user_id=456,
            reaction_emoji="👍",
            is_big=False,
            date=datetime.now(timezone.utc),
        )
        await test_session.commit()

        assert reaction.reaction_emoji == "👍"
        assert reaction.chat_id == 123


@pytest.mark.asyncio
class TestGroupSettingsRepository:
    """Test GroupSettingsRepository functionality."""

    async def test_create_default_settings(self, test_session):
        """Test creating default group settings."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        test_session.add(chat)
        await test_session.commit()

        repo_factory = RepositoryFactory(test_session)
        settings = await repo_factory.settings.create(
            chat_id=123, store_text=False, capture_reactions=False
        )
        await test_session.commit()

        assert settings.chat_id == 123
        assert settings.store_text is False
        assert settings.timezone == "UTC"

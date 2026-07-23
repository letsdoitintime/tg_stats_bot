"""Comprehensive tests for service layer."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from conftest import make_tg_chat, make_tg_message, make_tg_user  # tests/ is not a package
from sqlalchemy import select

from tgstats.enums import ChatType
from tgstats.models import Chat, Message, Reaction, User
from tgstats.services.factory import ServiceFactory


@pytest.mark.asyncio
class TestChatService:
    """Test ChatService functionality."""

    async def test_get_or_create_chat_new(self, test_session):
        """Test creating a new chat."""
        # Mock(spec=TelegramChat) still auto-creates each attribute as a Mock,
        # so is_forum/has_protected_content reached SQLAlchemy's Boolean as
        # Mock objects. The shared builder gives every mapped column a real value.
        telegram_chat = make_tg_chat(id=123456, title="Test Group", type="group", username=None)

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
        # Literals, deliberately — setup_chat builds the row from these same
        # constants, so asserting against them is a tautology. This asserted
        # False while the product default is True.
        assert settings.store_text is True
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
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user = User(user_id=456, first_name="Test")
        test_session.add_all([chat, user])
        await test_session.commit()

        # The long hand-rolled mock below missed `chat.type`, so ChatType(...)
        # got a Mock. The shared builder covers every field the ORM writes.
        telegram_msg = make_tg_message(
            message_id=789,
            date=datetime.now(timezone.utc),
            chat=make_tg_chat(id=123, title="Test", type="group"),
            from_user=make_tg_user(id=456, first_name="Test"),
        )

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
        """Reaction updates are persisted when the chat opts in.

        This previously asserted `len(reactions) > 0` on the return value of
        process_reaction_update, which is declared `-> None` and returns
        nothing — the assertion could never have passed. It also never enabled
        capture_reactions, so the method returned early before doing any work.
        Now it enables the setting and asserts the row that actually lands.
        """
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user = User(user_id=456, first_name="Test")
        message = Message(
            chat_id=123, msg_id=789, user_id=456, date=datetime.now(timezone.utc), text_len=0
        )
        test_session.add_all([chat, user, message])
        await test_session.commit()

        services = ServiceFactory(test_session)
        await services.chat.setup_chat(123)
        await services.chat.update_reaction_capture(123, capture_reactions=True)
        await test_session.commit()

        new_reaction = Mock()
        new_reaction.emoji = "👍"
        new_reaction.is_big = False
        reaction_update = Mock()
        reaction_update.chat = make_tg_chat(id=123, title="Test", type="group")
        reaction_update.message_id = 789
        reaction_update.user = make_tg_user(id=456, first_name="Test")
        reaction_update.date = datetime.now(timezone.utc)
        reaction_update.new_reaction = [new_reaction]
        reaction_update.old_reaction = []

        await services.reaction.process_reaction_update(reaction_update)
        await test_session.commit()

        stored = (
            (
                await test_session.execute(
                    select(Reaction).where(Reaction.chat_id == 123, Reaction.msg_id == 789)
                )
            )
            .scalars()
            .all()
        )
        assert [r.reaction_emoji for r in stored] == ["👍"]
        assert stored[0].removed_at is None

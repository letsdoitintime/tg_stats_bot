"""Tests for database common helper functions."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from tgstats.enums import ChatType, MembershipStatus
from tgstats.handlers.common import ensure_membership, upsert_chat, upsert_user
from tgstats.models import Chat, Membership, User


class TestUpsertChat:
    """Test chat upsert functionality."""

    @pytest.mark.asyncio
    async def test_create_new_chat(self, test_session):
        """Test creating a new chat."""
        # Create mock Telegram chat
        tg_chat = Mock()
        tg_chat.id = -1001234567890
        tg_chat.title = "Test Group"
        tg_chat.username = "testgroup"
        tg_chat.type = "supergroup"
        tg_chat.is_forum = False

        # Upsert chat
        chat = await upsert_chat(test_session, tg_chat)

        assert chat.chat_id == -1001234567890
        assert chat.title == "Test Group"
        assert chat.username == "testgroup"
        assert chat.type == ChatType.SUPERGROUP
        assert chat.is_forum is False

    @pytest.mark.asyncio
    async def test_update_existing_chat(self, test_session):
        """Test updating an existing chat."""
        # Create initial chat
        tg_chat = Mock()
        tg_chat.id = -1001234567890
        tg_chat.title = "Old Title"
        tg_chat.username = "oldusername"
        tg_chat.type = "supergroup"
        tg_chat.is_forum = False

        chat1 = await upsert_chat(test_session, tg_chat)

        # Update chat with new info
        tg_chat.title = "New Title"
        tg_chat.username = "newusername"

        chat2 = await upsert_chat(test_session, tg_chat)

        # Should be the same chat with updated info
        assert chat2.chat_id == chat1.chat_id
        assert chat2.title == "New Title"
        assert chat2.username == "newusername"


class TestUpsertUser:
    """Test user upsert functionality."""

    @pytest.mark.asyncio
    async def test_create_new_user(self, test_session):
        """Test creating a new user."""
        # Create mock Telegram user
        tg_user = Mock()
        tg_user.id = 123456789
        tg_user.username = "testuser"
        tg_user.first_name = "Test"
        tg_user.last_name = "User"
        tg_user.is_bot = False
        tg_user.language_code = "en"

        # Upsert user
        user = await upsert_user(test_session, tg_user)

        assert user.user_id == 123456789
        assert user.username == "testuser"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.is_bot is False
        assert user.language_code == "en"

    @pytest.mark.asyncio
    async def test_update_existing_user(self, test_session):
        """Test updating an existing user."""
        # Create initial user
        tg_user = Mock()
        tg_user.id = 123456789
        tg_user.username = "oldusername"
        tg_user.first_name = "Old"
        tg_user.last_name = "Name"
        tg_user.is_bot = False
        tg_user.language_code = "en"

        user1 = await upsert_user(test_session, tg_user)

        # Update user with new info
        tg_user.username = "newusername"
        tg_user.first_name = "New"
        tg_user.last_name = "Name"

        user2 = await upsert_user(test_session, tg_user)

        # Should be the same user with updated info
        assert user2.user_id == user1.user_id
        assert user2.username == "newusername"
        assert user2.first_name == "New"


class TestEnsureMembership:
    """Test membership creation functionality."""

    @pytest.mark.asyncio
    async def test_create_new_membership(self, test_session):
        """Test creating a new membership."""
        # Create chat and user first
        tg_chat = Mock()
        tg_chat.id = -1001234567890
        tg_chat.title = "Test Group"
        tg_chat.username = None
        tg_chat.type = "supergroup"
        tg_chat.is_forum = False

        tg_user = Mock()
        tg_user.id = 123456789
        tg_user.username = "testuser"
        tg_user.first_name = "Test"
        tg_user.last_name = "User"
        tg_user.is_bot = False
        tg_user.language_code = "en"

        await upsert_chat(test_session, tg_chat)
        await upsert_user(test_session, tg_user)

        # Create membership
        join_time = datetime.utcnow()
        membership = await ensure_membership(
            test_session, tg_chat.id, tg_user.id, join_time, MembershipStatus.MEMBER
        )

        assert membership.chat_id == tg_chat.id
        assert membership.user_id == tg_user.id
        assert membership.joined_at == join_time
        assert membership.status_current == MembershipStatus.MEMBER
        assert membership.left_at is None

    @pytest.mark.asyncio
    async def test_existing_membership_not_duplicated(self, test_session):
        """Test that existing membership is not duplicated."""
        # Create chat and user first
        tg_chat = Mock()
        tg_chat.id = -1001234567890
        tg_chat.title = "Test Group"
        tg_chat.username = None
        tg_chat.type = "supergroup"
        tg_chat.is_forum = False

        tg_user = Mock()
        tg_user.id = 123456789
        tg_user.username = "testuser"
        tg_user.first_name = "Test"
        tg_user.last_name = "User"
        tg_user.is_bot = False
        tg_user.language_code = "en"

        await upsert_chat(test_session, tg_chat)
        await upsert_user(test_session, tg_user)

        # Create first membership
        join_time1 = datetime.utcnow()
        membership1 = await ensure_membership(
            test_session, tg_chat.id, tg_user.id, join_time1, MembershipStatus.MEMBER
        )

        # Try to create another membership
        join_time2 = datetime.utcnow()
        membership2 = await ensure_membership(
            test_session, tg_chat.id, tg_user.id, join_time2, MembershipStatus.ADMINISTRATOR
        )

        # Should return the same membership (existing one)
        assert membership1.chat_id == membership2.chat_id
        assert membership1.user_id == membership2.user_id
        assert membership1.joined_at == membership2.joined_at  # Original join time preserved

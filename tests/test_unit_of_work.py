"""Tests for Unit of Work pattern."""

import pytest
from datetime import datetime, timezone

from tgstats.repositories.unit_of_work import UnitOfWork
from tgstats.services.factory import ServiceFactory
from tgstats.models import Chat, User
from tgstats.enums import ChatType


@pytest.mark.asyncio
class TestUnitOfWork:
    """Test Unit of Work pattern."""

    async def test_uow_commits_on_success(self, test_session):
        """Test that UoW commits on successful completion."""
        async with UnitOfWork(test_session) as uow:
            # Create entities
            chat = await uow.repos.chat.create(chat_id=123, title="Test Chat", type=ChatType.GROUP)
            user = await uow.repos.user.create(user_id=456, first_name="Test User")

        # Verify data persisted after context exit
        result_chat = await uow.repos.chat.get_by_chat_id(123)
        result_user = await uow.repos.user.get_by_pk(user_id=456)

        assert result_chat is not None
        assert result_user is not None

    async def test_uow_rollback_on_exception(self, test_session):
        """Test that UoW rolls back on exception."""
        try:
            async with UnitOfWork(test_session) as uow:
                # Create entity
                await uow.repos.chat.create(chat_id=123, title="Test Chat", type=ChatType.GROUP)
                # Raise exception before commit
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Verify data was not persisted
        uow2 = UnitOfWork(test_session)
        result = await uow2.repos.chat.get_by_chat_id(123)
        assert result is None

    async def test_uow_provides_services(self, test_session):
        """Test that UoW provides access to services."""
        from telegram import Chat as TelegramChat

        telegram_chat = TelegramChat(id=123, type="group", title="Test")
        telegram_chat.username = None

        async with UnitOfWork(test_session) as uow:
            # Use services through UoW
            chat = await uow.services.chat.get_or_create_chat(telegram_chat)
            settings = await uow.services.chat.setup_chat(123)

        assert chat is not None
        assert settings is not None

    async def test_uow_manual_commit(self, test_session):
        """Test manual commit within UoW."""
        async with UnitOfWork(test_session) as uow:
            await uow.repos.chat.create(chat_id=123, title="Test", type=ChatType.GROUP)
            await uow.commit()

            # Should be visible after manual commit
            result = await uow.repos.chat.get_by_chat_id(123)
            assert result is not None

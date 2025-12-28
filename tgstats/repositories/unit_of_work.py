"""Unit of Work pattern for managing database transactions."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.factory import RepositoryFactory
from ..services.factory import ServiceFactory


class UnitOfWork:
    """
    Unit of Work pattern implementation for managing database transactions.

    Usage:
        async with UnitOfWork(session) as uow:
            chat = await uow.services.chat.get_or_create_chat(telegram_chat)
            await uow.services.message.process_message(message)
            # Auto-commits on successful exit
            # Auto-rollback on exception
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize Unit of Work.

        Args:
            session: Database session to manage
        """
        self.session = session
        self._repos: Optional[RepositoryFactory] = None
        self._services: Optional[ServiceFactory] = None
        self._committed = False

    @property
    def repos(self) -> RepositoryFactory:
        """Get repository factory."""
        if self._repos is None:
            self._repos = RepositoryFactory(self.session)
        return self._repos

    @property
    def services(self) -> ServiceFactory:
        """Get service factory."""
        if self._services is None:
            self._services = ServiceFactory(self.session)
        return self._services

    async def __aenter__(self) -> "UnitOfWork":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exit async context manager.

        Commits transaction on success, rollback on exception.
        """
        if exc_type is not None:
            # Exception occurred, rollback
            await self.rollback()
            return False
        else:
            # Success, commit
            await self.commit()
            return True

    async def commit(self) -> None:
        """Commit the transaction."""
        if not self._committed:
            await self.session.commit()
            self._committed = True

    async def rollback(self) -> None:
        """Rollback the transaction."""
        await self.session.rollback()
        self._committed = False

    async def flush(self) -> None:
        """Flush pending changes without committing."""
        await self.session.flush()

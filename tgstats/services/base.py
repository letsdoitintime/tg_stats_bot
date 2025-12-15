"""Base service class for common service patterns."""

from abc import ABC
from typing import TYPE_CHECKING

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from ..repositories.factory import RepositoryFactory

logger = structlog.get_logger(__name__)


class BaseService(ABC):
    """Base service class with common functionality."""
    
    def __init__(self, session: AsyncSession, repo_factory: "RepositoryFactory" = None):
        """
        Initialize base service.
        
        Args:
            session: Database session
            repo_factory: Optional repository factory (created if not provided)
        """
        self.session = session
        
        if repo_factory is None:
            from ..repositories.factory import RepositoryFactory
            repo_factory = RepositoryFactory(session)
        
        self.repos = repo_factory
        self.logger = structlog.get_logger(self.__class__.__name__)
    
    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.session.commit()
        self.logger.debug("Transaction committed")
    
    async def rollback(self) -> None:
        """Rollback the current transaction."""
        await self.session.rollback()
        self.logger.debug("Transaction rolled back")
    
    async def flush(self) -> None:
        """Flush pending changes without committing."""
        await self.session.flush()

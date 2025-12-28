"""Service factory for dependency injection."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.factory import RepositoryFactory
from .chat_service import ChatService
from .message_service import MessageService
from .user_service import UserService
from .reaction_service import ReactionService


class ServiceFactory:
    """Factory for creating service instances with shared session and repositories."""

    def __init__(self, session: AsyncSession):
        """
        Initialize service factory.

        Args:
            session: Database session to use for all services
        """
        self.session = session
        self.repos = RepositoryFactory(session)

        # Cache service instances
        self._chat_service: Optional[ChatService] = None
        self._message_service: Optional[MessageService] = None
        self._user_service: Optional[UserService] = None
        self._reaction_service: Optional[ReactionService] = None

    @property
    def chat(self) -> ChatService:
        """Get or create chat service."""
        if self._chat_service is None:
            self._chat_service = ChatService(self.session, self.repos)
        return self._chat_service

    @property
    def message(self) -> MessageService:
        """Get or create message service."""
        if self._message_service is None:
            self._message_service = MessageService(self.session, self.repos)
        return self._message_service

    @property
    def user(self) -> UserService:
        """Get or create user service."""
        if self._user_service is None:
            self._user_service = UserService(self.session, self.repos)
        return self._user_service

    @property
    def reaction(self) -> ReactionService:
        """Get or create reaction service."""
        if self._reaction_service is None:
            self._reaction_service = ReactionService(self.session, self.repos)
        return self._reaction_service

"""Repository factory for dependency injection."""

from sqlalchemy.ext.asyncio import AsyncSession

from .chat_repository import ChatRepository
from .user_repository import UserRepository
from .message_repository import MessageRepository
from .membership_repository import MembershipRepository
from .reaction_repository import ReactionRepository


class RepositoryFactory:
    """Factory for creating repository instances with shared session."""
    
    def __init__(self, session: AsyncSession):
        """
        Initialize repository factory.
        
        Args:
            session: Database session to use for all repositories
        """
        self.session = session
        self._chat_repo = None
        self._user_repo = None
        self._message_repo = None
        self._membership_repo = None
        self._reaction_repo = None
    
    @property
    def chat(self) -> ChatRepository:
        """Get or create chat repository."""
        if self._chat_repo is None:
            self._chat_repo = ChatRepository(self.session)
        return self._chat_repo
    
    @property
    def user(self) -> UserRepository:
        """Get or create user repository."""
        if self._user_repo is None:
            self._user_repo = UserRepository(self.session)
        return self._user_repo
    
    @property
    def message(self) -> MessageRepository:
        """Get or create message repository."""
        if self._message_repo is None:
            self._message_repo = MessageRepository(self.session)
        return self._message_repo
    
    @property
    def membership(self) -> MembershipRepository:
        """Get or create membership repository."""
        if self._membership_repo is None:
            self._membership_repo = MembershipRepository(self.session)
        return self._membership_repo
    
    @property
    def reaction(self) -> ReactionRepository:
        """Get or create reaction repository."""
        if self._reaction_repo is None:
            self._reaction_repo = ReactionRepository(self.session)
        return self._reaction_repo

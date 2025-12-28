"""User management service."""

import structlog
from typing import Optional, TYPE_CHECKING
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import User as TelegramUser

from ..models import User, Membership
from ..enums import MembershipStatus
from .base import BaseService

if TYPE_CHECKING:
    from ..repositories.factory import RepositoryFactory

logger = structlog.get_logger(__name__)


class UserService(BaseService):
    """Service for user-related operations."""

    def __init__(self, session: AsyncSession, repo_factory: "RepositoryFactory" = None):
        """Initialize user service with database session."""
        super().__init__(session, repo_factory)

    async def get_or_create_user(self, tg_user: TelegramUser) -> User:
        """Get or create a user from Telegram user object."""
        user = await self.repos.user.upsert_from_telegram(tg_user)
        self.logger.info("User upserted", user_id=user.user_id, username=user.username)
        return user

    async def ensure_membership(
        self,
        chat_id: int,
        user_id: int,
        joined_at: Optional[datetime] = None,
        status: MembershipStatus = MembershipStatus.MEMBER,
    ) -> Membership:
        """Ensure a membership exists for a user in a chat."""
        membership = await self.repos.membership.ensure_membership(
            chat_id, user_id, joined_at, status
        )
        return membership

    async def handle_user_join(self, chat_id: int, user_id: int, joined_at: datetime) -> Membership:
        """Handle user joining a chat."""
        existing = await self.repos.membership.get_by_chat_and_user(chat_id, user_id)

        if existing and existing.left_at:
            # User is rejoining
            membership = await self.repos.membership.update_join_status(chat_id, user_id, joined_at)
            self.logger.info("User rejoined", chat_id=chat_id, user_id=user_id)
        else:
            # New membership
            membership = await self.repos.membership.ensure_membership(chat_id, user_id, joined_at)
            self.logger.info("User joined", chat_id=chat_id, user_id=user_id)

        await self.session.commit()
        return membership

    async def handle_user_leave(self, chat_id: int, user_id: int, left_at: datetime) -> Membership:
        """Handle user leaving a chat."""
        membership = await self.repos.membership.update_leave_status(chat_id, user_id, left_at)
        await self.commit()
        self.logger.info("User left", chat_id=chat_id, user_id=user_id)
        return membership

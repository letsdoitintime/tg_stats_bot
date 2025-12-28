"""Membership repository for database operations."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..enums import MembershipStatus
from ..models import Membership
from .base import BaseRepository


class MembershipRepository(BaseRepository[Membership]):
    """Repository for membership-related database operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Membership, session)

    async def get_by_chat_and_user(self, chat_id: int, user_id: int) -> Optional[Membership]:
        """Get membership by chat and user ID."""
        result = await self.session.execute(
            select(Membership).where(Membership.chat_id == chat_id, Membership.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def ensure_membership(
        self,
        chat_id: int,
        user_id: int,
        joined_at_if_missing: Optional[datetime] = None,
        status: MembershipStatus = MembershipStatus.MEMBER,
    ) -> Membership:
        """
        Ensure membership record exists for a user in a chat.

        Args:
            chat_id: Chat ID
            user_id: User ID
            joined_at_if_missing: Datetime to use if membership doesn't exist
            status: Current membership status

        Returns:
            Membership model instance
        """
        # Convert timezone-aware datetime to UTC naive if provided
        if joined_at_if_missing and joined_at_if_missing.tzinfo:
            joined_at_if_missing = joined_at_if_missing.astimezone(timezone.utc).replace(
                tzinfo=None
            )

        membership = await self.get_by_chat_and_user(chat_id, user_id)

        if membership is None:
            membership_data = {
                "chat_id": chat_id,
                "user_id": user_id,
                "joined_at": joined_at_if_missing
                or datetime.now(timezone.utc).replace(tzinfo=None),
                "status_current": status,
            }

            stmt = insert(Membership).values(**membership_data)
            stmt = stmt.on_conflict_do_nothing()

            await self.session.execute(stmt)
            await self.session.flush()

            membership = await self.get_by_chat_and_user(chat_id, user_id)

        return membership

    async def update_join_status(
        self,
        chat_id: int,
        user_id: int,
        joined_at: datetime,
        status: MembershipStatus = MembershipStatus.MEMBER,
    ) -> Membership:
        """Update membership when user joins/rejoins."""
        await self.session.execute(
            update(Membership)
            .where(Membership.chat_id == chat_id, Membership.user_id == user_id)
            .values(joined_at=joined_at, left_at=None, status_current=status)
        )
        await self.session.flush()
        return await self.get_by_chat_and_user(chat_id, user_id)

    async def update_leave_status(
        self,
        chat_id: int,
        user_id: int,
        left_at: datetime,
        status: MembershipStatus = MembershipStatus.LEFT,
    ) -> Membership:
        """Update membership when user leaves."""
        await self.session.execute(
            update(Membership)
            .where(Membership.chat_id == chat_id, Membership.user_id == user_id)
            .values(left_at=left_at, status_current=status)
        )
        await self.session.flush()
        return await self.get_by_chat_and_user(chat_id, user_id)

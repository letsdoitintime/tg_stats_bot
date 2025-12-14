"""Reaction repository for database operations."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Reaction
from .base import BaseRepository


class ReactionRepository(BaseRepository[Reaction]):
    """Repository for reaction-related database operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Reaction, session)
    
    async def get_active_reaction(
        self,
        chat_id: int,
        msg_id: int,
        user_id: Optional[int],
        emoji: str
    ) -> Optional[Reaction]:
        """Get an active (not removed) reaction."""
        result = await self.session.execute(
            select(Reaction).where(
                Reaction.chat_id == chat_id,
                Reaction.msg_id == msg_id,
                Reaction.user_id == user_id,
                Reaction.reaction_emoji == emoji,
                Reaction.removed_at.is_(None)
            )
        )
        return result.scalar_one_or_none()
    
    async def mark_as_removed(
        self,
        chat_id: int,
        msg_id: int,
        user_id: Optional[int],
        emoji: str,
        removed_at: datetime
    ) -> int:
        """
        Mark a reaction as removed.
        
        Returns:
            Number of reactions updated
        """
        result = await self.session.execute(
            update(Reaction)
            .where(
                Reaction.chat_id == chat_id,
                Reaction.msg_id == msg_id,
                Reaction.user_id == user_id,
                Reaction.reaction_emoji == emoji,
                Reaction.removed_at.is_(None)
            )
            .values(removed_at=removed_at)
        )
        await self.session.flush()
        return result.rowcount
    
    async def upsert_reaction(
        self,
        chat_id: int,
        msg_id: int,
        user_id: Optional[int],
        emoji: str,
        is_big: bool,
        date: datetime
    ) -> None:
        """
        Insert or update a reaction.
        
        On conflict (same user, message, emoji), updates the date and clears removed_at.
        """
        # Convert timezone-aware datetime to UTC naive
        if date and date.tzinfo:
            date = date.astimezone(timezone.utc).replace(tzinfo=None)
        
        reaction_data = {
            "chat_id": chat_id,
            "msg_id": msg_id,
            "user_id": user_id,
            "reaction_emoji": emoji,
            "is_big": is_big,
            "date": date,
            "removed_at": None,
        }
        
        stmt = insert(Reaction).values(**reaction_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "chat_id", "msg_id", "reaction_emoji"],
            set_={
                "date": stmt.excluded.date,
                "removed_at": None,
                "is_big": stmt.excluded.is_big,
            }
        )
        
        await self.session.execute(stmt)
        await self.session.flush()

"""User repository for database operations."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import User as TelegramUser

from ..models import User
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for user-related database operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)
    
    async def get_by_user_id(self, user_id: int) -> Optional[User]:
        """Get user by Telegram user ID."""
        result = await self.session.execute(
            select(User).where(User.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def upsert_from_telegram(self, tg_user: TelegramUser) -> User:
        """
        Upsert a user record from Telegram user object.
        
        Args:
            tg_user: Telegram user object
            
        Returns:
            User model instance
        """
        user_data = {
            "user_id": tg_user.id,
            "username": tg_user.username,
            "first_name": tg_user.first_name,
            "last_name": tg_user.last_name,
            "is_bot": tg_user.is_bot,
            "language_code": tg_user.language_code,
            "is_premium": getattr(tg_user, "is_premium", None),
            "added_to_attachment_menu": getattr(tg_user, "added_to_attachment_menu", None),
            "can_join_groups": getattr(tg_user, "can_join_groups", None),
            "can_read_all_group_messages": getattr(tg_user, "can_read_all_group_messages", None),
            "supports_inline_queries": getattr(tg_user, "supports_inline_queries", None),
            "updated_at": datetime.utcnow(),
        }
        
        stmt = insert(User).values(**user_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=[User.user_id],
            set_={
                "username": stmt.excluded.username,
                "first_name": stmt.excluded.first_name,
                "last_name": stmt.excluded.last_name,
                "is_bot": stmt.excluded.is_bot,
                "language_code": stmt.excluded.language_code,
                "is_premium": stmt.excluded.is_premium,
                "added_to_attachment_menu": stmt.excluded.added_to_attachment_menu,
                "can_join_groups": stmt.excluded.can_join_groups,
                "can_read_all_group_messages": stmt.excluded.can_read_all_group_messages,
                "supports_inline_queries": stmt.excluded.supports_inline_queries,
                "updated_at": stmt.excluded.updated_at,
            }
        )
        
        await self.session.execute(stmt)
        await self.session.flush()
        
        return await self.get_by_user_id(tg_user.id)

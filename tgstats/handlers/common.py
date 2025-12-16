"""Common helper functions for database upserts.

⚠️  DEPRECATED: These functions are deprecated and will be removed in v0.3.0.
    Use ChatService, UserService instead of these helper functions.
"""

import warnings
import structlog
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Chat as TelegramChat, User as TelegramUser

from ..models import Chat, User, Membership
from ..enums import ChatType, MembershipStatus

logger = structlog.get_logger(__name__)


async def upsert_chat(session: AsyncSession, tg_chat: TelegramChat) -> Chat:
    """
    Upsert a chat record from Telegram chat object.
    
    .. deprecated:: 0.2.0
        Use :meth:`ChatService.get_or_create_chat` instead.
    
    Args:
        session: Database session
        tg_chat: Telegram chat object
        
    Returns:
        Chat model instance
    """
    warnings.warn(
        "upsert_chat is deprecated, use ChatService.get_or_create_chat instead",
        DeprecationWarning,
        stacklevel=2
    )
    
    chat_data = {
        "chat_id": tg_chat.id,
        "title": tg_chat.title,
        "username": tg_chat.username,
        "type": ChatType(tg_chat.type),
        "is_forum": getattr(tg_chat, "is_forum", False),
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }
    
    # Use PostgreSQL UPSERT
    stmt = insert(Chat).values(**chat_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Chat.chat_id],
        set_={
            "title": stmt.excluded.title,
            "username": stmt.excluded.username,
            "type": stmt.excluded.type,
            "is_forum": stmt.excluded.is_forum,
            "updated_at": stmt.excluded.updated_at,
        }
    )
    
    await session.execute(stmt)
    await session.flush()
    
    # Return the chat object
    result = await session.execute(
        select(Chat).where(Chat.chat_id == tg_chat.id)
    )
    return result.scalar_one()


async def upsert_user(session: AsyncSession, tg_user: TelegramUser) -> User:
    """
    Upsert a user record from Telegram user object.
    
    .. deprecated:: 0.2.0
        Use :meth:`UserService.get_or_create_user` instead.
    
    Args:
        session: Database session
        tg_user: Telegram user object
        
    Returns:
        User model instance
    """
    warnings.warn(
        "upsert_user is deprecated, use UserService.get_or_create_user instead",
        DeprecationWarning,
        stacklevel=2
    )
    
    user_data = {
        "user_id": tg_user.id,
        "username": tg_user.username,
        "first_name": tg_user.first_name,
        "last_name": tg_user.last_name,
        "is_bot": tg_user.is_bot,
        "language_code": tg_user.language_code,
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }
    
    # Use PostgreSQL UPSERT
    stmt = insert(User).values(**user_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=[User.user_id],
        set_={
            "username": stmt.excluded.username,
            "first_name": stmt.excluded.first_name,
            "last_name": stmt.excluded.last_name,
            "is_bot": stmt.excluded.is_bot,
            "language_code": stmt.excluded.language_code,
            "updated_at": stmt.excluded.updated_at,
        }
    )
    
    await session.execute(stmt)
    await session.flush()
    
    # Return the user object
    result = await session.execute(
        select(User).where(User.user_id == tg_user.id)
    )
    return result.scalar_one()


async def ensure_membership(
    session: AsyncSession, 
    chat_id: int, 
    user_id: int, 
    joined_at_if_missing: Optional[datetime] = None,
    status: MembershipStatus = MembershipStatus.MEMBER
) -> Membership:
    """
    Ensure membership record exists for a user in a chat.
    
    .. deprecated:: 0.2.0
        Use :meth:`UserService.ensure_membership` instead.
    
    Args:
        session: Database session
        chat_id: Chat ID
        user_id: User ID
        joined_at_if_missing: Datetime to use if membership doesn't exist
        status: Current membership status
        
    Returns:
        Membership model instance
    """
    warnings.warn(
        "ensure_membership is deprecated, use UserService.ensure_membership instead",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Convert timezone-aware datetime to UTC naive if provided
    if joined_at_if_missing and joined_at_if_missing.tzinfo:
        joined_at_if_missing = joined_at_if_missing.astimezone(timezone.utc).replace(tzinfo=None)
    
    # Check if membership already exists
    result = await session.execute(
        select(Membership).where(
            Membership.chat_id == chat_id,
            Membership.user_id == user_id
        )
    )
    membership = result.scalar_one_or_none()
    
    if membership is None:
        # Create new membership
        membership_data = {
            "chat_id": chat_id,
            "user_id": user_id,
            "joined_at": joined_at_if_missing or datetime.now(timezone.utc).replace(tzinfo=None),
            "status_current": status,
        }
        
        stmt = insert(Membership).values(**membership_data)
        stmt = stmt.on_conflict_do_nothing()
        
        await session.execute(stmt)
        await session.flush()
        
        # Fetch the membership
        result = await session.execute(
            select(Membership).where(
                Membership.chat_id == chat_id,
                Membership.user_id == user_id
            )
        )
        membership = result.scalar_one()
    
    return membership

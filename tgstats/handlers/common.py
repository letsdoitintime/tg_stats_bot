"""Common helper functions for database upserts."""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Chat as TelegramChat, User as TelegramUser

from ..models import Chat, User, Membership
from ..enums import ChatType, MembershipStatus

logger = logging.getLogger(__name__)


async def upsert_chat(session: AsyncSession, tg_chat: TelegramChat) -> Chat:
    """
    Upsert a chat record from Telegram chat object.
    
    Args:
        session: Database session
        tg_chat: Telegram chat object
        
    Returns:
        Chat model instance
    """
    chat_data = {
        "chat_id": tg_chat.id,
        "title": tg_chat.title,
        "username": tg_chat.username,
        "type": ChatType(tg_chat.type),
        "is_forum": getattr(tg_chat, "is_forum", False),
        "updated_at": datetime.utcnow(),
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
    await session.commit()
    
    # Return the chat object
    result = await session.execute(
        select(Chat).where(Chat.chat_id == tg_chat.id)
    )
    return result.scalar_one()


async def upsert_user(session: AsyncSession, tg_user: TelegramUser) -> User:
    """
    Upsert a user record from Telegram user object.
    
    Args:
        session: Database session
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
        "updated_at": datetime.utcnow(),
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
    await session.commit()
    
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
    
    Args:
        session: Database session
        chat_id: Chat ID
        user_id: User ID
        joined_at_if_missing: Datetime to use if membership doesn't exist
        status: Current membership status
        
    Returns:
        Membership model instance
    """
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
            "joined_at": joined_at_if_missing or datetime.utcnow(),
            "status_current": status,
        }
        
        stmt = insert(Membership).values(**membership_data)
        stmt = stmt.on_conflict_do_nothing()
        
        await session.execute(stmt)
        await session.commit()
        
        # Fetch the membership
        result = await session.execute(
            select(Membership).where(
                Membership.chat_id == chat_id,
                Membership.user_id == user_id
            )
        )
        membership = result.scalar_one()
    
    return membership

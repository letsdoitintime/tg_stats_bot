"""Member handlers for tracking user joins/leaves."""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from ..services.factory import ServiceFactory
from ..utils.decorators import with_db_session

logger = structlog.get_logger(__name__)


@with_db_session
async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession) -> None:
    """Handle new members joining the chat."""
    if not update.message or not update.message.new_chat_members:
        return
    
    chat = update.message.chat
    join_date = update.message.date
    
    services = ServiceFactory(session)
    
    # Upsert chat
    await services.chat.get_or_create_chat(chat)
    
    # Process each new member
    for new_user in update.message.new_chat_members:
        # Upsert user
        await services.user.get_or_create_user(new_user)
        
        # Handle join
        await services.user.handle_user_join(chat.id, new_user.id, join_date)
        
        logger.info(
            "Member joined",
            chat_id=chat.id,
            user_id=new_user.id,
            username=new_user.username
        )


@with_db_session
async def handle_left_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession) -> None:
    """Handle member leaving the chat."""
    if not update.message or not update.message.left_chat_member:
        return
    
    chat = update.message.chat
    left_user = update.message.left_chat_member
    leave_date = update.message.date
    
    services = ServiceFactory(session)
    
    # Upsert chat and user
    await services.chat.get_or_create_chat(chat)
    await services.user.get_or_create_user(left_user)
    
    # Handle leave
    await services.user.handle_user_leave(chat.id, left_user.id, leave_date)
    
    logger.info(
        "Member left",
        chat_id=chat.id,
        user_id=left_user.id,
        username=left_user.username
    )


@with_db_session
async def handle_chat_member_updated(update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession) -> None:
    """Handle chat member status updates."""
    if not update.chat_member:
        return
    
    member_update = update.chat_member
    chat = member_update.chat
    user = member_update.new_chat_member.user
    old_status = member_update.old_chat_member.status
    new_status = member_update.new_chat_member.status
    
    logger.info(
        "Chat member updated",
        chat_id=chat.id,
        user_id=user.id,
        old_status=old_status,
        new_status=new_status
    )
    
    # Handle status changes if needed
    # For now, we just log them
    # Future enhancement: Track admin changes, bans, etc.

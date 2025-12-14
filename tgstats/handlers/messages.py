"""Message handlers for the Telegram bot."""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from ..db import async_session
from ..services.message_service import MessageService

logger = structlog.get_logger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all incoming messages and store analytics data."""
    if not update.message:
        return
    
    message = update.message
    
    if not message.from_user:  # Skip messages without user info
        return
    
    async with async_session() as session:
        try:
            service = MessageService(session)
            await service.process_message(message)
            
        except Exception as e:
            logger.error(
                "Error processing message",
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                msg_id=message.message_id,
                error=str(e),
                exc_info=True
            )
            await session.rollback()


async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle edited messages."""
    if not update.edited_message:
        return
    
    # For edited messages, we process them as new messages with edit_date
    # The update object needs to have message set for handle_message
    update.message = update.edited_message
    await handle_message(update, context)

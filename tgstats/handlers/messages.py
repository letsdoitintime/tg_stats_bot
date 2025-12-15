"""Message handlers for the Telegram bot.

This module handles incoming Telegram messages and edited messages,
processing them through the MessageService for storage and analytics.
"""

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from ..db import async_session
from ..services.message_service import MessageService
from ..core.exceptions import DatabaseError

logger = structlog.get_logger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all incoming messages and store analytics data.
    
    Args:
        update: Telegram update object containing the message
        context: Telegram context with bot and user data
        
    Note:
        This handler silently skips messages without user info or message object.
        Errors are logged but don't interrupt bot operation.
    """
    if not update.message:
        logger.debug("Received update without message, skipping")
        return
    
    message = update.message
    
    if not message.from_user:
        logger.debug(
            "Message without user info, skipping",
            chat_id=message.chat.id,
            msg_id=message.message_id
        )
        return
    
    async with async_session() as session:
        try:
            service = MessageService(session)
            await service.process_message(message)
            
        except DatabaseError as e:
            logger.error(
                "Database error processing message",
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                msg_id=message.message_id,
                error=str(e),
                exc_info=True
            )
            await session.rollback()
        except Exception as e:
            logger.error(
                "Unexpected error processing message",
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                msg_id=message.message_id,
                error_type=type(e).__name__,
                error=str(e),
                exc_info=True
            )
            await session.rollback()


async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle edited messages.
    
    Args:
        update: Telegram update object containing the edited message
        context: Telegram context with bot and user data
        
    Note:
        Edited messages are processed as new messages with edit_date set.
        We reuse handle_message by reassigning update.message.
    """
    if not update.edited_message:
        logger.debug("Received update without edited_message, skipping")
        return
    
    logger.debug(
        "Processing edited message",
        chat_id=update.edited_message.chat.id,
        msg_id=update.edited_message.message_id
    )
    
    # Process edited message as a regular message
    update.message = update.edited_message
    await handle_message(update, context)

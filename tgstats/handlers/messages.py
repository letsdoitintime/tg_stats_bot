"""Message handlers for the Telegram bot."""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from ..services.factory import ServiceFactory
from ..utils.decorators import with_db_session

logger = structlog.get_logger(__name__)


@with_db_session
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession) -> None:
    """Handle all incoming messages and store analytics data."""
    if not update.message:
        return
    
    message = update.message
    
    if not message.from_user:  # Skip messages without user info
        return
    
    services = ServiceFactory(session)
    await services.message.process_message(message)


@with_db_session
async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession) -> None:
    """Handle edited messages."""
    if not update.edited_message:
        return
    
    message = update.edited_message
    
    if not message.from_user:  # Skip messages without user info
        return
    
    services = ServiceFactory(session)
    await services.message.process_message(message)

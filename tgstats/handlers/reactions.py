"""Reaction handlers for the Telegram bot."""

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from ..db import async_session
from ..services.reaction_service import ReactionService

logger = structlog.get_logger(__name__)


async def handle_message_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle message reaction updates (reactions added or removed) and reaction count updates."""
    
    logger.debug(
        "Received reaction update",
        has_message_reaction=bool(update.message_reaction),
        has_message_reaction_count=bool(update.message_reaction_count),
        update_type="message_reaction" if update.message_reaction else "message_reaction_count"
    )
    
    # Handle individual reaction updates
    if update.message_reaction:
        await _handle_individual_reaction(update, context)
    
    # Handle reaction count updates (anonymous reactions)
    elif update.message_reaction_count:
        await _handle_reaction_count(update, context)


async def _handle_individual_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle individual message reaction updates (reactions added or removed)."""
    reaction_update = update.message_reaction
    
    async with async_session() as session:
        try:
            service = ReactionService(session)
            await service.process_reaction_update(reaction_update)
            
        except Exception as e:
            logger.error(
                "Error processing reaction",
                chat_id=reaction_update.chat.id if reaction_update.chat else None,
                user_id=reaction_update.user.id if reaction_update.user else None,
                msg_id=reaction_update.message_id,
                error=str(e),
                exc_info=True
            )
            await session.rollback()


async def _handle_reaction_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle message reaction count updates (anonymous reactions)."""
    reaction_count_update = update.message_reaction_count
    chat = reaction_count_update.chat
    
    # For now, just log these - we could implement anonymous reaction tracking later
    logger.info(
        "Reaction count update (anonymous)",
        chat_id=chat.id if chat else None,
        msg_id=reaction_count_update.message_id,
        reactions=len(reaction_count_update.reactions) if reaction_count_update.reactions else 0,
    )
def _extract_emoji_from_reaction(reaction_type) -> str:
    """Extract emoji string from ReactionType object."""
    try:
        # Handle emoji reactions
        if hasattr(reaction_type, 'emoji'):
            emoji = reaction_type.emoji
            logger.debug(f"Extracted emoji: {emoji}")
            return emoji
        
        # Handle custom emoji reactions (stickers)
        elif hasattr(reaction_type, 'custom_emoji_id'):
            custom_id = f"custom:{reaction_type.custom_emoji_id}"
            logger.debug(f"Extracted custom emoji: {custom_id}")
            return custom_id
        
        # Fallback to string representation
        else:
            fallback = str(reaction_type)
            logger.debug(f"Fallback emoji extraction: {fallback}")
            return fallback
            
    except Exception as e:
        logger.warning(
            "Failed to extract emoji from reaction",
            extra={"error": str(e), "reaction_type": str(reaction_type)}
        )
        return str(reaction_type)

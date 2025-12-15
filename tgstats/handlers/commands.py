"""Command handlers for bot configuration and management."""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from ..services.chat_service import ChatService
from ..utils.decorators import group_only, require_admin, with_db_session
from ..utils.validators import parse_boolean_argument
from ..utils.rate_limiter import rate_limiter
from ..utils.sanitizer import sanitize_command_arg, sanitize_text
from ..utils.metrics import metrics, track_time
from ..core.exceptions import ValidationError, ChatNotSetupError
from ..enums import ChatType

logger = structlog.get_logger(__name__)


@track_time("setup_command")
@with_db_session
async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession) -> None:
    """Setup command to initialize chat and create default settings."""
    if not update.effective_chat or not update.message or not update.effective_user:
        return
    
    # Rate limiting
    is_limited, limit_msg = rate_limiter.is_rate_limited(update.effective_user.id)
    if is_limited:
        await update.message.reply_text(limit_msg)
        metrics.increment_commands("setup", "rate_limited")
        return
    
    chat = update.effective_chat
    
    # Only work in groups
    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text(
            "This command can only be used in groups."
        )
        return
    
    # Check if user is admin
    if not await _is_user_admin(update, context):
        await update.message.reply_text(
            "Only administrators can use this command."
        )
        return
    
    service = ChatService(session)
    
    # Create chat and setup settings
    await service.get_or_create_chat(chat)
    settings = await service.setup_chat(chat.id)
    
    settings_text = f"""
📊 **Group Analytics Setup Complete!**

**Current Settings:**
• Store Text: {'✅ Enabled' if settings.store_text else '❌ Disabled'}
• Text Retention: {settings.text_retention_days} days
• Metadata Retention: {settings.metadata_retention_days} days
• Timezone: {settings.timezone}
• Locale: {settings.locale}
• Capture Reactions: {'✅ Enabled' if settings.capture_reactions else '❌ Disabled'}

**Available Commands:**
• `/settings` - View current settings
• `/set_text on|off` - Toggle text storage (admin only)
• `/set_reactions on|off` - Toggle reaction capture (admin only)

The bot is now tracking message analytics for this group!
    """.strip()
    
    await update.message.reply_text(settings_text, parse_mode="Markdown")
    
    logger.info(
        "Group setup completed",
        chat_id=chat.id,
        chat_title=chat.title,
        user_id=update.effective_user.id if update.effective_user else None
    )


@with_db_session
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession) -> None:
    """Show current group settings."""
    if not update.effective_chat or not update.message:
        return
    
    chat = update.effective_chat
    
    # Only work in groups
    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text(
            "This command can only be used in groups."
        )
        return
    
    service = ChatService(session)
    settings = await service.get_chat_settings(chat.id)
    
    if not settings:
        await update.message.reply_text(
            "❌ Group not set up yet. Use /setup to initialize analytics."
        )
        return
    
    settings_text = f"""
📊 **Current Group Settings**

• Store Text: {'✅ Enabled' if settings.store_text else '❌ Disabled'}
• Text Retention: {settings.text_retention_days} days
• Metadata Retention: {settings.metadata_retention_days} days
• Timezone: {settings.timezone}
• Locale: {settings.locale}
• Capture Reactions: {'✅ Enabled' if settings.capture_reactions else '❌ Disabled'}

**Commands:**
• `/set_text on|off` - Toggle text storage (admin only)
• `/set_reactions on|off` - Toggle reaction capture (admin only)
    """.strip()
    
    await update.message.reply_text(settings_text, parse_mode="Markdown")


@with_db_session
async def set_text_command(update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession) -> None:
    """Set text storage setting for the group."""
    if not update.message or not update.message.chat or not update.effective_user:
        return
    
    chat = update.message.chat
    
    # Only works in groups
    if chat.type == "private":
        await update.message.reply_text("❌ This command only works in groups.")
        return
    
    # Check if user is admin
    if not await _is_user_admin(update, context):
        await update.message.reply_text("❌ Only group admins can change settings.")
        return
    
    # Parse argument
    try:
        if not context.args:
            raise ValidationError("Missing argument")
        
        store_text = parse_boolean_argument(context.args[0])
    except ValidationError as e:
        await update.message.reply_text(
            f"❌ {str(e)}\n\nUsage: `/set_text on` or `/set_text off`",
            parse_mode="Markdown"
        )
        return
    
    service = ChatService(session)
    settings = await service.update_text_storage(chat.id, store_text)
    
    if not settings:
        await update.message.reply_text(
            "❌ Please run `/setup` first to initialize group settings.",
            parse_mode="Markdown"
        )
        return
    
    status = "✅ Enabled" if store_text else "❌ Disabled"
    await update.message.reply_text(
        f"📝 Text storage has been **{status}**",
        parse_mode="Markdown"
    )


@with_db_session
async def set_reactions_command(update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession) -> None:
    """Set reaction capture setting for the group."""
    if not update.message or not update.message.chat or not update.effective_user:
        return
    
    chat = update.message.chat
    
    # Only works in groups
    if chat.type == "private":
        await update.message.reply_text("❌ This command only works in groups.")
        return
    
    # Check if user is admin
    if not await _is_user_admin(update, context):
        await update.message.reply_text("❌ Only group admins can change settings.")
        return
    
    # Parse argument
    try:
        if not context.args:
            raise ValidationError("Missing argument")
        
        capture_reactions = parse_boolean_argument(context.args[0])
    except ValidationError as e:
        await update.message.reply_text(
            f"❌ {str(e)}\n\nUsage: `/set_reactions on` or `/set_reactions off`",
            parse_mode="Markdown"
        )
        return
    
    service = ChatService(session)
    settings = await service.update_reaction_capture(chat.id, capture_reactions)
    
    if not settings:
        await update.message.reply_text(
            "❌ Please run `/setup` first to initialize group settings.",
            parse_mode="Markdown"
        )
        return
    
    status = "✅ Enabled" if capture_reactions else "❌ Disabled"
    await update.message.reply_text(
        f"🎭 Reaction capture has been **{status}**",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message with available commands."""
    if not update.message:
        return
    
    help_text = """
🤖 **Telegram Analytics Bot**

This bot tracks message statistics for your group.

**Commands:**
• `/setup` - Initialize analytics for this group (admin only)
• `/settings` - View current group settings
• `/set_text on|off` - Toggle text storage (admin only)
• `/set_reactions on|off` - Toggle reaction capture (admin only)
• `/help` - Show this help message

**Features:**
📊 Message statistics and trends
👥 User activity tracking
📈 Daily/hourly analytics
🎭 Reaction tracking (when enabled)

For more information, visit our documentation.
    """.strip()
    
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def _is_user_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user is an administrator in the chat."""
    if not update.effective_chat or not update.effective_user:
        return False
    
    try:
        chat_administrators = await context.bot.get_chat_administrators(
            update.effective_chat.id
        )
        admin_ids = [admin.user.id for admin in chat_administrators]
        return update.effective_user.id in admin_ids
    except Exception as e:
        logger.error("Error checking admin status", error=str(e))
        return False

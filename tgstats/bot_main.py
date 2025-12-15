"""
Main entry point for the Telegram Analytics Bot.

This bot provides multi-group analytics for Telegram chats with configurable
per-group settings and comprehensive message tracking.

## Running Locally

1. Copy .env.example to .env and fill in your bot token
2. Start PostgreSQL database
3. Run migrations: `alembic upgrade head`
4. Start the bot: `python -m tgstats.bot_main`

## Docker

Use the provided docker-compose.yml:
```bash
docker-compose up --build
```

## Environment Variables

- BOT_TOKEN: Your Telegram bot token from @BotFather
- DATABASE_URL: PostgreSQL connection string
- MODE: 'polling' (default) or 'webhook'
- WEBHOOK_URL: Required only for webhook mode
- LOG_LEVEL: INFO, DEBUG, WARNING, ERROR
"""

import asyncio
import signal
import sys
import traceback

import structlog
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    MessageReactionHandler,
    ChatMemberHandler,
    filters,
)
from telegram.request import HTTPXRequest

from .config import settings
from .utils.logging import setup_logging, configure_third_party_logging
from .handlers.commands import (
    setup_command,
    settings_command,
    set_text_command,
    set_reactions_command,
    help_command,
)
from .handlers.messages import handle_message, handle_edited_message
from .handlers.reactions import handle_message_reaction
from .handlers.members import (
    handle_new_chat_members,
    handle_left_chat_member,
    handle_chat_member_updated,
)
from .plugins import PluginManager

# Configure logging
setup_logging(
    log_level=settings.log_level,
    log_to_file=settings.log_to_file,
    log_file_path=settings.log_file_path,
    log_file_max_bytes=settings.log_file_max_bytes,
    log_file_backup_count=settings.log_file_backup_count,
    log_format=settings.log_format
)
configure_third_party_logging(
    settings.telegram_log_level, 
    settings.httpx_log_level,
    settings.uvicorn_log_level
)

logger = structlog.get_logger(__name__)

# Global plugin manager
plugin_manager = PluginManager()


async def run_migrations():
    """Run database migrations."""
    logger.info("Running database migrations...")
    try:
        # Import here to avoid circular dependencies
        from alembic.config import Config
        from alembic import command
        import os
        
        # Get the directory containing this file
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alembic_cfg = Config(os.path.join(base_dir, "alembic.ini"))
        
        # Set the script location
        alembic_cfg.set_main_option("script_location", os.path.join(base_dir, "migrations"))
        
        # Run migrations
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully")
        
    except Exception as e:
        logger.error("Failed to run migrations", error=str(e))
        raise


async def error_handler(update: object, context) -> None:
    """Enhanced global error handler with detailed logging."""
    # Format the full traceback
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ''.join(tb_list)
    
    logger.error(
        "Exception while handling an update",
        update_id=update.update_id if hasattr(update, 'update_id') else None,
        chat_id=update.effective_chat.id if update and hasattr(update, 'effective_chat') and update.effective_chat else None,
        user_id=update.effective_user.id if update and hasattr(update, 'effective_user') and update.effective_user else None,
        error_type=type(context.error).__name__,
        error=str(context.error),
        traceback=tb_string,
    )


def create_application() -> Application:
    """Create and configure the Telegram bot application with optimizations."""
    # Configure HTTP request with connection pooling from settings
    request = HTTPXRequest(
        connection_pool_size=settings.bot_connection_pool_size,
        read_timeout=settings.bot_read_timeout,
        write_timeout=settings.bot_write_timeout,
        connect_timeout=settings.bot_connect_timeout,
        pool_timeout=settings.bot_pool_timeout,
    )
    
    # Create application with optimizations
    application = (
        Application.builder()
        .token(settings.bot_token)
        .request(request)
        .concurrent_updates(True)
        .build()
    )
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Add command handlers
    application.add_handler(CommandHandler("setup", setup_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("set_text", set_text_command))
    application.add_handler(CommandHandler("set_reactions", set_reactions_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start", help_command))
    
    # Add reaction handlers
    application.add_handler(MessageReactionHandler(handle_message_reaction))
    # Note: message_reaction_count updates are also handled by the same handler
    # as they come through the same MessageReactionHandler
    
    # Add message handlers with optimized filters
    # Handle regular messages (text, media, etc.) in groups only
    application.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL | 
             filters.AUDIO | filters.VOICE | filters.VIDEO_NOTE | filters.Sticker.ALL |
             filters.ANIMATION | filters.CONTACT | filters.LOCATION | filters.VENUE |
             filters.POLL | filters.GAME) & 
            ~filters.COMMAND & 
            (filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP),
            handle_message
        )
    )
    # Handle member updates
    application.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members)
    )
    application.add_handler(
        MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_left_chat_member)
    )
    
    # Add edited message handler
    application.add_handler(
        MessageHandler(filters.UpdateType.EDITED_MESSAGE, handle_edited_message)
    )
    
    # Add chat member handler
    application.add_handler(ChatMemberHandler(handle_chat_member_updated))
    
    logger.info("Bot application configured successfully")
    return application


async def setup_plugins(application: Application) -> None:
    """Load and initialize all plugins."""
    global plugin_manager
    
    # Skip if plugins are disabled
    if not settings.enable_plugins:
        logger.info("Plugins disabled in configuration")
        return
    
    try:
        logger.info("Loading plugins...")
        await plugin_manager.load_plugins()
        
        logger.info("Initializing plugins...")
        await plugin_manager.initialize_plugins(application)
        
        logger.info("Registering command plugins...")
        plugin_manager.register_command_plugins(application)
        
        # Start hot reload monitoring
        await plugin_manager.start_hot_reload(application)
        
        # Log loaded plugins
        plugins = plugin_manager.list_plugins()
        logger.info(
            "plugins_loaded",
            count=len(plugins),
            plugins=list(plugins.keys())
        )
        
    except Exception as e:
        logger.error("Failed to setup plugins", error=str(e), exc_info=True)


async def run_polling_mode(application: Application) -> None:
    """Run the bot in polling mode with graceful shutdown."""
    logger.info("Starting bot in polling mode...")
    
    # Initialize the application
    await application.initialize()
    await application.start()
    
    # Setup plugins
    await setup_plugins(application)
    
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    logger.info("Bot is running in polling mode. Press Ctrl+C to stop.")
    
    # Create a future for shutdown signal
    shutdown_event = asyncio.Event()
    
    def handle_shutdown_signal():
        """Handle shutdown signals."""
        logger.info("Shutdown signal received, stopping gracefully...")
        shutdown_event.set()
    
    # Register signal handlers for the event loop
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_shutdown_signal)
    
    try:
        # Wait for shutdown signal
        await shutdown_event.wait()
    finally:
        logger.info("Shutting down bot...")
        try:
            # Stop hot reload first
            await plugin_manager.stop_hot_reload()
            
            # Shutdown plugins
            await plugin_manager.shutdown_plugins()
            
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
            logger.info("Bot shutdown complete")
        except Exception as e:
            logger.error("Error during shutdown", error=str(e), exc_info=True)


async def run_webhook_mode(application: Application) -> None:
    """Run the bot in webhook mode with FastAPI."""
    if not settings.webhook_url:
        logger.error("WEBHOOK_URL is required for webhook mode")
        sys.exit(1)
    
    logger.info("Starting bot in webhook mode...")
    
    # Initialize the application
    await application.initialize()
    await application.start()
    
    # Setup plugins
    await setup_plugins(application)
    
    # Set webhook
    await application.bot.set_webhook(
        url=f"{settings.webhook_url}/tg/webhook",
        allowed_updates=Update.ALL_TYPES,
    )
    
    logger.info(f"Webhook set to: {settings.webhook_url}/tg/webhook")
    
    # Import and configure FastAPI app
    from .web.app import app, set_bot_application
    
    set_bot_application(application)
    
    # Run FastAPI server
    import uvicorn
    
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8010,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    
    logger.info("FastAPI server starting on port 8010")
    
    try:
        await server.serve()
    finally:
        await plugin_manager.stop_hot_reload()
        await plugin_manager.shutdown_plugins()
        await application.stop()
        await application.shutdown()


async def main():
    """Main entry point with graceful shutdown handling."""
    try:
        # Skip migrations for now since they're already done
        # await run_migrations()
        
        # Create and configure the application
        application = create_application()
        
        # Check if we should run in webhook or polling mode
        webhook_url = settings.webhook_url
        
        if webhook_url:
            await run_webhook_mode(application)
        else:
            await run_polling_mode(application)
            
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("Unexpected error", error=str(e), exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("Fatal error", error=str(e), exc_info=True)
        sys.exit(1)

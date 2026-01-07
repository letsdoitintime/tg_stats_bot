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
    ChatMemberHandler,
    CommandHandler,
    MessageHandler,
    MessageReactionHandler,
    filters,
)
from telegram.request import HTTPXRequest

from .core.config import settings
from .core.config_validator import validate_config
from .handlers.commands import (
    help_command,
    set_reactions_command,
    set_text_command,
    settings_command,
    setup_command,
)
from .handlers.members import (
    handle_chat_member_updated,
    handle_left_chat_member,
    handle_new_chat_members,
)
from .handlers.messages import handle_edited_message, handle_message
from .handlers.reactions import handle_message_reaction
from .plugins import PluginManager
from .utils.logging import configure_third_party_logging, setup_logging
from .utils.network_monitor import get_network_monitor

# Configure logging
setup_logging(
    log_level=settings.log_level,
    log_to_file=settings.log_to_file,
    log_file_path=settings.log_file_path,
    log_file_max_bytes=settings.log_file_max_bytes,
    log_file_backup_count=settings.log_file_backup_count,
    log_format=settings.log_format,
)
configure_third_party_logging(
    settings.telegram_log_level, settings.httpx_log_level, settings.uvicorn_log_level
)

logger = structlog.get_logger(__name__)

# Validate configuration at startup
try:
    validate_config(settings)
    logger.info("Configuration validated successfully")
except ValueError as e:
    logger.error("Configuration validation failed", error=str(e))
    sys.exit(1)

# Global plugin manager
plugin_manager = PluginManager()


async def run_migrations():
    """Run database migrations."""
    logger.info("Running database migrations...")
    try:
        # Import here to avoid circular dependencies
        import os

        from alembic import command
        from alembic.config import Config

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
    # Import here to avoid circular dependency issues
    from telegram.error import NetworkError, RetryAfter, TimedOut

    # Get network monitor
    monitor = get_network_monitor()

    # Check if it's a network-related error that should be handled quietly
    if isinstance(context.error, (NetworkError, TimedOut, RetryAfter)):
        # Record the error for monitoring
        error_type = type(context.error).__name__
        error_message = str(context.error)
        monitor.record_error(error_type, error_message)

        # Only log at DEBUG level for transient network errors
        # These are automatically retried by python-telegram-bot
        logger.debug(
            "transient_network_error",
            error_type=error_type,
            error=error_message,
            update_id=update.update_id if hasattr(update, "update_id") else None,
            consecutive_errors=monitor.get_health_status()["consecutive_errors"],
        )
        # These errors are typically transient and automatically retried
        return

    # Format the full traceback for other errors
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    logger.error(
        "Exception while handling an update",
        update_id=update.update_id if hasattr(update, "update_id") else None,
        chat_id=(
            update.effective_chat.id
            if update and hasattr(update, "effective_chat") and update.effective_chat
            else None
        ),
        user_id=(
            update.effective_user.id
            if update and hasattr(update, "effective_user") and update.effective_user
            else None
        ),
        error_type=type(context.error).__name__,
        error=str(context.error),
        traceback=tb_string,
    )


def create_application() -> Application:
    """Create and configure the Telegram bot application with optimizations."""
    # Configure HTTP request with connection pooling for regular bot operations
    request = HTTPXRequest(
        connection_pool_size=settings.bot_connection_pool_size,
        read_timeout=settings.bot_read_timeout,
        write_timeout=settings.bot_write_timeout,
        connect_timeout=settings.bot_connect_timeout,
        pool_timeout=settings.bot_pool_timeout,
        http_version="1.1",  # Use HTTP/1.1 for better stability with long-polling
    )

    # Configure separate request handler for get_updates with higher timeouts
    # This is critical for long-polling stability - read_timeout must be > poll timeout
    get_updates_request = HTTPXRequest(
        connection_pool_size=settings.bot_connection_pool_size,
        read_timeout=settings.bot_get_updates_read_timeout,
        write_timeout=settings.bot_write_timeout,
        connect_timeout=settings.bot_get_updates_connect_timeout,
        pool_timeout=settings.bot_get_updates_pool_timeout,
        http_version="1.1",  # Use HTTP/1.1 for better stability
    )

    # Create application with optimizations
    application = (
        Application.builder()
        .token(settings.bot_token)
        .request(request)
        .get_updates_request(get_updates_request)  # Dedicated request handler for polling
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
            (
                filters.TEXT
                | filters.PHOTO
                | filters.VIDEO
                | filters.Document.ALL
                | filters.AUDIO
                | filters.VOICE
                | filters.VIDEO_NOTE
                | filters.Sticker.ALL
                | filters.ANIMATION
                | filters.CONTACT
                | filters.LOCATION
                | filters.VENUE
                | filters.POLL
                | filters.GAME
            )
            & ~filters.COMMAND
            & (filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP),
            handle_message,
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
        logger.info("plugins_loaded", count=len(plugins), plugins=list(plugins.keys()))

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

    # Start polling with explicit timeout configuration and bootstrap retries
    # - timeout: how long Telegram waits for new updates (long-polling)
    # - poll_interval: delay between get_updates calls (0 = no delay)
    # - bootstrap_retries: retries on startup connection errors (-1 = infinite)
    logger.info(
        "starting_polling",
        get_updates_timeout=settings.bot_get_updates_timeout,
        poll_interval=settings.bot_poll_interval,
        bootstrap_retries=settings.bot_bootstrap_retries,
        get_updates_read_timeout=settings.bot_get_updates_read_timeout,
    )
    
    await application.updater.start_polling(
        allowed_updates=Update.ALL_TYPES,
        timeout=settings.bot_get_updates_timeout,
        poll_interval=settings.bot_poll_interval,
        bootstrap_retries=settings.bot_bootstrap_retries,
    )

    logger.info("Bot is running in polling mode. Press Ctrl+C to stop.")

    # Start network health monitoring in background
    monitor = get_network_monitor()
    health_check_task = asyncio.create_task(monitor.periodic_health_check(interval_seconds=300))

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
            # Cancel health check task
            health_check_task.cancel()
            try:
                await health_check_task
            except asyncio.CancelledError:
                pass

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

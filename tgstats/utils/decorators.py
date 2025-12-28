"""Decorators for common patterns."""

import functools
import structlog
from typing import Callable, Any, Tuple, Optional

from telegram import Update
from telegram.ext import ContextTypes

from ..db import async_session
from ..core.exceptions import TgStatsError

logger = structlog.get_logger(__name__)


def _parse_handler_args(args: tuple) -> Tuple[Optional[Any], Update, ContextTypes.DEFAULT_TYPE, tuple]:
    """
    Parse handler arguments to extract self, update, context, and extra args.
    
    Returns:
        Tuple of (self_arg or None, update, context, extra_args)
    """
    # Handle both bound methods (self, update, context) and functions (update, context)
    if len(args) >= 3 and hasattr(args[0], '__class__') and not isinstance(args[0], Update):
        # Bound method: (self, update, context, ...)
        return args[0], args[1], args[2], args[3:]
    elif len(args) >= 2:
        # Regular function: (update, context, ...)
        return None, args[0], args[1], args[2:]
    else:
        raise TypeError("Handler requires at least update and context arguments")


def _call_handler(func: Callable, self_arg: Optional[Any], update: Update, 
                  context: ContextTypes.DEFAULT_TYPE, extra_args: tuple, kwargs: dict) -> Any:
    """Call handler function with or without self argument."""
    if self_arg is not None:
        return func(self_arg, update, context, *extra_args, **kwargs)
    else:
        return func(update, context, *extra_args, **kwargs)


def with_db_session(func: Callable) -> Callable:
    """
    Decorator that provides a database session to handler functions.
    Automatically handles commit on success, rollback on error, and error logging.
    
    Usage:
        @with_db_session
        async def my_handler(update, context, session):
            # Use session here
            # Commit happens automatically on success
            # Rollback happens automatically on error
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            self_arg, update, context, extra_args = _parse_handler_args(args)
        except TypeError as e:
            raise TypeError(f"Handler {func.__name__} requires at least update and context arguments")
        
        async with async_session() as session:
            try:
                result = await _call_handler(func, self_arg, update, context, 
                                            extra_args + (session,), kwargs)
                # Auto-commit on success
                await session.commit()
                logger.debug("Transaction committed", handler=func.__name__)
                return result
            except TgStatsError as e:
                await session.rollback()
                logger.error(
                    "Application error in handler",
                    handler=func.__name__,
                    error=str(e),
                    error_type=type(e).__name__
                )
                if update.effective_message:
                    await update.effective_message.reply_text(
                        f"❌ Error: {str(e)}"
                    )
            except Exception as e:
                await session.rollback()
                logger.error(
                    "Unexpected error in handler",
                    handler=func.__name__,
                    error=str(e),
                    exc_info=True
                )
                if update.effective_message:
                    await update.effective_message.reply_text(
                        "❌ An unexpected error occurred. Please try again."
                    )
    return wrapper


def log_handler_call(func: Callable) -> Callable:
    """Decorator that logs handler entry and exit."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        logger.debug("Handler started", handler=func.__name__)
        try:
            result = await func(*args, **kwargs)
            logger.debug("Handler completed", handler=func.__name__)
            return result
        except Exception as e:
            logger.error(
                "Handler failed",
                handler=func.__name__,
                error=str(e),
                exc_info=True
            )
            raise
    return wrapper


def require_admin(func: Callable) -> Callable:
    """
    Decorator that checks if user is admin before executing handler.
    Should be used after with_db_session decorator.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            self_arg, update, context, extra_args = _parse_handler_args(args)
        except TypeError:
            return
        
        if not update.effective_chat or not update.effective_user:
            return
        
        try:
            chat_administrators = await context.bot.get_chat_administrators(
                update.effective_chat.id
            )
            admin_ids = [admin.user.id for admin in chat_administrators]
            
            if update.effective_user.id not in admin_ids:
                if update.effective_message:
                    await update.effective_message.reply_text(
                        "❌ Only administrators can use this command."
                    )
                return
            
            return await _call_handler(func, self_arg, update, context, extra_args, kwargs)
            
        except Exception as e:
            logger.error("Error checking admin status", error=str(e))
            if update.effective_message:
                await update.effective_message.reply_text(
                    "❌ Error checking permissions."
                )
    return wrapper


def group_only(func: Callable) -> Callable:
    """Decorator that ensures command is only used in groups."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            self_arg, update, context, extra_args = _parse_handler_args(args)
        except TypeError:
            return
        
        if not update.effective_chat:
            return
        
        if update.effective_chat.type == "private":
            if update.effective_message:
                await update.effective_message.reply_text(
                    "❌ This command can only be used in groups."
                )
            return
        
        return await _call_handler(func, self_arg, update, context, extra_args, kwargs)
    return wrapper

"""Database retry utilities for handling transient failures."""

import asyncio
import logging
from functools import wraps
from typing import TypeVar, Callable, Any

from sqlalchemy.exc import (
    OperationalError,
    DBAPIError,
    TimeoutError as SQLAlchemyTimeoutError,
)

from ..core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T')


def with_db_retry(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to retry database operations on transient failures.
    
    Handles common transient database errors like connection timeouts,
    connection resets, and temporary unavailability.
    
    Usage:
        @with_db_retry
        async def my_db_operation():
            # database code here
    """
    @wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> T:
        last_exception = None
        
        for attempt in range(settings.db_retry_attempts):
            try:
                return await func(*args, **kwargs)
            except (OperationalError, DBAPIError, SQLAlchemyTimeoutError) as e:
                last_exception = e
                error_msg = str(e).lower()
                
                # Only retry on transient errors
                is_transient = any(
                    keyword in error_msg
                    for keyword in [
                        "connection",
                        "timeout",
                        "terminated",
                        "closed",
                        "reset",
                        "broken pipe",
                        "server closed the connection",
                    ]
                )
                
                if not is_transient:
                    logger.error(
                        "Non-transient database error, not retrying",
                        error=str(e),
                        func=func.__name__,
                    )
                    raise
                
                if attempt < settings.db_retry_attempts - 1:
                    delay = settings.db_retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        "Database operation failed, retrying",
                        attempt=attempt + 1,
                        max_attempts=settings.db_retry_attempts,
                        delay=delay,
                        error=str(e),
                        func=func.__name__,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Database operation failed after all retries",
                        attempts=settings.db_retry_attempts,
                        error=str(e),
                        func=func.__name__,
                    )
        
        raise last_exception
    
    @wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> T:
        """Synchronous version of retry wrapper."""
        import time
        last_exception = None
        
        for attempt in range(settings.db_retry_attempts):
            try:
                return func(*args, **kwargs)
            except (OperationalError, DBAPIError, SQLAlchemyTimeoutError) as e:
                last_exception = e
                error_msg = str(e).lower()
                
                is_transient = any(
                    keyword in error_msg
                    for keyword in [
                        "connection",
                        "timeout",
                        "terminated",
                        "closed",
                        "reset",
                        "broken pipe",
                        "server closed the connection",
                    ]
                )
                
                if not is_transient:
                    logger.error(
                        "Non-transient database error, not retrying",
                        error=str(e),
                        func=func.__name__,
                    )
                    raise
                
                if attempt < settings.db_retry_attempts - 1:
                    delay = settings.db_retry_delay * (2 ** attempt)
                    logger.warning(
                        "Database operation failed, retrying",
                        attempt=attempt + 1,
                        max_attempts=settings.db_retry_attempts,
                        delay=delay,
                        error=str(e),
                        func=func.__name__,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "Database operation failed after all retries",
                        attempts=settings.db_retry_attempts,
                        error=str(e),
                        func=func.__name__,
                    )
        
        raise last_exception
    
    # Return appropriate wrapper based on whether function is async
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

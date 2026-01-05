"""Utility functions and decorators."""

from .cache import CacheManager, cache_manager, cached
from .db_retry import with_db_retry
from .metrics import MetricsManager, metrics, track_db_query, track_time
from .rate_limiter import RateLimiter, rate_limiter
from .sanitizer import (
    is_safe_sql_input,
    is_safe_web_input,
    sanitize_chat_id,
    sanitize_command_arg,
    sanitize_text,
    sanitize_user_id,
    sanitize_username,
)
from .validation import (
    ValidationError,
    sanitize_command_input,
    validate_chat_id,
    validate_date_string,
    validate_locale,
    validate_page_params,
    validate_retention_days,
    validate_timezone,
    validate_user_id,
)

__all__ = [
    "rate_limiter",
    "RateLimiter",
    "cache",
    "CacheManager",
    "cache_manager",
    "cached",
    "sanitize_text",
    "sanitize_command_arg",
    "is_safe_sql_input",
    "is_safe_web_input",
    "sanitize_chat_id",
    "sanitize_user_id",
    "sanitize_username",
    "metrics",
    "MetricsManager",
    "track_time",
    "track_db_query",
    "with_db_retry",
    "ValidationError",
    "validate_chat_id",
    "validate_user_id",
    "validate_retention_days",
    "validate_page_params",
    "validate_date_string",
    "validate_timezone",
    "validate_locale",
    "sanitize_command_input",
]

"""Application constants and defaults.

This module centralizes all magic numbers, default values, and configuration
constants used throughout the application. Keeping them here makes them easier
to find, update, and test.
"""

# ============================================================================
# Default Retention Periods
# ============================================================================
# How long to keep different types of data in the database

DEFAULT_TEXT_RETENTION_DAYS = 90
"""Default retention period for message text content (90 days)."""

DEFAULT_METADATA_RETENTION_DAYS = 365
"""Default retention period for message metadata (1 year)."""


# ============================================================================
# Default Group Settings
# ============================================================================
# Default values when a group is first set up

DEFAULT_TIMEZONE = "UTC"
"""Default timezone for new groups."""

DEFAULT_LOCALE = "en"
"""Default locale/language for new groups."""

DEFAULT_STORE_TEXT = True
"""Default setting for storing message text (privacy consideration)."""

DEFAULT_CAPTURE_REACTIONS = False
"""Default setting for capturing message reactions."""


# ============================================================================
# Pagination Settings
# ============================================================================
# Limits for paginated API responses

DEFAULT_PAGE_SIZE = 50
"""Default number of items per page for paginated responses."""

MAX_PAGE_SIZE = 1000
"""Maximum allowed page size to prevent excessive memory usage."""

MIN_PAGE_SIZE = 1
"""Minimum page size."""


# ============================================================================
# Celery Task Configuration
# ============================================================================
# Settings for background task processing

TASK_TIME_LIMIT = 30 * 60  # 30 minutes
"""Hard time limit for Celery tasks (in seconds)."""

TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
"""Soft time limit for Celery tasks to allow graceful shutdown (in seconds)."""

WORKER_PREFETCH_MULTIPLIER = 1
"""Number of tasks to prefetch per worker process."""

WORKER_MAX_TASKS_PER_CHILD = 1000
"""Maximum tasks a worker process handles before restart (prevents memory leaks)."""

CELERY_JITTER_MIN = 0
"""Minimum jitter for periodic tasks (in seconds)."""

CELERY_JITTER_MAX = 30
"""Maximum jitter for periodic tasks to prevent thundering herd (in seconds)."""


# ============================================================================
# API Configuration
# ============================================================================
# API version and endpoint paths

API_VERSION = "0.2.0"
"""Current API version."""

WEBHOOK_PATH = "/tg/webhook"
"""Path for Telegram webhook endpoint."""

HEALTH_CHECK_PATH = "/healthz"
"""Path for health check endpoint."""


# ============================================================================
# Rate Limiting
# ============================================================================
# Default rate limits (can be overridden via environment variables)

DEFAULT_RATE_LIMIT_PER_MINUTE = 10
"""Default number of requests allowed per minute per user."""

DEFAULT_RATE_LIMIT_PER_HOUR = 100
"""Default number of requests allowed per hour per user."""


# ============================================================================
# Cache Configuration
# ============================================================================
# Default cache settings

DEFAULT_CACHE_TTL = 300  # 5 minutes
"""Default time-to-live for cached items (in seconds)."""

CHAT_SETTINGS_CACHE_TTL = 600  # 10 minutes
"""Cache TTL specifically for chat settings."""


# ============================================================================
# Database Configuration
# ============================================================================
# Default database connection settings

DEFAULT_DB_POOL_SIZE = 10
"""Default database connection pool size."""

DEFAULT_DB_MAX_OVERFLOW = 20
"""Default maximum overflow connections."""

DEFAULT_DB_POOL_TIMEOUT = 30
"""Default timeout for getting connection from pool (in seconds)."""


# ============================================================================
# Message Processing
# ============================================================================
# Limits and defaults for message processing

MAX_TEXT_LENGTH = 4096
"""Maximum text length for Telegram messages."""

MAX_CAPTION_LENGTH = 1024
"""Maximum caption length for media messages."""


# ============================================================================
# TimescaleDB Configuration
# ============================================================================
# Chunk intervals for time-series data

TIMESCALE_CHUNK_INTERVAL_DAYS = 7
"""Chunk interval for TimescaleDB hypertables (7 days)."""


# ============================================================================
# Export Functions
# ============================================================================
# Validation helpers

def validate_page_size(page_size: int) -> int:
    """Validate and clamp page size to allowed range.
    
    Args:
        page_size: Requested page size
        
    Returns:
        Validated page size within MIN_PAGE_SIZE and MAX_PAGE_SIZE
    """
    return max(MIN_PAGE_SIZE, min(page_size, MAX_PAGE_SIZE))


def get_default_settings() -> dict:
    """Get dictionary of default group settings.
    
    Returns:
        Dictionary with default values for all group settings
    """
    return {
        "timezone": DEFAULT_TIMEZONE,
        "locale": DEFAULT_LOCALE,
        "store_text": DEFAULT_STORE_TEXT,
        "capture_reactions": DEFAULT_CAPTURE_REACTIONS,
        "text_retention_days": DEFAULT_TEXT_RETENTION_DAYS,
        "metadata_retention_days": DEFAULT_METADATA_RETENTION_DAYS,
    }

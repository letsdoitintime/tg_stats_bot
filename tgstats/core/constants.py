"""Application constants."""

# Default retention periods (in days)
DEFAULT_TEXT_RETENTION_DAYS = 90
DEFAULT_METADATA_RETENTION_DAYS = 365

# Default settings
DEFAULT_TIMEZONE = "UTC"
DEFAULT_LOCALE = "en"
DEFAULT_STORE_TEXT = True
DEFAULT_CAPTURE_REACTIONS = False

# Pagination defaults
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 1000

# Time limits (in seconds)
TASK_TIME_LIMIT = 30 * 60  # 30 minutes
TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes

# Worker settings
WORKER_PREFETCH_MULTIPLIER = 1
WORKER_MAX_TASKS_PER_CHILD = 1000

# Celery jitter range
CELERY_JITTER_MIN = 0
CELERY_JITTER_MAX = 30

# API settings
API_VERSION = "0.2.0"
WEBHOOK_PATH = "/tg/webhook"

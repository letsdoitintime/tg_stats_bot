"""Celery configuration and tasks for background processing."""

import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import structlog
from celery import Celery
from celery.schedules import crontab
from sqlalchemy import text

logger = structlog.get_logger(__name__)

# Import after logger setup to avoid circular imports
try:
    from .core.config import settings
    from .core.constants import (
        CELERY_JITTER_MAX,
        CELERY_JITTER_MIN,
        TASK_SOFT_TIME_LIMIT,
        TASK_TIME_LIMIT,
        WORKER_MAX_TASKS_PER_CHILD,
        WORKER_PREFETCH_MULTIPLIER,
    )
    from .db import get_sync_session
except ImportError:
    # Handle case when running standalone
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tgstats.core.config import settings
    from tgstats.core.constants import (
        CELERY_JITTER_MAX,
        CELERY_JITTER_MIN,
        TASK_SOFT_TIME_LIMIT,
        TASK_TIME_LIMIT,
        WORKER_MAX_TASKS_PER_CHILD,
        WORKER_PREFETCH_MULTIPLIER,
    )
    from tgstats.db import get_sync_session

# Create Celery app
celery_app = Celery(
    "tgstats",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["tgstats.celery_tasks"],
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Task execution limits
    task_time_limit=TASK_TIME_LIMIT,  # Hard timeout (5 minutes)
    task_soft_time_limit=TASK_SOFT_TIME_LIMIT,  # Soft timeout (4 minutes)
    # Worker resource limits
    worker_prefetch_multiplier=WORKER_PREFETCH_MULTIPLIER,  # Tasks to prefetch per worker
    worker_max_tasks_per_child=WORKER_MAX_TASKS_PER_CHILD,  # Restart after N tasks (prevents memory leaks)
    worker_max_memory_per_child=512000,  # 512MB per worker process
    worker_disable_rate_limits=False,  # Enable rate limiting
    # Task priority and routing
    task_default_priority=5,  # Default task priority (0-10)
    task_inherit_parent_priority=True,  # Inherit priority from parent
    # Result backend
    result_expires=3600,  # Results expire after 1 hour
    result_compression="gzip",  # Compress results to save memory
    # Concurrency and performance
    worker_pool_restarts=True,  # Enable pool restarts
    # Logging
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
)


def check_timescaledb_available() -> bool:
    """Check if TimescaleDB extension is available."""
    try:
        with get_sync_session() as session:
            result = session.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
            ).fetchone()
            return result is not None
    except Exception as e:
        logger.error(f"Error checking TimescaleDB availability: {e}")
        return False


# Configure periodic tasks only if TimescaleDB is NOT available
# (TimescaleDB continuous aggregates update automatically)
if not check_timescaledb_available():
    celery_app.conf.beat_schedule = {
        "refresh-chat-daily-mv": {
            "task": "tgstats.celery_tasks.refresh_materialized_view",
            "schedule": crontab(minute="*/10"),  # Every 10 minutes
            "args": ("chat_daily_mv",),
            "options": {"jitter": True, "max_retries": 3},
        },
        "refresh-user-chat-daily-mv": {
            "task": "tgstats.celery_tasks.refresh_materialized_view",
            "schedule": crontab(minute="*/10"),
            "args": ("user_chat_daily_mv",),
            "options": {"jitter": True, "max_retries": 3},
        },
        "refresh-chat-hourly-heatmap-mv": {
            "task": "tgstats.celery_tasks.refresh_materialized_view",
            "schedule": crontab(minute="*/10"),
            "args": ("chat_hourly_heatmap_mv",),
            "options": {"jitter": True, "max_retries": 3},
        },
    }


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={
        "max_retries": settings.celery_task_max_retries,
        "countdown": settings.celery_task_retry_delay,
    },
    retry_backoff=True,
    retry_jitter=True,
)
def refresh_materialized_view(self, view_name: str) -> Dict[str, Any]:
    """Refresh a materialized view and log the results."""
    start_time = datetime.now(timezone.utc)

    # Add jitter to avoid thundering herd
    jitter = random.uniform(CELERY_JITTER_MIN, CELERY_JITTER_MAX)
    if jitter > 0:
        import time

        time.sleep(jitter)

    try:
        with get_sync_session() as session:
            # Get row count before refresh
            result_before = session.execute(text(f"SELECT COUNT(*) FROM {view_name}")).fetchone()
            rows_before = result_before[0] if result_before else 0

            # Refresh the materialized view
            # Note: CONCURRENTLY requires unique indexes, which we don't have
            # Regular refresh is fast enough for our small views (< 1 second)
            logger.info(f"Starting refresh of materialized view: {view_name}")
            session.execute(text(f"REFRESH MATERIALIZED VIEW {view_name}"))
            session.commit()

            # Get row count after refresh
            result_after = session.execute(text(f"SELECT COUNT(*) FROM {view_name}")).fetchone()
            rows_after = result_after[0] if result_after else 0

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            result = {
                "view_name": view_name,
                "duration_seconds": duration,
                "rows_before": rows_before,
                "rows_after": rows_after,
                "rows_changed": rows_after - rows_before,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }

            logger.info("Materialized view refresh completed", extra=result)

            return result

    except Exception as e:
        logger.error(f"Error refreshing materialized view {view_name}: {e}", exc_info=True)
        raise


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={
        "max_retries": settings.celery_task_max_retries,
        "countdown": settings.celery_task_retry_delay,
    },
    retry_backoff=True,
    retry_jitter=True,
)
def retention_preview(self, chat_id: int) -> Dict[str, Any]:
    """Preview what would be deleted by retention policies."""
    try:
        with get_sync_session() as session:
            # Get group settings
            settings_result = session.execute(
                text(
                    """
                    SELECT text_retention_days, metadata_retention_days, store_text, timezone
                    FROM group_settings
                    WHERE chat_id = :chat_id
                """
                ),
                {"chat_id": chat_id},
            ).fetchone()

            if not settings_result:
                return {"error": "No settings found for chat"}

            text_retention_days, metadata_retention_days, store_text, timezone = settings_result

            # Calculate cutoff dates
            now = datetime.now(timezone.utc)
            text_cutoff = now - timedelta(days=text_retention_days)
            metadata_cutoff = now - timedelta(days=metadata_retention_days)

            # Count messages that would have text removed
            text_removal_count = 0
            if store_text and text_retention_days > 0:
                result = session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM messages
                        WHERE chat_id = :chat_id
                        AND date < :cutoff
                        AND text_raw IS NOT NULL
                    """
                    ),
                    {"chat_id": chat_id, "cutoff": text_cutoff},
                ).fetchone()
                text_removal_count = result[0] if result else 0

            # Count messages that would be deleted entirely
            metadata_removal_count = 0
            if metadata_retention_days > 0:
                result = session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM messages
                        WHERE chat_id = :chat_id
                        AND date < :cutoff
                    """
                    ),
                    {"chat_id": chat_id, "cutoff": metadata_cutoff},
                ).fetchone()
                metadata_removal_count = result[0] if result else 0

            # Count reactions that would be deleted
            reaction_removal_count = 0
            if metadata_retention_days > 0:
                result = session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM reactions
                        WHERE chat_id = :chat_id
                        AND date < :cutoff
                    """
                    ),
                    {"chat_id": chat_id, "cutoff": metadata_cutoff},
                ).fetchone()
                reaction_removal_count = result[0] if result else 0

            return {
                "chat_id": chat_id,
                "text_retention_days": text_retention_days,
                "metadata_retention_days": metadata_retention_days,
                "store_text": store_text,
                "text_removal_count": text_removal_count,
                "metadata_removal_count": metadata_removal_count,
                "reaction_removal_count": reaction_removal_count,
                "text_cutoff_date": text_cutoff.isoformat(),
                "metadata_cutoff_date": metadata_cutoff.isoformat(),
                "preview_generated_at": now.isoformat(),
            }

    except Exception as e:
        logger.error(f"Error generating retention preview for chat {chat_id}: {e}", exc_info=True)
        return {"error": str(e)}


if __name__ == "__main__":
    # For development - start worker
    celery_app.start()

"""Prometheus metrics for monitoring."""

import time
from functools import wraps
from typing import Callable

import structlog

try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from ..core.config import settings

logger = structlog.get_logger()


class MetricsManager:
    """Manager for application metrics."""

    def __init__(self):
        self._enabled = settings.enable_metrics and PROMETHEUS_AVAILABLE

        if not self._enabled:
            return

        self.registry = CollectorRegistry()

        # Bot metrics
        self.messages_processed = Counter(
            "bot_messages_processed_total",
            "Total messages processed",
            ["chat_type", "media_type"],
            registry=self.registry,
        )

        self.commands_executed = Counter(
            "bot_commands_executed_total",
            "Total commands executed",
            ["command", "status"],
            registry=self.registry,
        )

        self.reactions_tracked = Counter(
            "bot_reactions_tracked_total",
            "Total reactions tracked",
            ["reaction_type"],
            registry=self.registry,
        )

        # Performance metrics
        self.request_duration = Histogram(
            "bot_request_duration_seconds",
            "Request duration in seconds",
            ["handler"],
            registry=self.registry,
        )

        self.db_query_duration = Histogram(
            "bot_db_query_duration_seconds",
            "Database query duration in seconds",
            ["operation"],
            registry=self.registry,
        )

        # System metrics
        self.active_chats = Gauge(
            "bot_active_chats", "Number of active chats", registry=self.registry
        )

        self.db_connections = Gauge(
            "bot_db_connections",
            "Number of database connections",
            ["state"],
            registry=self.registry,
        )

        self.errors_total = Counter(
            "bot_errors_total", "Total errors encountered", ["error_type"], registry=self.registry
        )

        logger.info("metrics_initialized")

    def increment_messages(self, chat_type: str = "unknown", media_type: str = "text"):
        """Increment messages processed counter."""
        if self._enabled:
            self.messages_processed.labels(chat_type=chat_type, media_type=media_type).inc()

    def increment_commands(self, command: str, status: str = "success"):
        """Increment commands executed counter."""
        if self._enabled:
            self.commands_executed.labels(command=command, status=status).inc()

    def increment_reactions(self, reaction_type: str):
        """Increment reactions tracked counter."""
        if self._enabled:
            self.reactions_tracked.labels(reaction_type=reaction_type).inc()

    def increment_errors(self, error_type: str):
        """Increment error counter."""
        if self._enabled:
            self.errors_total.labels(error_type=error_type).inc()

    def set_active_chats(self, count: int):
        """Set active chats gauge."""
        if self._enabled:
            self.active_chats.set(count)

    def set_db_connections(self, state: str, count: int):
        """Set database connections gauge."""
        if self._enabled:
            self.db_connections.labels(state=state).set(count)

    def get_metrics(self) -> bytes:
        """Get Prometheus metrics in text format."""
        if not self._enabled:
            return b"# Metrics not enabled\n"

        return generate_latest(self.registry)


# Global metrics instance
metrics = MetricsManager()


def track_time(handler_name: str):
    """
    Decorator to track execution time.

    Usage:
        @track_time("process_message")
        async def process_message(...):
            ...
    """

    def decorator(func: Callable):
        """Decorator function that wraps the target function with timing logic."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            """Async wrapper that measures execution time and records metrics."""
            if not metrics._enabled:
                return await func(*args, **kwargs)

            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                metrics.request_duration.labels(handler=handler_name).observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                metrics.request_duration.labels(handler=handler_name).observe(duration)
                metrics.increment_errors(type(e).__name__)
                raise

        return wrapper

    return decorator


def track_db_query(operation: str):
    """
    Decorator to track database query duration.

    Usage:
        @track_db_query("insert_message")
        async def insert_message(...):
            ...
    """

    def decorator(func: Callable):
        """Decorator function that wraps database operations with query tracking."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            """Async wrapper that measures query execution time and records DB metrics."""
            if not metrics._enabled:
                return await func(*args, **kwargs)

            start_time = time.time()
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            metrics.db_query_duration.labels(operation=operation).observe(duration)
            return result

        return wrapper

    return decorator

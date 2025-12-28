"""Performance monitoring and profiling utilities.

Provides decorators and helpers for monitoring function execution time,
database query performance, and system metrics.
"""

import time
import functools
from typing import Callable, Any, Optional
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for a function or operation."""

    name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def finish(self, success: bool = True, error: Optional[str] = None):
        """Mark operation as finished."""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.success = success
        self.error = error


class PerformanceMonitor:
    """Central performance monitoring system."""

    def __init__(self):
        self._metrics = []
        self._slow_threshold = 1.0  # Default: 1 second

    def set_slow_threshold(self, threshold: float):
        """Set threshold for slow operation warning (in seconds)."""
        self._slow_threshold = threshold

    def record_metric(self, metric: PerformanceMetrics):
        """Record a performance metric."""
        # Log if operation was slow
        if metric.duration and metric.duration > self._slow_threshold:
            logger.warning(
                "Slow operation detected",
                operation=metric.name,
                duration=metric.duration,
                threshold=self._slow_threshold,
                success=metric.success,
                **metric.metadata,
            )

        # Log all operations at debug level
        logger.debug(
            "Operation completed",
            operation=metric.name,
            duration=metric.duration,
            success=metric.success,
            **metric.metadata,
        )

        # Store metric (limit history to last 1000)
        self._metrics.append(metric)
        if len(self._metrics) > 1000:
            self._metrics.pop(0)

    def get_metrics(
        self, operation_name: Optional[str] = None, limit: int = 100
    ) -> list[PerformanceMetrics]:
        """Get recorded metrics."""
        if operation_name:
            metrics = [m for m in self._metrics if m.name == operation_name]
        else:
            metrics = self._metrics

        return metrics[-limit:]

    def get_average_duration(self, operation_name: str) -> Optional[float]:
        """Get average duration for an operation."""
        metrics = [m for m in self._metrics if m.name == operation_name and m.duration]
        if not metrics:
            return None

        total = sum(m.duration for m in metrics)
        return total / len(metrics)

    def get_slow_operations(self, threshold: Optional[float] = None) -> list[PerformanceMetrics]:
        """Get operations that exceeded threshold."""
        threshold = threshold or self._slow_threshold
        return [m for m in self._metrics if m.duration and m.duration > threshold]


# Global performance monitor
performance_monitor = PerformanceMonitor()


def monitor_performance(operation_name: Optional[str] = None, **metadata):
    """
    Decorator to monitor function performance.

    Args:
        operation_name: Name for the operation (defaults to function name)
        **metadata: Additional metadata to include in metrics

    Example:
        @monitor_performance(operation_name="process_message")
        async def process_message(msg_id):
            # Function code
            pass
    """

    def decorator(func: Callable) -> Callable:
        name = operation_name or func.__name__

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            metric = PerformanceMetrics(name=name, start_time=time.time(), metadata=metadata)

            try:
                result = await func(*args, **kwargs)
                metric.finish(success=True)
                return result
            except Exception as e:
                metric.finish(success=False, error=str(e))
                raise
            finally:
                performance_monitor.record_metric(metric)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            metric = PerformanceMetrics(name=name, start_time=time.time(), metadata=metadata)

            try:
                result = func(*args, **kwargs)
                metric.finish(success=True)
                return result
            except Exception as e:
                metric.finish(success=False, error=str(e))
                raise
            finally:
                performance_monitor.record_metric(metric)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


@contextmanager
def measure_time(operation_name: str, **metadata):
    """
    Context manager for measuring execution time.

    Example:
        with measure_time("database_query", table="messages"):
            # Code to measure
            result = execute_query()
    """
    metric = PerformanceMetrics(name=operation_name, start_time=time.time(), metadata=metadata)

    try:
        yield metric
        metric.finish(success=True)
    except Exception as e:
        metric.finish(success=False, error=str(e))
        raise
    finally:
        performance_monitor.record_metric(metric)


class QueryPerformanceTracker:
    """Track database query performance."""

    def __init__(self):
        self._query_times = {}

    def record_query(self, query_name: str, duration: float, row_count: int = 0):
        """Record a database query execution."""
        if query_name not in self._query_times:
            self._query_times[query_name] = []

        self._query_times[query_name].append(
            {"duration": duration, "row_count": row_count, "timestamp": datetime.now(timezone.utc)}
        )

        # Log slow queries
        if duration > 1.0:
            logger.warning(
                "Slow database query", query=query_name, duration=duration, row_count=row_count
            )

        # Keep only last 100 executions per query
        if len(self._query_times[query_name]) > 100:
            self._query_times[query_name].pop(0)

    def get_query_stats(self, query_name: str) -> dict:
        """Get statistics for a specific query."""
        if query_name not in self._query_times:
            return {}

        times = self._query_times[query_name]
        durations = [t["duration"] for t in times]

        return {
            "count": len(times),
            "avg_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "total_duration": sum(durations),
        }

    def get_all_stats(self) -> dict:
        """Get statistics for all queries."""
        return {query: self.get_query_stats(query) for query in self._query_times.keys()}

    def get_slowest_queries(self, limit: int = 10) -> list:
        """Get slowest queries by average duration."""
        stats = []
        for query_name, executions in self._query_times.items():
            avg_duration = sum(e["duration"] for e in executions) / len(executions)
            stats.append(
                {"query": query_name, "avg_duration": avg_duration, "executions": len(executions)}
            )

        stats.sort(key=lambda x: x["avg_duration"], reverse=True)
        return stats[:limit]


# Global query tracker
query_tracker = QueryPerformanceTracker()


def track_query(query_name: str):
    """
    Decorator to track database query performance.

    Example:
        @track_query("get_user_messages")
        async def get_user_messages(user_id):
            # Query code
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start = time.time()
            result = await func(*args, **kwargs)
            duration = time.time() - start

            # Try to get row count from result
            row_count = 0
            if hasattr(result, "__len__"):
                row_count = len(result)

            query_tracker.record_query(query_name, duration, row_count)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start

            row_count = 0
            if hasattr(result, "__len__"):
                row_count = len(result)

            query_tracker.record_query(query_name, duration, row_count)
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Import asyncio for decorator checks
import asyncio


class MemoryMonitor:
    """Monitor memory usage."""

    @staticmethod
    def get_process_memory() -> dict:
        """Get current process memory usage."""
        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()

            return {
                "rss_mb": mem_info.rss / 1024 / 1024,  # Resident Set Size
                "vms_mb": mem_info.vms / 1024 / 1024,  # Virtual Memory Size
                "percent": process.memory_percent(),
            }
        except ImportError:
            logger.warning("psutil not installed, memory monitoring unavailable")
            return {}

    @staticmethod
    def log_memory_usage(context: str = ""):
        """Log current memory usage."""
        mem_stats = MemoryMonitor.get_process_memory()
        if mem_stats:
            logger.info("Memory usage", context=context, **mem_stats)


def get_performance_summary() -> dict:
    """Get overall performance summary."""
    return {
        "query_stats": query_tracker.get_all_stats(),
        "slowest_queries": query_tracker.get_slowest_queries(5),
        "slow_operations": len(performance_monitor.get_slow_operations()),
        "memory": MemoryMonitor.get_process_memory(),
    }

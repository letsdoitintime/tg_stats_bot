"""Common monitoring and alerting helpers."""

from typing import Optional, Dict, Any
import structlog
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


class HealthMonitor:
    """Monitor application health and track metrics."""
    
    def __init__(self):
        """Initialize health monitor."""
        self._errors: Dict[str, int] = {}
        self._last_error_time: Dict[str, datetime] = {}
        self._last_check: Optional[datetime] = None
        
    def record_error(self, error_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Record an error occurrence.
        
        Args:
            error_type: Type of error (e.g., "database_connection", "api_timeout")
            details: Optional additional error context
        """
        self._errors[error_type] = self._errors.get(error_type, 0) + 1
        self._last_error_time[error_type] = datetime.now()
        
        logger.warning(
            "error_recorded",
            error_type=error_type,
            count=self._errors[error_type],
            details=details or {}
        )
    
    def get_error_count(self, error_type: str, since: Optional[datetime] = None) -> int:
        """
        Get error count for a specific type.
        
        Args:
            error_type: Type of error to check
            since: Only count errors since this time (default: all time)
            
        Returns:
            Number of errors of this type
        """
        if error_type not in self._errors:
            return 0
            
        # If no time filter, return total count
        if since is None:
            return self._errors[error_type]
        
        # Check if last error was after 'since'
        last_error = self._last_error_time.get(error_type)
        if last_error and last_error >= since:
            return self._errors[error_type]
        
        return 0
    
    def is_healthy(self, error_threshold: int = 10, time_window_minutes: int = 5) -> bool:
        """
        Check if system is healthy based on recent error rates.
        
        Args:
            error_threshold: Maximum number of errors allowed in time window
            time_window_minutes: Time window to check (minutes)
            
        Returns:
            True if healthy, False if error rate is too high
        """
        since = datetime.now() - timedelta(minutes=time_window_minutes)
        
        # Count total errors in time window
        total_errors = 0
        for error_type in self._errors:
            total_errors += self.get_error_count(error_type, since=since)
        
        is_healthy = total_errors < error_threshold
        
        if not is_healthy:
            logger.error(
                "health_check_failed",
                total_errors=total_errors,
                threshold=error_threshold,
                time_window_minutes=time_window_minutes
            )
        
        return is_healthy
    
    def get_health_report(self) -> Dict[str, Any]:
        """
        Get comprehensive health report.
        
        Returns:
            Dictionary with health status and metrics
        """
        now = datetime.now()
        recent_errors = {}
        
        # Get errors from last 5 minutes
        five_minutes_ago = now - timedelta(minutes=5)
        for error_type, last_time in self._last_error_time.items():
            if last_time >= five_minutes_ago:
                recent_errors[error_type] = self._errors[error_type]
        
        return {
            "status": "healthy" if self.is_healthy() else "degraded",
            "total_errors_all_time": sum(self._errors.values()),
            "recent_errors_5min": recent_errors,
            "error_types_seen": list(self._errors.keys()),
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "current_time": now.isoformat()
        }
    
    def reset_counters(self) -> None:
        """Reset all error counters."""
        self._errors.clear()
        self._last_error_time.clear()
        logger.info("health_monitor_counters_reset")
    
    def mark_check(self) -> None:
        """Mark that a health check was performed."""
        self._last_check = datetime.now()


# Global health monitor instance
health_monitor = HealthMonitor()


def track_error(error_type: str, details: Optional[Dict[str, Any]] = None):
    """
    Decorator to track errors in functions.
    
    Usage:
        @track_error("database_error")
        async def my_function():
            # If this raises an exception, it's recorded
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                health_monitor.record_error(
                    error_type,
                    details={
                        **(details or {}),
                        "function": func.__name__,
                        "error_message": str(e),
                        "error_class": e.__class__.__name__
                    }
                )
                raise
        return wrapper
    return decorator


class CircuitBreaker:
    """
    Simple circuit breaker pattern implementation.
    
    Prevents cascading failures by temporarily blocking calls
    to a failing service.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout_seconds: int = 60
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name for logging
            failure_threshold: Number of failures before opening circuit
            timeout_seconds: Time to wait before attempting to close circuit
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timedelta(seconds=timeout_seconds)
        
        self._failures = 0
        self._last_failure_time: Optional[datetime] = None
        self._state = "closed"  # closed, open, half-open
    
    def record_success(self) -> None:
        """Record successful call."""
        self._failures = 0
        self._state = "closed"
        logger.debug("circuit_breaker_success", name=self.name)
    
    def record_failure(self) -> None:
        """Record failed call."""
        self._failures += 1
        self._last_failure_time = datetime.now()
        
        if self._failures >= self.failure_threshold:
            self._state = "open"
            logger.error(
                "circuit_breaker_opened",
                name=self.name,
                failures=self._failures,
                threshold=self.failure_threshold
            )
    
    def is_open(self) -> bool:
        """Check if circuit is open (blocking calls)."""
        if self._state == "closed":
            return False
        
        # Check if we should attempt to close circuit
        if self._last_failure_time:
            time_since_failure = datetime.now() - self._last_failure_time
            if time_since_failure > self.timeout:
                self._state = "half-open"
                logger.info("circuit_breaker_half_open", name=self.name)
                return False
        
        return self._state == "open"
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            "name": self.name,
            "state": self._state,
            "failures": self._failures,
            "threshold": self.failure_threshold,
            "last_failure": (
                self._last_failure_time.isoformat()
                if self._last_failure_time else None
            )
        }


class RateLimitMonitor:
    """Monitor rate limit usage and alerts."""
    
    def __init__(self):
        """Initialize rate limit monitor."""
        self._rate_limit_hits: Dict[str, int] = {}
        
    def record_rate_limit_hit(self, user_id: int, endpoint: str = "default") -> None:
        """
        Record a rate limit hit.
        
        Args:
            user_id: User who hit rate limit
            endpoint: Endpoint or command that was rate limited
        """
        key = f"{user_id}:{endpoint}"
        self._rate_limit_hits[key] = self._rate_limit_hits.get(key, 0) + 1
        
        logger.warning(
            "rate_limit_hit",
            user_id=user_id,
            endpoint=endpoint,
            total_hits=self._rate_limit_hits[key]
        )
    
    def get_rate_limit_stats(self) -> Dict[str, Any]:
        """Get rate limit statistics."""
        total_hits = sum(self._rate_limit_hits.values())
        unique_users = len(set(
            key.split(":")[0] for key in self._rate_limit_hits.keys()
        ))
        
        return {
            "total_rate_limit_hits": total_hits,
            "unique_users_rate_limited": unique_users,
            "top_offenders": sorted(
                self._rate_limit_hits.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }


# Global instances
rate_limit_monitor = RateLimitMonitor()


# Export commonly used items
__all__ = [
    'HealthMonitor',
    'health_monitor',
    'track_error',
    'CircuitBreaker',
    'RateLimitMonitor',
    'rate_limit_monitor'
]

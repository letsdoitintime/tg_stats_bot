"""Network connection monitoring and health tracking for Telegram bot.

This module provides utilities to monitor the health of the Telegram bot's
network connections and detect issues like connection pool exhaustion or
persistent network errors that might indicate infrastructure problems.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


class NetworkHealthMonitor:
    """Monitor network health and connection status for the Telegram bot."""

    def __init__(self):
        """Initialize network health monitor."""
        self._network_errors_count = 0
        self._last_error_time: Optional[datetime] = None
        self._last_success_time: Optional[datetime] = None
        self._consecutive_errors = 0
        self._error_types: dict[str, int] = {}

    def record_error(self, error_type: str, error_message: str) -> None:
        """
        Record a network error occurrence.

        Args:
            error_type: Type of error (e.g., "NetworkError", "TimedOut")
            error_message: Error message details
        """
        now = datetime.now()
        self._last_error_time = now
        self._network_errors_count += 1
        self._consecutive_errors += 1
        self._error_types[error_type] = self._error_types.get(error_type, 0) + 1

        # Log based on severity (consecutive errors indicate persistent issue)
        if self._consecutive_errors >= 5:
            logger.warning(
                "persistent_network_errors_detected",
                error_type=error_type,
                consecutive_errors=self._consecutive_errors,
                total_errors=self._network_errors_count,
                last_success=(now - self._last_success_time).total_seconds()
                if self._last_success_time
                else None,
                message=error_message,
            )
        else:
            logger.debug(
                "network_error_recorded",
                error_type=error_type,
                consecutive=self._consecutive_errors,
                total=self._network_errors_count,
            )

    def record_success(self) -> None:
        """Record a successful network operation."""
        now = datetime.now()
        self._last_success_time = now

        # If we had consecutive errors, log recovery
        if self._consecutive_errors >= 3:
            logger.info(
                "network_recovered",
                previous_consecutive_errors=self._consecutive_errors,
                downtime_seconds=(now - self._last_error_time).total_seconds()
                if self._last_error_time
                else 0,
            )

        self._consecutive_errors = 0

    def get_health_status(self) -> dict:
        """
        Get current network health status.

        Returns:
            Dictionary with health metrics
        """
        now = datetime.now()
        return {
            "total_errors": self._network_errors_count,
            "consecutive_errors": self._consecutive_errors,
            "error_types": dict(self._error_types),
            "last_error_seconds_ago": (now - self._last_error_time).total_seconds()
            if self._last_error_time
            else None,
            "last_success_seconds_ago": (now - self._last_success_time).total_seconds()
            if self._last_success_time
            else None,
            "is_healthy": self._consecutive_errors < 5,
        }

    def is_degraded(self) -> bool:
        """
        Check if network connection is degraded.

        Returns:
            True if connection is degraded (multiple consecutive errors)
        """
        return self._consecutive_errors >= 3

    def should_alert(self) -> bool:
        """
        Check if we should alert about network issues.

        Returns:
            True if persistent errors warrant alerting
        """
        # Alert if we've had many consecutive errors OR
        # if we've had lots of errors recently
        if self._consecutive_errors >= 10:
            return True

        # Check error rate in last 5 minutes
        if self._last_error_time:
            five_min_ago = datetime.now() - timedelta(minutes=5)
            if self._last_error_time > five_min_ago and self._network_errors_count >= 20:
                return True

        return False

    async def periodic_health_check(self, interval_seconds: int = 300) -> None:
        """
        Periodically log network health status.

        Args:
            interval_seconds: How often to log status (default: 5 minutes)
        """
        while True:
            await asyncio.sleep(interval_seconds)

            status = self.get_health_status()
            logger.info("network_health_check", **status)

            # Alert if needed
            if self.should_alert():
                logger.error(
                    "network_health_alert",
                    consecutive_errors=self._consecutive_errors,
                    total_errors=self._network_errors_count,
                    recommendation="Check Telegram API status and network connectivity",
                )


# Global network monitor instance
_network_monitor: Optional[NetworkHealthMonitor] = None


def get_network_monitor() -> NetworkHealthMonitor:
    """Get the global network monitor instance."""
    global _network_monitor
    if _network_monitor is None:
        _network_monitor = NetworkHealthMonitor()
    return _network_monitor

"""Rate limiting utilities for command spam prevention."""

import time
from collections import defaultdict
from typing import Dict, Tuple

import structlog

from ..core.config import settings

logger = structlog.get_logger()


class RateLimiter:
    """In-memory rate limiter for user commands."""

    def __init__(self):
        self._user_requests: Dict[int, list] = defaultdict(list)
        self._cleanup_interval = 300  # Clean up old entries every 5 minutes
        self._last_cleanup = time.time()

    def is_rate_limited(self, user_id: int) -> Tuple[bool, str]:
        """
        Check if user is rate limited.

        Args:
            user_id: Telegram user ID

        Returns:
            Tuple of (is_limited, message)
        """
        current_time = time.time()

        # Periodic cleanup
        if current_time - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_entries()

        # Get user's request history
        requests = self._user_requests[user_id]

        # Remove requests older than 1 hour
        cutoff_hour = current_time - 3600
        cutoff_minute = current_time - 60

        requests[:] = [req_time for req_time in requests if req_time > cutoff_hour]

        # Count recent requests
        requests_last_minute = sum(1 for req_time in requests if req_time > cutoff_minute)
        requests_last_hour = len(requests)

        # Check limits
        if requests_last_minute >= settings.rate_limit_per_minute:
            logger.warning(
                "rate_limit_exceeded", user_id=user_id, window="minute", count=requests_last_minute
            )
            return True, "⚠️ Rate limit exceeded. Please wait a minute before sending more commands."

        if requests_last_hour >= settings.rate_limit_per_hour:
            logger.warning(
                "rate_limit_exceeded", user_id=user_id, window="hour", count=requests_last_hour
            )
            return True, "⚠️ Rate limit exceeded. Please wait before sending more commands."

        # Add this request
        requests.append(current_time)

        return False, ""

    def _cleanup_old_entries(self):
        """Remove old entries to prevent memory bloat."""
        current_time = time.time()
        cutoff = current_time - 7200  # Keep last 2 hours

        for user_id in list(self._user_requests.keys()):
            requests = self._user_requests[user_id]
            requests[:] = [req_time for req_time in requests if req_time > cutoff]

            # Remove empty entries
            if not requests:
                del self._user_requests[user_id]

        self._last_cleanup = current_time
        logger.debug("rate_limiter_cleanup", entries_remaining=len(self._user_requests))


# Global rate limiter instance
rate_limiter = RateLimiter()

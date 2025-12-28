"""API rate limiting middleware for FastAPI endpoints."""

import hashlib
import time
from collections import defaultdict
from typing import Dict, Optional, Tuple

import structlog
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)


class APIRateLimiter:
    """
    Rate limiter for API endpoints using sliding window algorithm.

    **Important**: This implementation stores request history in memory, which:
    - Does NOT work with multiple workers (each worker has separate memory)
    - Has unbounded memory growth without cleanup (mitigated by 1-hour cleanup)
    - Will lose rate limit state on restart

    **For Production**: Use Redis-backed rate limiting for:
    - Multi-worker deployments
    - Persistent rate limit state
    - Distributed systems
    - High-traffic applications

    Example Redis implementation:
        from redis import Redis
        from limits import RateLimitItemPerMinute, RateLimitItemPerHour
        from limits.storage import RedisStorage
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10,
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute per client
            requests_per_hour: Maximum requests per hour per client
            burst_size: Allow burst of requests before applying rate limit
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size

        # Store request timestamps: {client_id: [timestamp1, timestamp2, ...]}
        # WARNING: In-memory storage - see class docstring for production considerations
        self._request_history: Dict[str, list] = defaultdict(list)

        logger.info(
            "Rate limiter initialized",
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            burst_size=burst_size,
        )

    def _get_client_id(self, request: Request) -> str:
        """
        Get client identifier from request.

        Uses X-Forwarded-For if present (for proxy/load balancer),
        otherwise uses client IP.
        """
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Use first IP in X-Forwarded-For chain
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        # For authenticated requests, use token as identifier
        auth_token = request.headers.get("X-Admin-Token") or request.headers.get("X-API-Token")
        if auth_token:
            # Use last 8 chars of token hash for identification
            token_hash = hashlib.sha256(auth_token.encode()).hexdigest()
            return f"token_{token_hash[:8]}"

        return f"ip_{client_ip}"

    def _cleanup_old_requests(self, client_id: str, current_time: float):
        """Remove request timestamps older than 1 hour."""
        if client_id not in self._request_history:
            return

        cutoff_time = current_time - 3600  # 1 hour ago
        self._request_history[client_id] = [
            ts for ts in self._request_history[client_id] if ts > cutoff_time
        ]

        # Remove client if no recent requests
        if not self._request_history[client_id]:
            del self._request_history[client_id]

    def check_rate_limit(self, request: Request) -> Tuple[bool, Optional[str]]:
        """
        Check if request should be rate limited.

        Args:
            request: FastAPI request object

        Returns:
            Tuple of (is_allowed, error_message)
        """
        client_id = self._get_client_id(request)
        current_time = time.time()

        # Cleanup old requests
        self._cleanup_old_requests(client_id, current_time)

        # Get request timestamps for this client
        timestamps = self._request_history[client_id]

        # Check minute limit
        one_minute_ago = current_time - 60
        recent_minute_requests = [ts for ts in timestamps if ts > one_minute_ago]

        if len(recent_minute_requests) >= self.requests_per_minute:
            retry_after = int(60 - (current_time - recent_minute_requests[0]))
            logger.warning(
                "Rate limit exceeded (per minute)",
                client_id=client_id,
                requests_last_minute=len(recent_minute_requests),
                limit=self.requests_per_minute,
            )
            return False, f"Rate limit exceeded. Retry after {retry_after} seconds."

        # Check hour limit
        one_hour_ago = current_time - 3600
        recent_hour_requests = [ts for ts in timestamps if ts > one_hour_ago]

        if len(recent_hour_requests) >= self.requests_per_hour:
            retry_after = int(3600 - (current_time - recent_hour_requests[0]))
            logger.warning(
                "Rate limit exceeded (per hour)",
                client_id=client_id,
                requests_last_hour=len(recent_hour_requests),
                limit=self.requests_per_hour,
            )
            return False, f"Hourly rate limit exceeded. Retry after {retry_after} seconds."

        # Check burst limit
        five_seconds_ago = current_time - 5
        burst_requests = [ts for ts in timestamps if ts > five_seconds_ago]

        if len(burst_requests) >= self.burst_size:
            logger.warning(
                "Burst limit exceeded",
                client_id=client_id,
                burst_requests=len(burst_requests),
                burst_size=self.burst_size,
            )
            return False, "Too many requests. Please slow down."

        # Record this request
        self._request_history[client_id].append(current_time)

        return True, None

    def get_client_stats(self, request: Request) -> Dict:
        """Get rate limit statistics for a client."""
        client_id = self._get_client_id(request)
        current_time = time.time()

        self._cleanup_old_requests(client_id, current_time)

        timestamps = self._request_history.get(client_id, [])

        one_minute_ago = current_time - 60
        one_hour_ago = current_time - 3600

        return {
            "client_id": client_id,
            "requests_last_minute": len([ts for ts in timestamps if ts > one_minute_ago]),
            "requests_last_hour": len([ts for ts in timestamps if ts > one_hour_ago]),
            "limit_per_minute": self.requests_per_minute,
            "limit_per_hour": self.requests_per_hour,
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to apply rate limiting to API endpoints.

    Usage:
        app.add_middleware(RateLimitMiddleware, rate_limiter=limiter)
    """

    def __init__(self, app, rate_limiter: APIRateLimiter):
        super().__init__(app)
        self.rate_limiter = rate_limiter

    async def dispatch(self, request: Request, call_next):
        """Process request and apply rate limiting."""
        # Skip rate limiting for health checks and webhook
        # TODO: Make exempted paths configurable via settings
        exempted_paths = ["/healthz", "/health", "/tg/webhook"]
        if request.url.path in exempted_paths:
            return await call_next(request)

        # Check rate limit
        is_allowed, error_message = self.rate_limiter.check_rate_limit(request)

        if not is_allowed:
            # Extract retry-after time from error message if present
            # Default to 60 seconds if not specified
            retry_after = "60"
            if "Retry after" in error_message:
                try:
                    # Extract number from message like "Retry after 45 seconds"
                    import re

                    match = re.search(r"Retry after (\d+) seconds", error_message)
                    if match:
                        retry_after = match.group(1)
                except:
                    pass

            # Return JSONResponse instead of raising HTTPException
            # to work properly with BaseHTTPMiddleware
            from starlette.responses import JSONResponse

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": error_message},
                headers={"Retry-After": retry_after},
            )

        # Add rate limit info to response headers
        response = await call_next(request)

        stats = self.rate_limiter.get_client_stats(request)
        response.headers["X-RateLimit-Limit-Minute"] = str(self.rate_limiter.requests_per_minute)
        response.headers["X-RateLimit-Limit-Hour"] = str(self.rate_limiter.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Minute"] = str(
            max(0, self.rate_limiter.requests_per_minute - stats["requests_last_minute"])
        )
        response.headers["X-RateLimit-Remaining-Hour"] = str(
            max(0, self.rate_limiter.requests_per_hour - stats["requests_last_hour"])
        )

        return response


# Global rate limiter instance
api_rate_limiter = APIRateLimiter(
    requests_per_minute=60,  # 1 request per second on average
    requests_per_hour=1000,  # ~16 requests per minute sustained
    burst_size=10,  # Allow small bursts
)

"""Tests for API rate limiting."""

import time
from unittest.mock import MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from tgstats.web.rate_limiter import APIRateLimiter, RateLimitMiddleware


class TestAPIRateLimiter:
    """Test API rate limiter functionality."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initializes correctly."""
        limiter = APIRateLimiter(requests_per_minute=10, requests_per_hour=100, burst_size=5)

        assert limiter.requests_per_minute == 10
        assert limiter.requests_per_hour == 100
        assert limiter.burst_size == 5

    def test_get_client_id_from_ip(self):
        """Test client ID extraction from IP address."""
        limiter = APIRateLimiter()

        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.1"
        request.headers = {}

        client_id = limiter._get_client_id(request)
        assert client_id.startswith("ip_")
        assert "192.168.1.1" in client_id

    def test_get_client_id_from_forwarded_header(self):
        """Test client ID extraction from X-Forwarded-For header."""
        limiter = APIRateLimiter()

        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.headers = {"X-Forwarded-For": "203.0.113.1, 198.51.100.1"}

        client_id = limiter._get_client_id(request)
        assert "203.0.113.1" in client_id  # Should use first IP in chain

    def test_get_client_id_from_token(self):
        """Test client ID extraction from auth token."""
        limiter = APIRateLimiter()

        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.1"
        request.headers = {"X-Admin-Token": "test_token_12345"}

        client_id = limiter._get_client_id(request)
        assert client_id.startswith("token_")

    def test_rate_limit_allows_initial_requests(self):
        """Test that initial requests are allowed."""
        limiter = APIRateLimiter(requests_per_minute=5, requests_per_hour=100)

        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.1"
        request.headers = {}

        is_allowed, error_msg = limiter.check_rate_limit(request)
        assert is_allowed is True
        assert error_msg is None

    def test_rate_limit_per_minute_exceeded(self):
        """Test that per-minute rate limit is enforced."""
        limiter = APIRateLimiter(requests_per_minute=3, requests_per_hour=100)

        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.1"
        request.headers = {}

        # Make 3 requests (should be allowed)
        for _ in range(3):
            is_allowed, _ = limiter.check_rate_limit(request)
            assert is_allowed is True

        # 4th request should be blocked
        is_allowed, error_msg = limiter.check_rate_limit(request)
        assert is_allowed is False
        assert "Rate limit exceeded" in error_msg

    def test_rate_limit_per_hour_exceeded(self):
        """Test that per-hour rate limit is enforced."""
        limiter = APIRateLimiter(requests_per_minute=100, requests_per_hour=5)

        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.1"
        request.headers = {}

        # Make 5 requests (should be allowed)
        for _ in range(5):
            is_allowed, _ = limiter.check_rate_limit(request)
            assert is_allowed is True

        # 6th request should be blocked
        is_allowed, error_msg = limiter.check_rate_limit(request)
        assert is_allowed is False
        assert "Hourly rate limit exceeded" in error_msg or "Rate limit exceeded" in error_msg

    def test_burst_limit_exceeded(self):
        """Test that burst limit is enforced."""
        limiter = APIRateLimiter(requests_per_minute=100, requests_per_hour=1000, burst_size=3)

        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.1"
        request.headers = {}

        # Make burst_size requests rapidly (should be allowed)
        for _ in range(3):
            is_allowed, _ = limiter.check_rate_limit(request)
            assert is_allowed is True

        # Next request should be blocked due to burst
        is_allowed, error_msg = limiter.check_rate_limit(request)
        assert is_allowed is False
        assert "Too many requests" in error_msg or "Burst limit" in error_msg.lower()

    def test_rate_limit_different_clients(self):
        """Test that rate limits are per-client."""
        limiter = APIRateLimiter(requests_per_minute=2, requests_per_hour=100)

        request1 = MagicMock(spec=Request)
        request1.client.host = "192.168.1.1"
        request1.headers = {}

        request2 = MagicMock(spec=Request)
        request2.client.host = "192.168.1.2"
        request2.headers = {}

        # Client 1 makes 2 requests (max)
        for _ in range(2):
            is_allowed, _ = limiter.check_rate_limit(request1)
            assert is_allowed is True

        # Client 1's next request should be blocked
        is_allowed, _ = limiter.check_rate_limit(request1)
        assert is_allowed is False

        # But Client 2 should still be allowed
        is_allowed, _ = limiter.check_rate_limit(request2)
        assert is_allowed is True

    def test_cleanup_old_requests(self):
        """Test that old request timestamps are cleaned up."""
        limiter = APIRateLimiter()

        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.1"
        request.headers = {}

        client_id = limiter._get_client_id(request)

        # Add old timestamp
        old_time = time.time() - 7200  # 2 hours ago
        limiter._request_history[client_id].append(old_time)

        # Run cleanup
        limiter._cleanup_old_requests(client_id, time.time())

        # Old timestamp should be removed
        assert old_time not in limiter._request_history.get(client_id, [])

    def test_get_client_stats(self):
        """Test getting client rate limit statistics."""
        limiter = APIRateLimiter(requests_per_minute=10, requests_per_hour=100)

        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.1"
        request.headers = {}

        # Make 3 requests
        for _ in range(3):
            limiter.check_rate_limit(request)

        stats = limiter.get_client_stats(request)

        assert stats["requests_last_minute"] == 3
        assert stats["requests_last_hour"] == 3
        assert stats["limit_per_minute"] == 10
        assert stats["limit_per_hour"] == 100


class TestRateLimitMiddleware:
    """Test rate limit middleware integration."""

    def test_middleware_skips_health_endpoints(self):
        """Test that health check endpoints skip rate limiting."""
        from fastapi import FastAPI

        app = FastAPI()
        limiter = APIRateLimiter(requests_per_minute=1, requests_per_hour=10)

        @app.get("/healthz")
        def health():
            return {"status": "ok"}

        app.add_middleware(RateLimitMiddleware, rate_limiter=limiter)

        client = TestClient(app)

        # Make multiple requests (more than limit)
        for _ in range(5):
            response = client.get("/healthz")
            assert response.status_code == 200

    def test_middleware_applies_rate_limit(self):
        """Test that middleware applies rate limiting to API endpoints."""
        from fastapi import FastAPI

        app = FastAPI()
        limiter = APIRateLimiter(requests_per_minute=2, requests_per_hour=100)

        @app.get("/api/test")
        def test_endpoint():
            return {"status": "ok"}

        app.add_middleware(RateLimitMiddleware, rate_limiter=limiter)

        client = TestClient(app)

        # First 2 requests should succeed
        for _ in range(2):
            response = client.get("/api/test")
            assert response.status_code == 200

        # 3rd request should be rate limited
        response = client.get("/api/test")
        assert response.status_code == 429

    def test_middleware_adds_rate_limit_headers(self):
        """Test that middleware adds rate limit info headers."""
        from fastapi import FastAPI

        app = FastAPI()
        limiter = APIRateLimiter(requests_per_minute=10, requests_per_hour=100)

        @app.get("/api/test")
        def test_endpoint():
            return {"status": "ok"}

        app.add_middleware(RateLimitMiddleware, rate_limiter=limiter)

        client = TestClient(app)

        response = client.get("/api/test")

        assert "X-RateLimit-Limit-Minute" in response.headers
        assert "X-RateLimit-Limit-Hour" in response.headers
        assert "X-RateLimit-Remaining-Minute" in response.headers
        assert "X-RateLimit-Remaining-Hour" in response.headers

        assert response.headers["X-RateLimit-Limit-Minute"] == "10"
        assert response.headers["X-RateLimit-Limit-Hour"] == "100"

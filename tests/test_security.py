"""Tests for security utilities."""

import pytest
from tgstats.utils.security import SecurityUtils, RateLimitHelper
from tgstats.core.exceptions import InvalidInputError


class TestSecurityUtils:
    """Tests for SecurityUtils class."""

    def test_sanitize_string_basic(self):
        """Test basic string sanitization."""
        text = "Hello, World!"
        result = SecurityUtils.sanitize_string(text)
        assert result == "Hello, World!"

    def test_sanitize_string_html_escape(self):
        """Test HTML escaping in sanitization."""
        text = "<script>alert('xss')</script>"
        result = SecurityUtils.sanitize_string(text)
        assert "&lt;" in result
        assert "&gt;" in result
        assert "<script>" not in result

    def test_sanitize_string_max_length(self):
        """Test max length validation."""
        text = "x" * 2000
        with pytest.raises(InvalidInputError):
            SecurityUtils.sanitize_string(text, max_length=1000)

    def test_sanitize_string_null_bytes(self):
        """Test null byte removal."""
        text = "Hello\x00World"
        result = SecurityUtils.sanitize_string(text)
        assert "\x00" not in result
        assert result == "HelloWorld"

    def test_check_sql_injection_detected(self):
        """Test SQL injection detection."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1 OR 1=1",
            "admin' --",
            "UNION SELECT * FROM users",
        ]
        for text in malicious_inputs:
            assert SecurityUtils.check_sql_injection(text) is True

    def test_check_sql_injection_safe(self):
        """Test safe strings pass SQL injection check."""
        safe_inputs = [
            "Hello World",
            "user@example.com",
            "Normal text with numbers 123",
        ]
        for text in safe_inputs:
            assert SecurityUtils.check_sql_injection(text) is False

    def test_check_xss_detected(self):
        """Test XSS detection."""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "javascript:void(0)",
            "<img src=x onerror=alert('xss')>",
            "<iframe src='evil.com'>",
        ]
        for text in malicious_inputs:
            assert SecurityUtils.check_xss(text) is True

    def test_check_xss_safe(self):
        """Test safe strings pass XSS check."""
        safe_inputs = [
            "Hello World",
            "Click here: https://example.com",
            "Normal text",
        ]
        for text in safe_inputs:
            assert SecurityUtils.check_xss(text) is False

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        assert SecurityUtils.sanitize_filename("file.txt") == "file.txt"
        assert SecurityUtils.sanitize_filename("../../../etc/passwd") == "etcpasswd"
        assert SecurityUtils.sanitize_filename("file name.txt") == "file_name.txt"
        assert SecurityUtils.sanitize_filename(".hidden") == "hidden"

    def test_validate_safe_string_valid(self):
        """Test validation of safe strings."""
        safe_text = "Hello World 123"
        result = SecurityUtils.validate_safe_string(safe_text, allow_special_chars=False)
        assert result == safe_text

    def test_validate_safe_string_sql_injection(self):
        """Test validation rejects SQL injection."""
        malicious = "'; DROP TABLE users; --"
        with pytest.raises(InvalidInputError, match="SQL injection"):
            SecurityUtils.validate_safe_string(malicious)

    def test_validate_safe_string_xss(self):
        """Test validation rejects XSS."""
        malicious = "<script>alert('xss')</script>"
        with pytest.raises(InvalidInputError, match="XSS"):
            SecurityUtils.validate_safe_string(malicious)

    def test_mask_sensitive_data(self):
        """Test sensitive data masking."""
        text = "My phone is 1234567890"
        result = SecurityUtils.mask_sensitive_data(text)
        assert "1234567890" not in result
        assert "12******90" in result

    def test_generate_secure_token(self):
        """Test secure token generation."""
        token1 = SecurityUtils.generate_secure_token(32)
        token2 = SecurityUtils.generate_secure_token(32)
        
        assert len(token1) == 64  # 32 bytes = 64 hex chars
        assert len(token2) == 64
        assert token1 != token2  # Should be unique

    def test_validate_api_token_valid(self):
        """Test valid API token validation."""
        valid_token = "a" * 64
        assert SecurityUtils.validate_api_token(valid_token) is True

    def test_validate_api_token_invalid(self):
        """Test invalid API token validation."""
        assert SecurityUtils.validate_api_token("") is False
        assert SecurityUtils.validate_api_token("short") is False
        assert SecurityUtils.validate_api_token("invalid!@#$%") is False


class TestRateLimitHelper:
    """Tests for RateLimitHelper class."""

    def test_rate_limit_not_exceeded(self):
        """Test rate limit not exceeded under threshold."""
        limiter = RateLimitHelper()
        
        # Make 5 requests (under limit of 10)
        for i in range(5):
            exceeded = limiter.check_rate_limit("user123", max_requests=10, window_seconds=60)
            assert exceeded is False

    def test_rate_limit_exceeded(self):
        """Test rate limit exceeded when over threshold."""
        limiter = RateLimitHelper()
        
        # Make 11 requests (over limit of 10)
        for i in range(10):
            limiter.check_rate_limit("user123", max_requests=10, window_seconds=60)
        
        # 11th request should exceed limit
        exceeded = limiter.check_rate_limit("user123", max_requests=10, window_seconds=60)
        assert exceeded is True

    def test_rate_limit_different_identifiers(self):
        """Test rate limits are separate for different identifiers."""
        limiter = RateLimitHelper()
        
        # User 1 makes 10 requests
        for i in range(10):
            limiter.check_rate_limit("user1", max_requests=10, window_seconds=60)
        
        # User 2 should not be affected
        exceeded = limiter.check_rate_limit("user2", max_requests=10, window_seconds=60)
        assert exceeded is False

    def test_rate_limit_window_reset(self):
        """Test rate limit resets after window expires."""
        import time
        
        limiter = RateLimitHelper()
        
        # Make requests that should expire
        for i in range(5):
            limiter.check_rate_limit("user123", max_requests=10, window_seconds=1)
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Should be able to make more requests
        exceeded = limiter.check_rate_limit("user123", max_requests=10, window_seconds=1)
        assert exceeded is False

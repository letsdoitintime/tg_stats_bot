"""Security utilities for the TG Stats Bot.

Provides input sanitization, SQL injection prevention, and security helpers.
"""

import re
from typing import Optional
import html

import structlog

from ..core.exceptions import InvalidInputError

logger = structlog.get_logger(__name__)


class SecurityUtils:
    """Security utilities for input sanitization and validation."""

    # SQL injection patterns to detect
    SQL_INJECTION_PATTERNS = [
        r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)",
        r"(--|;|\/\*|\*\/|xp_|sp_)",
        r"(\bor\b\s+\d+\s*=\s*\d+)",
        r"(\band\b\s+\d+\s*=\s*\d+)",
        r"('|\"|`)",
    ]

    # XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe",
        r"<object",
        r"<embed",
    ]

    # Compiled regex patterns
    _sql_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in SQL_INJECTION_PATTERNS]
    _xss_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in XSS_PATTERNS]

    @classmethod
    def sanitize_string(cls, text: str, max_length: int = 1000) -> str:
        """
        Sanitize user input string.

        Args:
            text: Input text to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized string

        Raises:
            InvalidInputError: If input is too long
        """
        if not text:
            return ""

        # Check length
        if len(text) > max_length:
            raise InvalidInputError(f"Input too long. Maximum {max_length} characters allowed.")

        # HTML escape
        sanitized = html.escape(text)

        # Remove null bytes
        sanitized = sanitized.replace("\x00", "")

        return sanitized.strip()

    @classmethod
    def check_sql_injection(cls, text: str) -> bool:
        """
        Check if text contains potential SQL injection patterns.

        Args:
            text: Text to check

        Returns:
            True if potential SQL injection detected, False otherwise
        """
        if not text:
            return False

        for pattern in cls._sql_patterns:
            if pattern.search(text):
                logger.warning(
                    "Potential SQL injection detected", text=text[:100], pattern=pattern.pattern
                )
                return True

        return False

    @classmethod
    def check_xss(cls, text: str) -> bool:
        """
        Check if text contains potential XSS patterns.

        Args:
            text: Text to check

        Returns:
            True if potential XSS detected, False otherwise
        """
        if not text:
            return False

        for pattern in cls._xss_patterns:
            if pattern.search(text):
                logger.warning("Potential XSS detected", text=text[:100], pattern=pattern.pattern)
                return True

        return False

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Sanitize filename to prevent directory traversal.

        Args:
            filename: Filename to sanitize

        Returns:
            Sanitized filename
        """
        if not filename:
            return ""

        # Remove path separators and null bytes
        sanitized = filename.replace("/", "").replace("\\", "").replace("\x00", "")

        # Remove leading dots to prevent hidden files
        sanitized = sanitized.lstrip(".")

        # Allow only alphanumeric, dash, underscore, and dot
        sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", sanitized)

        # Limit length
        if len(sanitized) > 255:
            sanitized = sanitized[:255]

        return sanitized

    @classmethod
    def validate_safe_string(cls, text: str, allow_special_chars: bool = False) -> str:
        """
        Validate that string is safe (no SQL injection or XSS).

        Args:
            text: Text to validate
            allow_special_chars: Whether to allow special characters

        Returns:
            Validated string

        Raises:
            InvalidInputError: If text contains malicious patterns
        """
        if not text:
            return ""

        # Check for SQL injection
        if cls.check_sql_injection(text):
            raise InvalidInputError("Invalid input: potential SQL injection detected")

        # Check for XSS
        if cls.check_xss(text):
            raise InvalidInputError("Invalid input: potential XSS detected")

        # If special chars not allowed, validate alphanumeric + basic punctuation
        if not allow_special_chars:
            if not re.match(r"^[a-zA-Z0-9\s.,!?@#$%&*()_+=\-]+$", text):
                raise InvalidInputError("Input contains invalid characters")

        return text

    @classmethod
    def mask_sensitive_data(cls, text: str, pattern: str = r"\d{10,}") -> str:
        """
        Mask sensitive data in text (e.g., phone numbers, IDs).

        Args:
            text: Text containing sensitive data
            pattern: Regex pattern to match sensitive data

        Returns:
            Text with masked sensitive data
        """
        if not text:
            return ""

        def mask_match(match):
            """Mask matched text."""
            matched_text = match.group(0)
            if len(matched_text) <= 4:
                return "*" * len(matched_text)
            # Show first 2 and last 2 characters
            return matched_text[:2] + "*" * (len(matched_text) - 4) + matched_text[-2:]

        return re.sub(pattern, mask_match, text)

    @classmethod
    def generate_secure_token(cls, length: int = 32) -> str:
        """
        Generate a secure random token.

        Args:
            length: Token length in bytes

        Returns:
            Hex-encoded secure token
        """
        import secrets

        return secrets.token_hex(length)

    @classmethod
    def validate_api_token(cls, token: str) -> bool:
        """
        Validate API token format.

        Args:
            token: API token to validate

        Returns:
            True if token format is valid
        """
        if not token:
            return False

        # Token should be at least 32 characters
        if len(token) < 32:
            return False

        # Token should be alphanumeric (hex)
        if not re.match(r"^[a-zA-Z0-9]+$", token):
            return False

        return True


class RateLimitHelper:
    """Helper for implementing rate limiting."""

    def __init__(self):
        self._request_counts = {}
        self._last_cleanup = None

    def check_rate_limit(self, identifier: str, max_requests: int, window_seconds: int) -> bool:
        """
        Check if identifier has exceeded rate limit.

        Args:
            identifier: Unique identifier (e.g., user_id, IP)
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds

        Returns:
            True if rate limit exceeded, False otherwise
        """
        import time

        current_time = time.time()

        # Cleanup old entries periodically
        if not self._last_cleanup or (current_time - self._last_cleanup) > 3600:
            self._cleanup_old_entries(current_time, window_seconds * 2)
            self._last_cleanup = current_time

        # Get request history for identifier
        if identifier not in self._request_counts:
            self._request_counts[identifier] = []

        # Remove old requests outside window
        cutoff_time = current_time - window_seconds
        self._request_counts[identifier] = [
            req_time for req_time in self._request_counts[identifier] if req_time > cutoff_time
        ]

        # Check if limit exceeded
        if len(self._request_counts[identifier]) >= max_requests:
            logger.warning(
                "Rate limit exceeded",
                identifier=identifier,
                count=len(self._request_counts[identifier]),
                max_requests=max_requests,
            )
            return True

        # Add current request
        self._request_counts[identifier].append(current_time)
        return False

    def _cleanup_old_entries(self, current_time: float, max_age: int):
        """Remove old entries to prevent memory bloat."""
        cutoff = current_time - max_age
        for identifier in list(self._request_counts.keys()):
            self._request_counts[identifier] = [
                t for t in self._request_counts[identifier] if t > cutoff
            ]
            if not self._request_counts[identifier]:
                del self._request_counts[identifier]


# Global rate limiter instance
rate_limiter = RateLimitHelper()

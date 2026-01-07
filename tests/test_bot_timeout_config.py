"""Tests for bot timeout configuration and validation."""

import pytest
from pydantic import ValidationError

from tgstats.core.config import Settings


class TestBotTimeoutConfiguration:
    """Test bot timeout configuration and validation."""

    def test_default_timeout_values(self):
        """Test default timeout values are properly configured."""
        # Create settings with minimal required fields
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql://localhost/test",
        )

        # Verify default timeouts
        assert settings.bot_read_timeout == 40.0
        assert settings.bot_write_timeout == 15.0
        assert settings.bot_connect_timeout == 15.0
        assert settings.bot_pool_timeout == 15.0
        assert settings.bot_get_updates_timeout == 30
        assert settings.bot_get_updates_read_timeout == 50.0
        assert settings.bot_get_updates_connect_timeout == 20.0
        assert settings.bot_get_updates_pool_timeout == 20.0
        assert settings.bot_poll_interval == 0.0
        assert settings.bot_bootstrap_retries == -1

    def test_valid_get_updates_timeout_config(self):
        """Test valid get_updates timeout configuration."""
        # get_updates_read_timeout > get_updates_timeout + 10
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql://localhost/test",
            bot_get_updates_timeout=30,
            bot_get_updates_read_timeout=50.0,  # 30 + 20 = valid
        )

        assert settings.bot_get_updates_timeout == 30
        assert settings.bot_get_updates_read_timeout == 50.0

    def test_invalid_get_updates_timeout_too_low(self):
        """Test that get_updates_read_timeout must be > get_updates_timeout + 10."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                bot_token="test_token",
                database_url="postgresql://localhost/test",
                bot_get_updates_timeout=30,
                bot_get_updates_read_timeout=35.0,  # Too low (< 30 + 10)
            )

        error = str(exc_info.value)
        assert "bot_get_updates_read_timeout" in error
        assert "must be at least" in error

    def test_invalid_get_updates_timeout_exact_boundary(self):
        """Test boundary condition for get_updates_read_timeout."""
        # Exactly at boundary should PASS (>= not just >)
        # This is correct: read_timeout must be >= get_updates_timeout + 10
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql://localhost/test",
            bot_get_updates_timeout=30,
            bot_get_updates_read_timeout=40.0,  # Exactly 30 + 10 = valid (>=)
        )
        assert settings.bot_get_updates_read_timeout == 40.0

        # Below boundary should fail
        with pytest.raises(ValidationError):
            Settings(
                bot_token="test_token",
                database_url="postgresql://localhost/test",
                bot_get_updates_timeout=30,
                bot_get_updates_read_timeout=39.9,  # < 40, should fail
            )

    def test_custom_timeout_values(self):
        """Test custom timeout values."""
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql://localhost/test",
            bot_read_timeout=60.0,
            bot_write_timeout=20.0,
            bot_connect_timeout=25.0,
            bot_get_updates_timeout=40,
            bot_get_updates_read_timeout=60.0,  # 40 + 20 = valid
            bot_poll_interval=1.0,
            bot_bootstrap_retries=5,
        )

        assert settings.bot_read_timeout == 60.0
        assert settings.bot_write_timeout == 20.0
        assert settings.bot_connect_timeout == 25.0
        assert settings.bot_get_updates_timeout == 40
        assert settings.bot_get_updates_read_timeout == 60.0
        assert settings.bot_poll_interval == 1.0
        assert settings.bot_bootstrap_retries == 5

    def test_large_get_updates_timeout(self):
        """Test with larger get_updates_timeout values."""
        # Some bots might use longer polling timeouts
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql://localhost/test",
            bot_get_updates_timeout=60,
            bot_get_updates_read_timeout=80.0,  # 60 + 20 = valid
        )

        assert settings.bot_get_updates_timeout == 60
        assert settings.bot_get_updates_read_timeout == 80.0

    def test_bootstrap_retries_values(self):
        """Test different bootstrap_retries values."""
        # Infinite retries
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql://localhost/test",
            bot_bootstrap_retries=-1,
        )
        assert settings.bot_bootstrap_retries == -1

        # No retries
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql://localhost/test",
            bot_bootstrap_retries=0,
        )
        assert settings.bot_bootstrap_retries == 0

        # Limited retries
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql://localhost/test",
            bot_bootstrap_retries=10,
        )
        assert settings.bot_bootstrap_retries == 10

    def test_poll_interval_values(self):
        """Test different poll_interval values."""
        # No delay
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql://localhost/test",
            bot_poll_interval=0.0,
        )
        assert settings.bot_poll_interval == 0.0

        # Small delay
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql://localhost/test",
            bot_poll_interval=0.5,
        )
        assert settings.bot_poll_interval == 0.5

        # Larger delay
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql://localhost/test",
            bot_poll_interval=2.0,
        )
        assert settings.bot_poll_interval == 2.0

    def test_connection_pool_size_validation(self):
        """Test connection pool size validation."""
        # Valid pool size
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql://localhost/test",
            bot_connection_pool_size=16,
        )
        assert settings.bot_connection_pool_size == 16

        # Invalid pool size (0 or negative)
        with pytest.raises(ValidationError):
            Settings(
                bot_token="test_token",
                database_url="postgresql://localhost/test",
                bot_connection_pool_size=0,
            )

    def test_timeout_calculation_examples(self):
        """Test various timeout calculation examples for documentation."""
        # Example 1: Default configuration
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql://localhost/test",
        )
        assert settings.bot_get_updates_read_timeout > settings.bot_get_updates_timeout + 10

        # Example 2: High-latency network
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql://localhost/test",
            bot_get_updates_timeout=45,
            bot_get_updates_read_timeout=70.0,  # Extra buffer for high latency
        )
        assert settings.bot_get_updates_read_timeout > settings.bot_get_updates_timeout + 10

        # Example 3: Quick polling
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql://localhost/test",
            bot_get_updates_timeout=10,
            bot_get_updates_read_timeout=25.0,
        )
        assert settings.bot_get_updates_read_timeout > settings.bot_get_updates_timeout + 10

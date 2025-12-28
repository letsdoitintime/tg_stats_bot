"""Tests for database connection handling and error recovery."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from tgstats.core.exceptions import DatabaseConnectionError
from tgstats.db import verify_database_connection, verify_sync_database_connection
from tgstats.utils.db_retry import with_db_retry


class TestDatabaseConnectionHandling:
    """Test database connection error handling."""

    @pytest.mark.asyncio
    async def test_verify_database_connection_success(self):
        """Test successful database connection verification."""
        with patch("tgstats.db.async_session") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            result = await verify_database_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_verify_database_connection_failure(self):
        """Test database connection verification failure."""
        with patch("tgstats.db.async_session") as mock_session:
            mock_session.return_value.__aenter__.side_effect = OperationalError(
                "connection failed", None, None
            )

            result = await verify_database_connection()
            assert result is False

    def test_verify_sync_database_connection_success(self):
        """Test successful sync database connection verification."""
        with patch("tgstats.db.get_sync_session") as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value.__enter__.return_value = mock_session

            result = verify_sync_database_connection()
            assert result is True

    def test_verify_sync_database_connection_failure(self):
        """Test sync database connection verification failure."""
        with patch("tgstats.db.get_sync_session") as mock_get_session:
            mock_get_session.return_value.__enter__.side_effect = OperationalError(
                "connection failed", None, None
            )

            result = verify_sync_database_connection()
            assert result is False


class TestDatabaseRetry:
    """Test database retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        """Test that transient errors trigger retry."""
        call_count = 0

        @with_db_retry
        async def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OperationalError("connection timeout", None, None)
            return "success"

        with patch("tgstats.core.config.settings") as mock_settings:
            mock_settings.db_retry_attempts = 3
            mock_settings.db_retry_delay = 0.01

            result = await failing_function()
            assert result == "success"
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_non_transient_error(self):
        """Test that non-transient errors don't trigger retry."""
        call_count = 0

        @with_db_retry
        async def failing_function():
            nonlocal call_count
            call_count += 1
            raise OperationalError("syntax error in SQL", None, None)

        with patch("tgstats.core.config.settings") as mock_settings:
            mock_settings.db_retry_attempts = 3
            mock_settings.db_retry_delay = 0.01

            with pytest.raises(OperationalError):
                await failing_function()

            assert call_count == 1  # Should not retry

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test that max retries are respected."""
        call_count = 0

        @with_db_retry
        async def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise OperationalError("connection reset", None, None)

        with patch("tgstats.core.config.settings") as mock_settings:
            mock_settings.db_retry_attempts = 3
            mock_settings.db_retry_delay = 0.01

            with pytest.raises(OperationalError):
                await always_failing_function()

            assert call_count == 3  # Should retry max times


class TestConnectionPoolMonitoring:
    """Test connection pool event listeners."""

    def test_connection_pool_events_are_registered(self):
        """Test that connection pool event listeners are registered."""
        from sqlalchemy import event
        from sqlalchemy.pool import Pool

        # Check that our event listeners are registered
        listeners = event.contains(Pool, "connect")
        assert listeners is True, "Pool connect event listener should be registered"

        listeners = event.contains(Pool, "checkout")
        assert listeners is True, "Pool checkout event listener should be registered"

        listeners = event.contains(Pool, "checkin")
        assert listeners is True, "Pool checkin event listener should be registered"


class TestSessionErrorHandling:
    """Test session-level error handling."""

    @pytest.mark.asyncio
    async def test_session_operational_error_handling(self):
        """Test that operational errors in sessions are properly handled."""
        with patch("tgstats.db.async_session") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__.return_value = mock_session_instance
            mock_session_instance.execute.side_effect = OperationalError(
                "connection lost", None, None
            )

            from tgstats.db import get_session

            async_gen = get_session()
            session = await async_gen.__anext__()

            with pytest.raises(DatabaseConnectionError):
                await session.execute("SELECT 1")

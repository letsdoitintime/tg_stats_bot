"""Tests for database connection handling and error recovery."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

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
        """Our pool listeners are registered for connect/checkout/checkin.

        event.contains() takes (target, identifier, fn) — the two-argument form
        this used does not exist, so it raised TypeError rather than checking
        anything. Naming the actual functions also makes the assertion
        meaningful: it now fails if OUR listener is removed, not merely if some
        unrelated library registered one.
        """
        from sqlalchemy import event
        from sqlalchemy.pool import Pool

        from tgstats.db import receive_checkin, receive_checkout, receive_connect

        for identifier, fn in (
            ("connect", receive_connect),
            ("checkout", receive_checkout),
            ("checkin", receive_checkin),
        ):
            assert event.contains(
                Pool, identifier, fn
            ), f"Pool {identifier} listener {fn.__name__} should be registered"


class TestSessionErrorHandling:
    """Test session-level error handling."""

    @pytest.mark.asyncio
    async def test_session_operational_error_handling(self):
        """An OperationalError escaping the request becomes DatabaseConnectionError.

        get_session() yields inside its try/except, so it only observes
        exceptions thrown back INTO the generator — which is what the framework
        does when a request handler raises. The previous version called
        session.execute() in its own frame, where the generator could never see
        it, and patched tgstats.db.async_session without ever attaching the mock
        it built, so a real session was used regardless.
        """
        from tgstats.db import get_session

        mock_session = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("tgstats.db.async_session", return_value=mock_cm):
            async_gen = get_session()
            session = await async_gen.__anext__()
            assert session is mock_session

            with pytest.raises(DatabaseConnectionError):
                await async_gen.athrow(OperationalError("connection lost", None, None))

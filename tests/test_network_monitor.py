"""Tests for network error handling and monitoring."""

import asyncio

import pytest

from tgstats.utils.network_monitor import NetworkHealthMonitor, get_network_monitor


class TestNetworkHealthMonitor:
    """Test NetworkHealthMonitor class."""

    def test_init(self):
        """Test monitor initialization."""
        monitor = NetworkHealthMonitor()
        assert monitor._network_errors_count == 0
        assert monitor._consecutive_errors == 0
        assert monitor._last_error_time is None
        assert monitor._last_success_time is None
        assert len(monitor._recent_errors) == 0

    def test_record_error(self):
        """Test recording network errors."""
        monitor = NetworkHealthMonitor()

        # Record first error
        monitor.record_error("NetworkError", "Connection failed")
        assert monitor._network_errors_count == 1
        assert monitor._consecutive_errors == 1
        assert monitor._last_error_time is not None
        assert "NetworkError" in monitor._error_types
        assert len(monitor._recent_errors) == 1

        # Record second error
        monitor.record_error("TimedOut", "Request timed out")
        assert monitor._network_errors_count == 2
        assert monitor._consecutive_errors == 2
        assert len(monitor._recent_errors) == 2

    def test_record_success(self):
        """Test recording successful operations."""
        monitor = NetworkHealthMonitor()

        # Record some errors
        for _ in range(5):
            monitor.record_error("NetworkError", "Error")

        assert monitor._consecutive_errors == 5

        # Record success should reset consecutive errors
        monitor.record_success()
        assert monitor._consecutive_errors == 0
        assert monitor._last_success_time is not None
        # Total errors should remain
        assert monitor._network_errors_count == 5

    def test_get_health_status(self):
        """Test getting health status."""
        monitor = NetworkHealthMonitor()

        # Initial status
        status = monitor.get_health_status()
        assert status["total_errors"] == 0
        assert status["consecutive_errors"] == 0
        assert status["is_healthy"] is True

        # After errors
        for _ in range(3):
            monitor.record_error("NetworkError", "Error")

        status = monitor.get_health_status()
        assert status["total_errors"] == 3
        assert status["consecutive_errors"] == 3
        assert status["is_healthy"] is True  # < 5 consecutive

        # More errors
        for _ in range(3):
            monitor.record_error("NetworkError", "Error")

        status = monitor.get_health_status()
        assert status["consecutive_errors"] == 6
        assert status["is_healthy"] is False  # >= 5 consecutive

    def test_is_degraded(self):
        """Test degraded status detection."""
        monitor = NetworkHealthMonitor()

        # Not degraded initially
        assert monitor.is_degraded() is False

        # Record 2 errors - not yet degraded
        monitor.record_error("NetworkError", "Error")
        monitor.record_error("NetworkError", "Error")
        assert monitor.is_degraded() is False

        # 3rd error - now degraded
        monitor.record_error("NetworkError", "Error")
        assert monitor.is_degraded() is True

        # Recovery
        monitor.record_success()
        assert monitor.is_degraded() is False

    def test_should_alert(self):
        """Test alert condition detection."""
        monitor = NetworkHealthMonitor()

        # No alert initially
        assert monitor.should_alert() is False

        # Less than 10 consecutive - no alert
        for _ in range(9):
            monitor.record_error("NetworkError", "Error")
        assert monitor.should_alert() is False

        # 10 consecutive - alert
        monitor.record_error("NetworkError", "Error")
        assert monitor.should_alert() is True

    def test_error_types_tracking(self):
        """Test tracking different error types."""
        monitor = NetworkHealthMonitor()

        monitor.record_error("NetworkError", "Error 1")
        monitor.record_error("NetworkError", "Error 2")
        monitor.record_error("TimedOut", "Timeout")
        monitor.record_error("BadGateway", "502")

        status = monitor.get_health_status()
        assert status["error_types"]["NetworkError"] == 2
        assert status["error_types"]["TimedOut"] == 1
        assert status["error_types"]["BadGateway"] == 1

    @pytest.mark.asyncio
    async def test_periodic_health_check(self):
        """Test periodic health check logging."""
        monitor = NetworkHealthMonitor()

        # Start health check with short interval
        task = asyncio.create_task(monitor.periodic_health_check(interval_seconds=0.1))

        # Let it run briefly
        await asyncio.sleep(0.3)

        # Cancel the task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # No errors, just verify it ran without exception


def test_get_network_monitor_singleton():
    """Test global network monitor singleton."""
    monitor1 = get_network_monitor()
    monitor2 = get_network_monitor()

    # Should return the same instance
    assert monitor1 is monitor2

    # Should be a NetworkHealthMonitor
    assert isinstance(monitor1, NetworkHealthMonitor)

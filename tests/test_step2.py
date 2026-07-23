"""Additional tests for Step 2 functionality."""

from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest

from tgstats.web.date_utils import parse_period, rotate_heatmap_rows, to_local_date
from tgstats.web.query_utils import (
    build_heatmap_query,
    build_timeseries_query,
    get_aggregate_table_name,
    get_group_tz,
)


class TestTimezoneHandling:
    """Test timezone-related functionality."""

    def test_parse_period_default(self):
        """Test parse_period with default values."""
        tz = ZoneInfo("UTC")
        start_utc, end_utc, days = parse_period(tz=tz)

        assert days == 30
        assert start_utc < end_utc
        assert (end_utc - start_utc).days >= 29  # Account for time differences

    def test_parse_period_custom_dates(self):
        """Test parse_period with custom dates."""
        tz = ZoneInfo("Europe/Sofia")  # UTC+2/+3
        start_utc, end_utc, days = parse_period(from_date="2025-01-01", to_date="2025-01-07", tz=tz)

        assert days == 7
        # Sofia is ahead of UTC, so 2025-01-01 00:00 Sofia is 2024-12-31 22:00 UTC.
        # Assert the instant, not the hour number — the old `start_utc.hour < 12`
        # compared 22 < 12 and could only ever have passed for a timezone behind UTC.
        assert start_utc == datetime(2024, 12, 31, 22, 0)

    def test_parse_period_sofia_timezone(self):
        """Test timezone handling for Europe/Sofia specifically."""
        tz = ZoneInfo("Europe/Sofia")

        # Test winter time (UTC+2)
        start_utc, end_utc, days = parse_period(from_date="2025-01-15", to_date="2025-01-15", tz=tz)

        # Should convert from Sofia local to UTC
        # Start of day in Sofia (00:00) = 22:00 UTC previous day
        # End of day in Sofia (23:59) = 21:59 UTC same day
        assert start_utc.day == 14  # Previous day in UTC
        assert start_utc.hour == 22
        assert end_utc.day == 15
        assert end_utc.hour == 21

    def test_local_date_bounds_west_of_utc(self):
        """Daily-aggregate bounds must be LOCAL dates, not end_utc.date().

        Regression test. Moving to_date to the local end of day (correct for
        timestamp ranges) pushes end_utc onto the NEXT UTC date for any timezone
        west of UTC: America/Los_Angeles to=2025-01-07 gives end_utc
        2025-01-08 07:59. chat_daily[_mv] / user_chat_daily[_mv] are keyed by
        local date, so bounding them with end_utc.date() silently included an
        extra day. Every existing test used UTC or Europe/Sofia (both at or east
        of UTC), where the bug is invisible.
        """
        tz = ZoneInfo("America/Los_Angeles")
        start_utc, end_utc, days = parse_period(from_date="2025-01-01", to_date="2025-01-07", tz=tz)

        # The raw UTC instant does land on the next day — that part is correct,
        # it is what makes the timestamp range cover all of 7 Jan locally.
        assert end_utc.date().isoformat() == "2025-01-08"

        # ...but the aggregate bound must be the local date that was asked for.
        assert to_local_date(start_utc, tz).isoformat() == "2025-01-01"
        assert to_local_date(end_utc, tz).isoformat() == "2025-01-07"
        assert days == 7

    def test_local_date_bounds_east_of_utc_and_utc(self):
        """Same bounds hold at and east of UTC."""
        for name in ("UTC", "Europe/Sofia"):
            tz = ZoneInfo(name)
            start_utc, end_utc, _ = parse_period(
                from_date="2025-01-01", to_date="2025-01-07", tz=tz
            )
            assert to_local_date(start_utc, tz).isoformat() == "2025-01-01", name
            assert to_local_date(end_utc, tz).isoformat() == "2025-01-07", name

    def test_get_group_tz_with_settings(self):
        """Test getting group timezone from settings."""
        # Mock session and settings
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.timezone = "Europe/Sofia"
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_settings

        tz = get_group_tz(12345, mock_session)
        assert str(tz) == "Europe/Sofia"

    def test_get_group_tz_default(self):
        """Test getting default timezone when no settings."""
        mock_session = Mock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        tz = get_group_tz(12345, mock_session)
        assert str(tz) == "UTC"


class TestHeatmapRotation:
    """Test heatmap timezone rotation."""

    def test_rotate_heatmap_utc(self):
        """Test heatmap rotation for UTC timezone."""
        # Sample data: Monday 14:00 UTC with 10 messages
        rows = [
            (
                datetime(2025, 1, 20, 14, 0),  # hour_bucket
                1,  # weekday (Monday)
                14,  # hour
                10,  # msg_cnt
            )
        ]

        tz = ZoneInfo("UTC")
        matrix = rotate_heatmap_rows(rows, tz)

        assert matrix[0][14] == 10  # Monday, 14:00 UTC
        assert sum(sum(row) for row in matrix) == 10

    def test_rotate_heatmap_sofia(self):
        """Test heatmap rotation for Sofia timezone."""
        # Sample data: Monday 14:00 UTC = Monday 16:00 Sofia (winter)
        rows = [
            (
                datetime(2025, 1, 20, 14, 0),  # hour_bucket (UTC)
                1,  # weekday (Monday in UTC)
                14,  # hour (UTC)
                10,  # msg_cnt
            )
        ]

        tz = ZoneInfo("Europe/Sofia")
        matrix = rotate_heatmap_rows(rows, tz)

        # Should be rotated to Monday 16:00 Sofia time
        assert matrix[0][16] == 10  # Monday, 16:00 Sofia
        assert sum(sum(row) for row in matrix) == 10

    def test_rotate_heatmap_day_wrap(self):
        """Test heatmap rotation that wraps to next day."""
        # Sample data: Monday 23:00 UTC = Tuesday 01:00 Sofia (winter)
        rows = [
            (
                datetime(2025, 1, 20, 23, 0),  # Monday 23:00 UTC
                1,  # weekday (Monday in UTC)
                23,  # hour (UTC)
                5,  # msg_cnt
            )
        ]

        tz = ZoneInfo("Europe/Sofia")
        matrix = rotate_heatmap_rows(rows, tz)

        # Should be Tuesday 01:00 Sofia time
        assert matrix[1][1] == 5  # Tuesday, 01:00 Sofia
        assert sum(sum(row) for row in matrix) == 5


class TestUserMetrics:
    """Test user statistics calculations."""

    def test_activity_percentage_calculation(self):
        """Test activity percentage calculation logic."""
        # This would test the SQL logic if we had a test database
        # For now, we test the concept
        expected_percentage = (50 / 1000) * 100

        assert expected_percentage == 5.0

    def test_active_days_ratio_format(self):
        """Test active days ratio formatting."""
        active_days = 15
        total_days = 30
        ratio = f"{active_days}/{total_days}"

        assert ratio == "15/30"

    def test_days_since_joined_calculation(self):
        """Test days since joined calculation."""
        from datetime import datetime, timedelta

        joined_date = datetime.now() - timedelta(days=45)
        now = datetime.now()
        days_diff = (now - joined_date).days

        assert 44 <= days_diff <= 46  # Allow for slight timing differences


class TestAggregateQueries:
    """Test aggregate query logic."""

    def test_timescale_vs_postgres_branching(self):
        """TimescaleDB uses continuous aggregates; plain PG uses the _mv views.

        Previously this patched `tgstats.web.app.check_timescaledb_available` —
        a name that does not exist there (it lives in web/query_utils.py) — and
        then asserted nothing at all. It failed on the patch target, not on the
        behaviour, and would have passed with the branching completely broken.
        """
        assert get_aggregate_table_name(True, "chat_daily") == "chat_daily"
        assert get_aggregate_table_name(False, "chat_daily") == "chat_daily_mv"

        # The branch has to reach the SQL, not just the helper.
        for is_timescale, expected in ((True, "chat_daily"), (False, "chat_daily_mv")):
            sql = str(build_timeseries_query(is_timescale, "messages"))
            assert f"FROM {expected}" in sql

        for is_timescale, expected in (
            (True, "chat_hourly_heatmap"),
            (False, "chat_hourly_heatmap_mv"),
        ):
            assert f"FROM {expected}" in str(build_heatmap_query(is_timescale))


@pytest.fixture
def sample_heatmap_data():
    """Sample heatmap data for testing."""
    return [
        # Monday data
        (datetime(2025, 1, 20, 9, 0), 1, 9, 15),  # 9 AM, 15 messages
        (datetime(2025, 1, 20, 12, 0), 1, 12, 25),  # 12 PM, 25 messages
        (datetime(2025, 1, 20, 18, 0), 1, 18, 30),  # 6 PM, 30 messages
        # Tuesday data
        (datetime(2025, 1, 21, 10, 0), 2, 10, 20),  # 10 AM, 20 messages
        (datetime(2025, 1, 21, 15, 0), 2, 15, 18),  # 3 PM, 18 messages
    ]


def test_heatmap_aggregation(sample_heatmap_data):
    """Test that heatmap aggregation works correctly."""
    tz = ZoneInfo("UTC")
    matrix = rotate_heatmap_rows(sample_heatmap_data, tz)

    # Verify specific data points
    assert matrix[0][9] == 15  # Monday 9 AM
    assert matrix[0][12] == 25  # Monday 12 PM
    assert matrix[0][18] == 30  # Monday 6 PM
    assert matrix[1][10] == 20  # Tuesday 10 AM
    assert matrix[1][15] == 18  # Tuesday 3 PM

    # Verify total
    total_messages = sum(sum(row) for row in matrix)
    expected_total = 15 + 25 + 30 + 20 + 18
    assert total_messages == expected_total


def test_timezone_edge_cases():
    """Test edge cases in timezone handling."""
    # Test invalid timezone falls back to UTC
    mock_session = Mock()
    mock_settings = Mock()
    mock_settings.timezone = "Invalid/Timezone"
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_settings

    tz = get_group_tz(12345, mock_session)
    assert str(tz) == "UTC"


if __name__ == "__main__":
    pytest.main([__file__])


class TestAggregateDateBounds:
    """The endpoints must bind LOCAL dates to daily-aggregate queries.

    These call the router functions with a mocked session and inspect the
    parameters actually bound. Asserting on to_local_date() alone was not
    enough: reverting the call sites to end_utc.date() left the whole suite
    green, because nothing exercised the binding itself.
    """

    @staticmethod
    def _session_returning_nothing():
        session = Mock()
        session.execute.return_value.fetchall.return_value = []
        return session

    @pytest.mark.asyncio
    async def test_timeseries_binds_local_dates(self):
        from tgstats.web.routers import analytics

        session = self._session_returning_nothing()
        with (
            patch.object(analytics, "get_group_tz", return_value=ZoneInfo("America/Los_Angeles")),
            patch.object(analytics, "check_timescaledb_available", return_value=False),
        ):
            await analytics.get_chat_timeseries(
                chat_id=1,
                metric="messages",
                from_date="2025-01-01",
                to_date="2025-01-07",
                session=session,
                _token=None,
            )

        params = session.execute.call_args[0][1]
        assert params["start_date"].isoformat() == "2025-01-01"
        # end_utc is 2025-01-08 07:59 for LA; binding that date would pull in
        # an extra day of chat_daily aggregates.
        assert params["end_date"].isoformat() == "2025-01-07"

    @pytest.mark.asyncio
    async def test_users_binds_local_dates(self):
        from tgstats.web.routers import analytics

        session = self._session_returning_nothing()
        # the users endpoint reads a count via .fetchone().total
        session.execute.return_value.fetchone.return_value = Mock(total=0)
        with (
            patch.object(analytics, "get_group_tz", return_value=ZoneInfo("America/Los_Angeles")),
            patch.object(analytics, "check_timescaledb_available", return_value=False),
        ):
            await analytics.get_chat_users(
                chat_id=1,
                from_date="2025-01-01",
                to_date="2025-01-07",
                sort="act",
                search=None,
                left=None,
                page=1,
                per_page=50,
                session=session,
                _token=None,
            )

        bound = [c[0][1] for c in session.execute.call_args_list if len(c[0]) > 1]
        assert bound, "no parameterised query was executed"
        assert all(p["end_date"].isoformat() == "2025-01-07" for p in bound if "end_date" in p)

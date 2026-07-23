"""Smoke tests: every response_model endpoint must build a VALID response.

Why this file exists. `GET /api/chats/{id}/users` returned HTTP 500 on every
request — it constructed `UserStatsResponse(users=...)` while the schema
declares `items`, with no alias, so pydantic raised on every call. 225 other
tests passed throughout, because nothing had ever invoked an endpoint.

These call the endpoint functions directly with a mocked session and let the
response model validate. That is deliberately shallow — it does not check the
SQL or the numbers — but it catches the entire class of "the handler and its
declared schema disagree", which is invisible until a real request arrives.

Row objects are SimpleNamespace, not Mock: a Mock attribute satisfies getattr
but fails pydantic's int/float coercion, which would make these pass or fail
for the wrong reason.
"""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest

from tgstats.web.routers import analytics, chats

TZ = ZoneInfo("Europe/Sofia")


def _session(fetchall=None, fetchone=None, first=None):
    """Session whose execute() returns fixed rows regardless of the query."""
    session = Mock()
    result = Mock()
    result.fetchall.return_value = fetchall if fetchall is not None else []
    result.fetchone.return_value = fetchone
    session.execute.return_value = result
    session.query.return_value.filter_by.return_value.first.return_value = first
    return session


def _patched(**kwargs):
    """Patch the two module-level helpers every analytics endpoint calls."""
    return (
        patch.object(analytics, "get_group_tz", return_value=TZ),
        patch.object(analytics, "check_timescaledb_available", return_value=False),
    )


class TestChatsRouter:
    @pytest.mark.asyncio
    async def test_get_chats_builds_valid_summaries(self):
        rows = [
            SimpleNamespace(chat_id=-100, title="Group", msg_count_30d=5, avg_dau_30d=1.5),
            SimpleNamespace(chat_id=-200, title=None, msg_count_30d=0, avg_dau_30d=0.0),
        ]
        session = _session(fetchall=rows)
        with patch.object(chats, "check_timescaledb_available", return_value=False):
            out = chats.get_chats(session=session, _token=None)

        assert [c.chat_id for c in out] == [-100, -200]
        # Falls back to a synthetic title when the chat has none
        assert out[1].title == "Chat -200"

    @pytest.mark.asyncio
    async def test_get_chat_settings_builds_valid_response(self):
        settings = SimpleNamespace(
            chat_id=1,
            store_text=True,
            text_retention_days=90,
            metadata_retention_days=365,
            timezone="UTC",
            locale="en",
            capture_reactions=False,
        )
        out = chats.get_chat_settings(chat_id=1, session=_session(first=settings), _token=None)
        assert out.chat_id == 1
        assert out.timezone == "UTC"

    @pytest.mark.asyncio
    async def test_get_chat_settings_404s_when_missing(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            chats.get_chat_settings(chat_id=1, session=_session(first=None), _token=None)
        assert exc.value.status_code == 404


class TestAnalyticsRouter:
    @pytest.mark.asyncio
    async def test_summary_builds_valid_response(self):
        row = SimpleNamespace(
            total_messages=10,
            unique_users=3,
            avg_daily_users=1.5,
            new_users=2,
            left_users=1,
        )
        session = _session(fetchone=row)
        p1, p2 = _patched()
        with p1, p2:
            out = analytics.get_chat_summary(
                chat_id=1,
                from_date="2025-01-01",
                to_date="2025-01-07",
                session=session,
                _token=None,
            )
        assert out.total_messages == 10
        assert out.days == 7
        assert out.start_date == "2025-01-01"
        assert out.end_date == "2025-01-07"

    @pytest.mark.asyncio
    async def test_timeseries_builds_valid_points(self):
        rows = [SimpleNamespace(day=date(2025, 1, 1), value=7)]
        session = _session(fetchall=rows)
        p1, p2 = _patched()
        with p1, p2:
            out = analytics.get_chat_timeseries(
                chat_id=1,
                metric="messages",
                from_date="2025-01-01",
                to_date="2025-01-07",
                session=session,
                _token=None,
            )
        assert out[0].day == "2025-01-01"
        assert out[0].value == 7

    @pytest.mark.asyncio
    async def test_heatmap_builds_matrix_with_matching_labels(self):
        rows = [(datetime(2025, 1, 20, 14, 0), 1, 14, 10)]
        session = _session(fetchall=rows)
        p1, p2 = _patched()
        with p1, p2:
            out = analytics.get_chat_heatmap(
                chat_id=1, from_date=None, to_date=None, session=session, _token=None
            )
        assert out["weekdays"][0] == "Monday"
        assert len(out["data"]) == 7 and len(out["data"][0]) == 24
        # 14:00 UTC Monday is 16:00 Sofia, still Monday -> row 0
        assert out["data"][0][16] == 10

    @pytest.mark.asyncio
    async def test_users_builds_valid_response(self):
        """The regression that motivated this file: items vs users."""
        rows = [
            SimpleNamespace(
                user_id=5,
                username="u",
                first_name="F",
                last_name="L",
                msg_count=3,
                active_days=2,
                activity_pct=1.5,
                joined_at=datetime(2025, 1, 1),
                left_at=None,
                has_left=False,
                last_message_at=datetime(2025, 1, 2),
            )
        ]
        session = _session(fetchall=rows, fetchone=SimpleNamespace(total=1))
        p1, p2 = _patched()
        with p1, p2:
            out = analytics.get_chat_users(
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
        assert out.total == 1
        assert out.pages == 1
        assert len(out.items) == 1
        item = out.items[0]
        assert item.user_id == 5
        assert item.activity_percentage == 1.5
        assert item.active_days_ratio == "2/7"  # active_days / days in period
        assert item.last_message == "2025-01-02T00:00:00"
        assert item.left is False
        assert item.days_since_joined is not None and item.days_since_joined > 0

    @pytest.mark.asyncio
    async def test_retention_preview_builds_valid_response(self):
        # Exactly what celery_tasks.retention_preview() returns
        preview = {
            "chat_id": 1,
            "text_retention_days": 90,
            "metadata_retention_days": 365,
            "store_text": True,
            "text_removal_count": 4,
            "metadata_removal_count": 2,
            "reaction_removal_count": 1,
            "text_cutoff_date": "2024-10-01T00:00:00+00:00",
            "metadata_cutoff_date": "2024-01-01T00:00:00+00:00",
            "preview_generated_at": "2025-01-01T00:00:00+00:00",
        }
        with patch.object(analytics, "retention_preview", return_value=preview):
            out = analytics.preview_retention(chat_id=1, session=_session(), _token=None)
        assert out.chat_id == 1
        assert out.text_removal_count == 4
        assert out.metadata_removal_count == 2
        assert out.reaction_removal_count == 1
        assert out.store_text is True


class TestRealDataShapes:
    """Guards for bugs that only appear against the real database.

    Mocked rows cannot catch these: the columns are TIMESTAMP WITH TIME ZONE,
    so real rows come back timezone-aware while hand-built fixtures are naive.
    """

    def test_days_since_handles_aware_and_naive(self):
        from datetime import timedelta
        from datetime import timezone as dt_timezone

        from tgstats.web.routers.analytics import _days_since

        now = datetime.now(dt_timezone.utc)
        aware = now - timedelta(days=10)
        naive = aware.replace(tzinfo=None)

        # memberships.joined_at is timestamptz -> aware. Subtracting a naive
        # "now" raised "can't subtract offset-naive and offset-aware datetimes"
        # and 500'd /users for every chat that had a joined member.
        assert _days_since(aware, now) == 10
        assert _days_since(naive, now) == 10
        assert _days_since(None, now) is None

    def test_retention_preview_does_not_shadow_datetime_timezone(self):
        """celery_tasks unpacked a DB column into the name `timezone`.

        That shadowed the `datetime.timezone` import, so the next line evaluated
        'UTC'.utc and the task raised AttributeError on every call — which the
        endpoint reported as a 404 "not found".
        """
        from tgstats import celery_tasks

        session = Mock()
        session.execute.return_value.fetchone.side_effect = [
            (90, 365, True, "UTC"),  # settings row: last field is the tz STRING
            (4,),
            (2,),
            (1,),
        ]
        cm = Mock()
        cm.__enter__ = Mock(return_value=session)
        cm.__exit__ = Mock(return_value=False)

        with patch.object(celery_tasks, "get_sync_session", return_value=cm):
            result = celery_tasks.retention_preview(1)

        assert "error" not in result, result.get("error")
        assert result["text_retention_days"] == 90
        assert result["store_text"] is True


class TestReadiness:
    """/health/ready must not be permanently 503 in polling mode."""

    @pytest.mark.asyncio
    async def test_telegram_check_skipped_in_polling_mode(self):
        from tgstats.core.config import settings
        from tgstats.web import health

        with patch.object(settings, "mode", "polling"):
            out = await health.check_telegram_api()

        # The bot is a separate process in polling mode, so this process can
        # never see it; reporting that as unavailable gated readiness forever.
        assert out["available"] is True
        assert "skipped" in out

    @pytest.mark.asyncio
    async def test_telegram_check_runs_in_webhook_mode(self):
        from tgstats.core.config import settings
        from tgstats.web import health

        with patch.object(settings, "mode", "webhook"):
            out = await health.check_telegram_api()

        # No bot application is registered in the test process, so webhook mode
        # must still report an honest failure rather than skipping.
        assert out["available"] is False


class TestTemplateRendering:
    """The UI routes must actually render through the REAL app.

    Regression guard for a genuine breaking change: starlette 1.3 removed the
    old `TemplateResponse(name, context)` positional order in favour of
    `TemplateResponse(request, name, context)`. Under the old call the template
    NAME was read as the request and the context dict as the name, so jinja
    raised "TypeError: unhashable type: 'dict'" and /ui returned 500.

    These go through TestClient against the real app so they exercise app.py's
    OWN call sites. Calling templates.TemplateResponse() directly from the test
    would only re-assert starlette's signature and would pass even with app.py
    still broken — verified: that version of this test caught nothing.
    """

    @staticmethod
    def _client():
        from starlette.testclient import TestClient

        from tgstats.db import get_session
        from tgstats.web.app import app

        class _Result:
            def fetchall(self):
                return []

        class _Session:
            async def execute(self, *a, **k):
                return _Result()

            async def get(self, *a, **k):
                from types import SimpleNamespace

                return SimpleNamespace(
                    chat_id=-100, title="ВелоПокатушки 🇺🇦", type="supergroup"
                )

        async def _fake_session():
            yield _Session()

        app.dependency_overrides[get_session] = _fake_session
        return TestClient(app), app

    def test_ui_chat_list_renders(self):
        client, app = self._client()
        try:
            with client:  # the `with` matters: it runs lifespan
                resp = client.get("/ui")
            assert resp.status_code == 200, resp.text[:200]
            assert "Telegram Analytics" in resp.text
        finally:
            app.dependency_overrides.clear()

    def test_ui_chat_detail_renders(self):
        client, app = self._client()
        try:
            with client:
                resp = client.get("/ui/chat/-100")
            assert resp.status_code == 200, resp.text[:200]
            assert "ВелоПокатушки" in resp.text
        finally:
            app.dependency_overrides.clear()

"""Test configuration and fixtures."""

import asyncio
from datetime import datetime
from unittest.mock import Mock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tgstats.db import Base
from tgstats.models import *  # noqa

# Test database URL (use in-memory SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# SQLite stand-in for the Postgres materialized view created in
# migrations/versions/004_create_aggregates.py. Base.metadata.create_all() only
# builds mapped tables, so the view is absent under SQLite and every heatmap
# query fails with "no such table: chat_hourly_heatmap_mv".
#
# Only the view DEFINITION is re-expressed here — the query under test is the
# production one, unchanged. Column names and semantics match the migration:
# weekday is ISODOW (1=Monday..7=Sunday), hour is 0-23.
#   DATE_TRUNC('hour', date)  -> strftime('%Y-%m-%d %H:00:00', date)
#   EXTRACT(ISODOW FROM date) -> strftime('%w') is 0=Sunday, so 0 maps to 7
#   EXTRACT(HOUR FROM date)   -> strftime('%H', date)
#
# KNOWN DIVERGENCE: SQLite has no timestamp type, so hour_bucket is TEXT here
# where Postgres DATE_TRUNC yields a timestamp. plugins/heatmap/repository.py
# CASTs and string-compares past this, which is what these tests exercise;
# web/date_utils.py:rotate_heatmap_rows would raise TypeError on a TEXT bucket,
# so it is covered by test_step2.py against real datetimes instead.
HEATMAP_MV_SQL = """
CREATE VIEW IF NOT EXISTS chat_hourly_heatmap_mv AS
SELECT
    chat_id,
    strftime('%Y-%m-%d %H:00:00', "date") AS hour_bucket,
    CASE CAST(strftime('%w', "date") AS INTEGER)
        WHEN 0 THEN 7
        ELSE CAST(strftime('%w', "date") AS INTEGER)
    END AS weekday,
    CAST(strftime('%H', "date") AS INTEGER) AS hour,
    COUNT(*) AS msg_cnt,
    COUNT(DISTINCT user_id) AS unique_users
FROM messages
WHERE "date" IS NOT NULL
GROUP BY chat_id, hour_bucket, weekday, hour
"""


async def create_aggregate_views(conn):
    """Create the SQLite stand-ins for the migration's aggregate views."""
    await conn.execute(text(HEATMAP_MV_SQL))


# A bare Mock() auto-creates every attribute as a new Mock, and SQLAlchemy's
# Boolean type rejects those with "Not a boolean value: <Mock ...>". The repos
# read optional Telegram fields with getattr(obj, name, default), and getattr
# always finds the auto-created Mock, so the default never applies. These
# builders give every field the ORM writes a real, correctly typed value.


def make_tg_chat(**overrides):
    """Fake telegram.Chat with real-typed values for every mapped column."""
    chat = Mock()
    chat.id = -1001234567890
    chat.title = "Test Chat"
    chat.username = "testchat"
    chat.type = "supergroup"
    # Booleans — must not be Mocks
    chat.is_forum = False
    chat.has_protected_content = False
    # Optional/nullable fields read via getattr
    chat.description = None
    chat.photo = None
    chat.permissions = None
    chat.pinned_message = None
    chat.invite_link = None
    chat.slow_mode_delay = None
    chat.message_auto_delete_time = None
    chat.linked_chat_id = None
    chat.sticker_set_name = None
    chat.can_set_sticker_set = None
    for key, value in overrides.items():
        setattr(chat, key, value)
    return chat


def make_tg_message(**overrides):
    """Fake telegram.Message with every media slot explicitly empty.

    MagicMock is especially dangerous here: an auto-created `photo` attribute is
    truthy but iterates empty, so `max(tg_message.photo, ...)` in
    message_repository raises "max() iterable argument is empty" — a shape real
    Telegram never produces (photo is either absent or a non-empty tuple).
    """
    message = Mock()
    message.message_id = 1
    message.text = "Test message"
    message.caption = None
    # Entity lists are iterated directly, so they must be real sequences
    message.entities = []
    message.caption_entities = []
    message.date = datetime(2025, 1, 20, 12, 0)
    message.edit_date = None
    # Media — every one of these must be falsy, not an auto-Mock
    for attr in (
        "photo",
        "video",
        "audio",
        "voice",
        "document",
        "sticker",
        "animation",
        "video_note",
        "contact",
        "location",
        "venue",
        "poll",
        "dice",
        "game",
        "web_page",
    ):
        setattr(message, attr, None)
    # Forward / reply metadata
    message.forward_date = None
    message.forward_from = None
    message.forward_from_chat = None
    message.forward_from_message_id = None
    message.forward_signature = None
    message.forward_sender_name = None
    message.reply_to_message = None
    message.via_bot = None
    message.author_signature = None
    message.media_group_id = None
    message.message_thread_id = None
    # Booleans mapped on the Message model — must not be Mocks
    message.is_automatic_forward = False
    message.has_protected_content = False
    for key, value in overrides.items():
        setattr(message, key, value)
    return message


def make_tg_user(**overrides):
    """Fake telegram.User with real-typed values for every mapped column."""
    user = Mock()
    user.id = 123456789
    user.username = "testuser"
    user.first_name = "Test"
    user.last_name = "User"
    user.language_code = "en"
    # Booleans — must not be Mocks
    user.is_bot = False
    user.is_premium = False
    user.added_to_attachment_menu = False
    user.can_join_groups = True
    user.can_read_all_group_messages = False
    user.supports_inline_queries = False
    for key, value in overrides.items():
        setattr(user, key, value)
    return user


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await create_aggregate_views(conn)

    yield engine

    # Clean up
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create a test database session."""
    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

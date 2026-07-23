"""Integration tests for the improved bot architecture."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from conftest import make_tg_chat, make_tg_message, make_tg_user  # tests/ is not a package
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tgstats.core.constants import DEFAULT_CAPTURE_REACTIONS, DEFAULT_STORE_TEXT
from tgstats.models import Chat
from tgstats.services.chat_service import ChatService
from tgstats.services.message_service import MessageService
from tgstats.services.user_service import UserService
from tgstats.utils.cache import CacheManager
from tgstats.utils.rate_limiter import RateLimiter
from tgstats.utils.sanitizer import (
    is_safe_sql_input,
    sanitize_chat_id,
    sanitize_command_arg,
    sanitize_text,
)


@pytest.fixture
async def async_db_session():
    """Create an async in-memory SQLite session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Chat.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def mock_telegram_chat():
    """Mock Telegram chat object.

    Built via the shared helper: a bare MagicMock leaves is_forum and
    has_protected_content as Mock objects, which SQLAlchemy's Boolean rejects
    ("Not a boolean value"), and getattr(..., default) never sees the default
    because the auto-created attribute always exists.
    """
    return make_tg_chat(title="Test Group")


@pytest.fixture
def mock_telegram_user():
    """Mock Telegram user object (see mock_telegram_chat)."""
    return make_tg_user()


@pytest.mark.asyncio
class TestChatService:
    """Test chat service functionality."""

    async def test_get_or_create_chat(self, async_db_session, mock_telegram_chat):
        """Test chat creation."""
        service = ChatService(async_db_session)

        chat = await service.get_or_create_chat(mock_telegram_chat)

        assert chat is not None
        assert chat.chat_id == mock_telegram_chat.id
        assert chat.title == mock_telegram_chat.title

    async def test_setup_chat(self, async_db_session, mock_telegram_chat):
        """Test chat setup with default settings."""
        service = ChatService(async_db_session)

        # Create chat first
        await service.get_or_create_chat(mock_telegram_chat)

        # Setup settings
        settings = await service.setup_chat(mock_telegram_chat.id)

        assert settings is not None
        # Assert against the constants rather than literals — this asserted
        # capture_reactions is True while DEFAULT_CAPTURE_REACTIONS has been
        # False (reactions are opt-in), so it tested a default the product
        # does not have. Bound to the constant it cannot drift again.
        assert settings.store_text is DEFAULT_STORE_TEXT
        assert settings.capture_reactions is DEFAULT_CAPTURE_REACTIONS

    async def test_update_settings(self, async_db_session, mock_telegram_chat):
        """Test updating chat settings.

        ChatService exposes update_text_storage / update_reaction_capture;
        there is no generic update_settings, so this called a method that
        never existed.
        """
        service = ChatService(async_db_session)

        await service.get_or_create_chat(mock_telegram_chat)
        await service.setup_chat(mock_telegram_chat.id)

        updated = await service.update_text_storage(mock_telegram_chat.id, store_text=False)
        assert updated.store_text is False

        toggled = await service.update_reaction_capture(
            mock_telegram_chat.id, capture_reactions=True
        )
        assert toggled.capture_reactions is True


@pytest.mark.asyncio
class TestUserService:
    """Test user service functionality."""

    async def test_get_or_create_user(self, async_db_session, mock_telegram_user):
        """Test user creation."""
        service = UserService(async_db_session)

        user = await service.get_or_create_user(mock_telegram_user)

        assert user is not None
        assert user.user_id == mock_telegram_user.id
        assert user.username == mock_telegram_user.username


@pytest.mark.asyncio
class TestMessageService:
    """Test message service functionality."""

    async def test_process_message(self, async_db_session, mock_telegram_chat, mock_telegram_user):
        """Test message processing."""
        chat_service = ChatService(async_db_session)
        user_service = UserService(async_db_session)
        message_service = MessageService(async_db_session)

        # Setup chat and user
        chat = await chat_service.get_or_create_chat(mock_telegram_chat)
        await chat_service.setup_chat(mock_telegram_chat.id)
        user = await user_service.get_or_create_user(mock_telegram_user)

        # Built via the shared helper so every media slot is explicitly empty
        mock_message = make_tg_message(
            chat=mock_telegram_chat,
            from_user=mock_telegram_user,
        )

        # process_message takes only the Telegram message — it resolves the chat
        # and user itself. This passed (message, chat, user) and failed on arity.
        message = await message_service.process_message(mock_message)

        assert message is not None
        # The model column is msg_id; message_id is the Telegram-side name.
        assert message.msg_id == mock_message.message_id
        assert message.chat_id == chat.chat_id
        assert message.user_id == user.user_id


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_rate_limit_not_exceeded(self):
        """Test that user is not rate limited initially."""
        limiter = RateLimiter()

        is_limited, msg = limiter.is_rate_limited(12345)

        assert is_limited is False
        assert msg == ""

    def test_rate_limit_exceeded_per_minute(self):
        """Test rate limit per minute."""
        limiter = RateLimiter()
        user_id = 12345

        # Send 11 requests rapidly (limit is 10/min)
        for _ in range(11):
            is_limited, msg = limiter.is_rate_limited(user_id)

        assert is_limited is True
        assert "minute" in msg.lower()


class TestCacheManager:
    """Test cache functionality."""

    @pytest.mark.asyncio
    async def test_cache_set_get(self):
        """Test setting and getting cached values."""
        cache = CacheManager()

        # Even if Redis is not available, these should not error
        await cache.set("test_key", {"data": "value"})
        result = await cache.get("test_key")

        # If Redis is available, result should match
        # If not, result will be None
        assert result is None or result == {"data": "value"}


class TestSanitizer:
    """Test input sanitization."""

    def test_sanitize_text_basic(self):
        """Test basic text sanitization."""
        text = "<script>alert('xss')</script>Hello"
        result = sanitize_text(text)

        assert "&lt;script&gt;" in result
        assert "<script>" not in result

    def test_sanitize_text_max_length(self):
        """Test text length limiting."""
        long_text = "a" * 5000
        result = sanitize_text(long_text, max_length=100)

        assert len(result) <= 100

    def test_sanitize_command_arg(self):
        """Test command argument sanitization."""
        arg = "test; rm -rf /"
        result = sanitize_command_arg(arg)

        assert ";" not in result
        assert result == "test rm -rf /"

    def test_is_safe_sql_input(self):
        """Test SQL injection detection."""
        safe = "Hello world"
        unsafe = "'; DROP TABLE users; --"

        assert is_safe_sql_input(safe) is True
        assert is_safe_sql_input(unsafe) is False

    def test_sanitize_chat_id(self):
        """Test chat ID sanitization."""
        assert sanitize_chat_id(-1001234567890) == -1001234567890
        assert sanitize_chat_id("-1001234567890") == -1001234567890
        assert sanitize_chat_id("invalid") is None
        assert sanitize_chat_id(10**20) is None  # Too large


@pytest.mark.asyncio
class TestHealthEndpoints:
    """Test health check endpoints."""

    async def test_health_endpoint(self):
        """Test basic health endpoint."""
        from fastapi.testclient import TestClient

        from tgstats.web.app import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    async def test_liveness_probe(self):
        """Test Kubernetes liveness probe."""
        from fastapi.testclient import TestClient

        from tgstats.web.app import app

        client = TestClient(app)
        response = client.get("/health/live")

        assert response.status_code == 200
        assert response.json()["status"] == "alive"


@pytest.mark.asyncio
class TestAuthentication:
    """Test API authentication."""

    async def test_missing_api_token(self):
        """Test API call without token."""
        from fastapi import HTTPException

        from tgstats.web.auth import verify_api_token

        with pytest.raises(HTTPException):
            await verify_api_token(None)

        # This will pass if token is not configured
        # Otherwise should raise 401


class TestMetrics:
    """Test metrics tracking."""

    def test_metrics_increment(self):
        """Test incrementing metrics counters."""
        from tgstats.utils.metrics import metrics

        # These should not error even if Prometheus is not available
        metrics.increment_messages("supergroup", "text")
        metrics.increment_commands("setup", "success")
        metrics.increment_errors("ValueError")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Tests for heatmap repository and service."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from tgstats.db import Base
from tgstats.models import Message, Chat, User
from tgstats.plugins.heatmap.repository import HeatmapRepository
from tgstats.plugins.heatmap.service import HeatmapService


@pytest.fixture
async def session():
    """Create in-memory async session for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
async def sample_chat(session):
    """Create a sample chat."""
    chat = Chat(
        chat_id=123456,
        title="Test Chat",
        type="supergroup"
    )
    session.add(chat)
    await session.commit()
    return chat


@pytest.fixture
async def sample_user(session):
    """Create a sample user."""
    user = User(
        user_id=789012,
        username="testuser",
        first_name="Test"
    )
    session.add(user)
    await session.commit()
    return user


@pytest.fixture
async def sample_messages(session, sample_chat, sample_user):
    """Create sample messages for testing."""
    messages = []
    base_date = datetime.utcnow()
    
    # Create messages across different hours and days
    for day_offset in range(7):
        for hour in range(0, 24, 2):  # Every 2 hours
            # Create messages in chronological order for clarity
            msg_date = base_date - timedelta(days=day_offset, hours=hour)
            message = Message(
                chat_id=sample_chat.chat_id,
                msg_id=len(messages) + 1,
                user_id=sample_user.user_id,
                date=msg_date,
                text_raw="Test message",
                text_len=12,
                media_type="text"
            )
            messages.append(message)
            session.add(message)
    
    await session.commit()
    return messages


class TestHeatmapRepository:
    """Test HeatmapRepository."""
    
    async def test_get_message_count_by_chat(self, session, sample_messages):
        """Test getting message count for a chat."""
        repo = HeatmapRepository(session)
        count = await repo.get_message_count_by_chat(123456, days=7)
        
        assert count > 0
        assert count == len(sample_messages)
    
    async def test_get_message_count_empty_chat(self, session):
        """Test getting message count for empty chat."""
        repo = HeatmapRepository(session)
        count = await repo.get_message_count_by_chat(999999, days=7)
        
        assert count == 0
    
    async def test_get_hourly_activity(self, session, sample_messages):
        """Test getting hourly activity data."""
        repo = HeatmapRepository(session)
        data = await repo.get_hourly_activity(123456, days=7)
        
        assert len(data) > 0
        # Check that we have tuples of (hour, dow, count)
        for hour, dow, count in data:
            assert 0 <= hour < 24
            assert 0 <= dow < 7
            assert count > 0
    
    async def test_get_hourly_activity_with_limit(self, session, sample_messages):
        """Test getting hourly activity with limit."""
        repo = HeatmapRepository(session)
        # Set limit lower than total messages
        data = await repo.get_hourly_activity(123456, days=7, limit=10)
        
        # Should still get aggregated data
        assert len(data) > 0
    
    async def test_get_peak_activity_hour(self, session, sample_messages):
        """Test getting peak activity hour."""
        repo = HeatmapRepository(session)
        peak = await repo.get_peak_activity_hour(123456, days=7)
        
        assert peak is not None
        hour, count = peak
        assert 0 <= hour < 24
        assert count > 0
    
    async def test_get_peak_activity_day(self, session, sample_messages):
        """Test getting peak activity day."""
        repo = HeatmapRepository(session)
        peak = await repo.get_peak_activity_day(123456, days=7)
        
        assert peak is not None
        dow, count = peak
        assert 0 <= dow < 7
        assert count > 0


class TestHeatmapService:
    """Test HeatmapService."""
    
    async def test_is_large_chat(self, session, sample_messages):
        """Test large chat detection."""
        service = HeatmapService(session)
        
        # Our sample has less than threshold
        is_large = await service.is_large_chat(123456, days=7)
        assert not is_large
    
    async def test_get_hourly_activity(self, session, sample_messages):
        """Test getting hourly activity through service."""
        service = HeatmapService(session)
        data = await service.get_hourly_activity(123456, days=7, use_cache=False)
        
        assert len(data) > 0
        # Check serialization worked correctly
        for item in data:
            assert isinstance(item, (list, tuple))
            assert len(item) == 3
    
    async def test_get_activity_summary(self, session, sample_messages):
        """Test getting activity summary."""
        service = HeatmapService(session)
        summary = await service.get_activity_summary(123456, days=7)
        
        assert 'peak_hour' in summary
        assert 'peak_day' in summary
        
        if summary['peak_hour']:
            hour, count = summary['peak_hour']
            assert 0 <= hour < 24
            assert count > 0
        
        if summary['peak_day']:
            dow, count = summary['peak_day']
            assert 0 <= dow < 7
            assert count > 0
    
    async def test_format_heatmap(self, session, sample_messages):
        """Test heatmap formatting."""
        service = HeatmapService(session)
        data = await service.get_hourly_activity(123456, days=7, use_cache=False)
        
        formatted = service.format_heatmap(data)
        
        assert "📊" in formatted
        assert "Activity Heatmap" in formatted
        assert "Legend" in formatted
        # Check for day names
        assert "Mon" in formatted or "Sun" in formatted
    
    async def test_format_heatmap_empty_data(self, session):
        """Test heatmap formatting with empty data."""
        service = HeatmapService(session)
        formatted = service.format_heatmap([])
        
        # Should not crash, just return empty visualization
        assert isinstance(formatted, str)
        assert "Activity Heatmap" in formatted

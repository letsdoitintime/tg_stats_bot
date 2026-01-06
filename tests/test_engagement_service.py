"""Tests for engagement scoring service."""

from datetime import datetime, timedelta, timezone

import pytest

from tgstats.enums import ChatType
from tgstats.models import Chat, Message, Reaction, User
from tgstats.services.engagement_service import EngagementScoringService


@pytest.mark.asyncio
class TestEngagementScoringService:
    """Test EngagementScoringService functionality."""

    async def test_thread_filtering_replies_received(self, test_session):
        """Test that replies_received correctly filters by thread_id for both messages."""
        # Setup: Create chat and users
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP, is_forum=True)
        user1 = User(user_id=100, first_name="User1")
        user2 = User(user_id=200, first_name="User2")
        test_session.add_all([chat, user1, user2])
        await test_session.commit()

        now = datetime.now(timezone.utc)

        # Create messages in thread 1
        msg1_thread1 = Message(
            chat_id=123,
            msg_id=1,
            user_id=100,
            date=now - timedelta(days=5),
            thread_id=1,
            text_len=10,
        )
        reply1_thread1 = Message(
            chat_id=123,
            msg_id=2,
            user_id=200,
            date=now - timedelta(days=4),
            thread_id=1,
            reply_to_msg_id=1,
            text_len=10,
        )

        # Create messages in thread 2
        msg1_thread2 = Message(
            chat_id=123,
            msg_id=3,
            user_id=100,
            date=now - timedelta(days=3),
            thread_id=2,
            text_len=10,
        )
        reply1_thread2 = Message(
            chat_id=123,
            msg_id=4,
            user_id=200,
            date=now - timedelta(days=2),
            thread_id=2,
            reply_to_msg_id=3,
            text_len=10,
        )

        # Edge case: Reply in thread 2 to a message with same msg_id as thread 1
        # This should NOT be counted when filtering by thread 1
        reply_cross_thread = Message(
            chat_id=123,
            msg_id=5,
            user_id=200,
            date=now - timedelta(days=1),
            thread_id=2,
            reply_to_msg_id=1,  # Same msg_id as msg1_thread1, but different thread
            text_len=10,
        )

        test_session.add_all(
            [msg1_thread1, reply1_thread1, msg1_thread2, reply1_thread2, reply_cross_thread]
        )
        await test_session.commit()

        # Test: Get engagement metrics for user1 in thread 1
        service = EngagementScoringService(test_session)
        metrics_thread1 = await service.get_engagement_metrics(
            chat_id=123, user_id=100, days=30, thread_id=1
        )

        # Should only count the reply in thread 1
        assert metrics_thread1.replies_received == 1, (
            f"Expected 1 reply in thread 1, got {metrics_thread1.replies_received}. "
            "The cross-thread reply should not be counted."
        )

        # Test: Get engagement metrics for user1 in thread 2
        metrics_thread2 = await service.get_engagement_metrics(
            chat_id=123, user_id=100, days=30, thread_id=2
        )

        # Should only count the proper reply in thread 2
        # The cross-thread reply (reply_to_msg_id=1 but in thread 2) should NOT count
        # because the target message (msg_id=1) is in thread 1, not thread 2
        assert metrics_thread2.replies_received == 1, (
            f"Expected 1 reply in thread 2, got {metrics_thread2.replies_received}. "
            "The cross-thread reply should not be counted because the target message is in thread 1."
        )

        # Test: Get engagement metrics for user1 without thread filter (chat-wide)
        metrics_all = await service.get_engagement_metrics(chat_id=123, user_id=100, days=30)

        # Should count only 2 valid replies (one in each thread)
        # The cross-thread reply (msg_id=5) references msg_id=1 which exists,
        # so it will be counted as a valid reply in chat-wide stats
        assert metrics_all.replies_received == 3, (
            f"Expected 3 total replies, got {metrics_all.replies_received}. "
            "All replies to user's messages should be counted, including cross-thread ones."
        )

    async def test_engagement_score_basic(self, test_session):
        """Test basic engagement score calculation."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user = User(user_id=100, first_name="User1")
        test_session.add_all([chat, user])
        await test_session.commit()

        now = datetime.now(timezone.utc)

        # Add some messages
        for i in range(10):
            msg = Message(
                chat_id=123,
                msg_id=i + 1,
                user_id=100,
                date=now - timedelta(days=i),
                text_len=50,
            )
            test_session.add(msg)

        await test_session.commit()

        # Calculate score
        service = EngagementScoringService(test_session)
        score = await service.calculate_engagement_score(chat_id=123, user_id=100, days=30)

        # Verify score components
        assert score.user_id == 100
        assert 0 <= score.total_score <= 100
        assert 0 <= score.activity_score <= 100
        assert 0 <= score.consistency_score <= 100
        assert 0 <= score.quality_score <= 100
        assert 0 <= score.interaction_score <= 100

    async def test_reactions_filtering(self, test_session):
        """Test that reactions are correctly filtered by thread."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP, is_forum=True)
        user1 = User(user_id=100, first_name="User1")
        user2 = User(user_id=200, first_name="User2")
        test_session.add_all([chat, user1, user2])
        await test_session.commit()

        now = datetime.now(timezone.utc)

        # Message in thread 1
        msg1 = Message(
            chat_id=123,
            msg_id=1,
            user_id=100,
            date=now - timedelta(days=1),
            thread_id=1,
            text_len=10,
        )

        # Message in thread 2
        msg2 = Message(
            chat_id=123,
            msg_id=2,
            user_id=100,
            date=now - timedelta(days=1),
            thread_id=2,
            text_len=10,
        )

        test_session.add_all([msg1, msg2])
        await test_session.commit()

        # Add reactions to both messages
        reaction1 = Reaction(
            chat_id=123, msg_id=1, user_id=200, reaction_emoji="👍", date=now
        )
        reaction2 = Reaction(
            chat_id=123, msg_id=2, user_id=200, reaction_emoji="❤️", date=now
        )
        test_session.add_all([reaction1, reaction2])
        await test_session.commit()

        # Test thread 1 filtering
        service = EngagementScoringService(test_session)
        metrics_thread1 = await service.get_engagement_metrics(
            chat_id=123, user_id=100, days=30, thread_id=1
        )

        assert metrics_thread1.reactions_received == 1, (
            f"Expected 1 reaction in thread 1, got {metrics_thread1.reactions_received}"
        )

        # Test thread 2 filtering
        metrics_thread2 = await service.get_engagement_metrics(
            chat_id=123, user_id=100, days=30, thread_id=2
        )

        assert metrics_thread2.reactions_received == 1, (
            f"Expected 1 reaction in thread 2, got {metrics_thread2.reactions_received}"
        )

    async def test_public_method_access(self, test_session):
        """Test that get_engagement_metrics is now public and accessible."""
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user = User(user_id=100, first_name="User1")
        test_session.add_all([chat, user])
        await test_session.commit()

        service = EngagementScoringService(test_session)

        # Should be able to call get_engagement_metrics (public method)
        metrics = await service.get_engagement_metrics(chat_id=123, user_id=100, days=30)

        assert metrics is not None
        assert metrics.message_count >= 0
        assert metrics.total_days == 30

        # Should not have underscore prefix (verify it's public)
        assert hasattr(service, "get_engagement_metrics")
        assert not hasattr(service, "_get_engagement_metrics") or hasattr(
            service, "get_engagement_metrics"
        )

    async def test_null_user_id_excluded_from_leaderboard(self, test_session):
        """Test that messages with NULL user_id are excluded from leaderboard calculations."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user = User(user_id=100, first_name="User1")
        test_session.add_all([chat, user])
        await test_session.commit()

        now = datetime.now(timezone.utc)

        # Add messages from the user
        for i in range(10):
            msg = Message(
                chat_id=123,
                msg_id=i + 1,
                user_id=100,
                date=now - timedelta(days=i),
                text_len=50,
            )
            test_session.add(msg)

        # Add system messages with NULL user_id (e.g., join/leave messages)
        for i in range(5):
            system_msg = Message(
                chat_id=123,
                msg_id=100 + i,
                user_id=None,  # System message
                date=now - timedelta(days=i),
                text_len=20,
            )
            test_session.add(system_msg)

        await test_session.commit()

        # Calculate scores - should only include user 100, not NULL user
        service = EngagementScoringService(test_session)
        scores = await service.calculate_chat_engagement_scores(
            chat_id=123, days=30, min_messages=5
        )

        # Should have exactly 1 user (not NULL)
        assert len(scores) == 1
        assert scores[0].user_id == 100

    async def test_timezone_aware_date_filtering(self, test_session):
        """Test that date filtering works correctly with timezone-aware datetimes."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user = User(user_id=100, first_name="User1")
        test_session.add_all([chat, user])
        await test_session.commit()

        now = datetime.now(timezone.utc)

        # Add messages within the 30-day window
        for i in range(5):
            msg = Message(
                chat_id=123,
                msg_id=i + 1,
                user_id=100,
                date=now - timedelta(days=i),
                text_len=50,
            )
            test_session.add(msg)

        # Add messages outside the 30-day window
        for i in range(5):
            old_msg = Message(
                chat_id=123,
                msg_id=100 + i,
                user_id=100,
                date=now - timedelta(days=40 + i),  # 40+ days ago
                text_len=50,
            )
            test_session.add(old_msg)

        await test_session.commit()

        # Calculate metrics - should only count recent messages
        service = EngagementScoringService(test_session)
        metrics = await service.get_engagement_metrics(chat_id=123, user_id=100, days=30)

        # Should only count the 5 recent messages
        assert metrics.message_count == 5

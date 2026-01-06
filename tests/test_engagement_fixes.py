"""Tests for engagement service SQL query fixes.

These tests verify the following fixes:
1. Reactions received counts only active reactions (not removed)
2. Reactions given counts only active reactions (not removed)
3. Reactions received excludes self-reactions
4. Replies received excludes self-replies
5. Date extraction uses cast(Message.date, Date) for portability
"""

from datetime import datetime, timedelta, timezone

import pytest

from tgstats.enums import ChatType
from tgstats.models import Chat, Message, Reaction, User
from tgstats.services.engagement_service import EngagementScoringService


@pytest.mark.asyncio
class TestEngagementServiceFixes:
    """Test fixes for engagement scoring service SQL queries."""

    async def test_reactions_received_excludes_removed(self, test_session):
        """Test that reactions_received only counts active reactions (removed_at IS NULL)."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user1 = User(user_id=100, first_name="User1")
        user2 = User(user_id=200, first_name="User2")
        test_session.add_all([chat, user1, user2])
        await test_session.commit()

        now = datetime.now(timezone.utc)

        # Create a message from user1
        msg = Message(
            chat_id=123,
            msg_id=1,
            user_id=100,
            date=now - timedelta(days=1),
            text_len=10,
        )
        test_session.add(msg)
        await test_session.commit()

        # Add 2 active reactions and 1 removed reaction
        reaction1 = Reaction(
            chat_id=123,
            msg_id=1,
            user_id=200,
            reaction_emoji="👍",
            date=now,
            removed_at=None,  # Active
        )
        reaction2 = Reaction(
            chat_id=123,
            msg_id=1,
            user_id=201,
            reaction_emoji="❤️",
            date=now,
            removed_at=None,  # Active
        )
        reaction3 = Reaction(
            chat_id=123,
            msg_id=1,
            user_id=202,
            reaction_emoji="🔥",
            date=now,
            removed_at=now - timedelta(hours=1),  # Removed
        )
        test_session.add_all([reaction1, reaction2, reaction3])
        await test_session.commit()

        # Test: Get engagement metrics
        service = EngagementScoringService(test_session)
        metrics = await service.get_engagement_metrics(chat_id=123, user_id=100, days=30)

        # Should only count 2 active reactions, not the removed one
        assert metrics.reactions_received == 2, (
            f"Expected 2 active reactions, got {metrics.reactions_received}. "
            "Removed reactions should not be counted."
        )

    async def test_reactions_given_excludes_removed(self, test_session):
        """Test that reactions_given only counts active reactions (removed_at IS NULL)."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user1 = User(user_id=100, first_name="User1")
        user2 = User(user_id=200, first_name="User2")
        test_session.add_all([chat, user1, user2])
        await test_session.commit()

        now = datetime.now(timezone.utc)

        # Create messages from user2
        for i in range(3):
            msg = Message(
                chat_id=123,
                msg_id=i + 1,
                user_id=200,
                date=now - timedelta(days=1),
                text_len=10,
            )
            test_session.add(msg)
        await test_session.commit()

        # User1 gives 2 active reactions and 1 removed reaction
        reaction1 = Reaction(
            chat_id=123,
            msg_id=1,
            user_id=100,
            reaction_emoji="👍",
            date=now,
            removed_at=None,  # Active
        )
        reaction2 = Reaction(
            chat_id=123,
            msg_id=2,
            user_id=100,
            reaction_emoji="❤️",
            date=now,
            removed_at=None,  # Active
        )
        reaction3 = Reaction(
            chat_id=123,
            msg_id=3,
            user_id=100,
            reaction_emoji="🔥",
            date=now,
            removed_at=now - timedelta(hours=1),  # Removed
        )
        test_session.add_all([reaction1, reaction2, reaction3])
        await test_session.commit()

        # Test: Get engagement metrics for user1
        service = EngagementScoringService(test_session)
        metrics = await service.get_engagement_metrics(chat_id=123, user_id=100, days=30)

        # Should only count 2 active reactions given
        assert metrics.reactions_given == 2, (
            f"Expected 2 active reactions given, got {metrics.reactions_given}. "
            "Removed reactions should not be counted."
        )

    async def test_reactions_received_excludes_self_reactions(self, test_session):
        """Test that reactions_received excludes self-reactions."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user1 = User(user_id=100, first_name="User1")
        user2 = User(user_id=200, first_name="User2")
        test_session.add_all([chat, user1, user2])
        await test_session.commit()

        now = datetime.now(timezone.utc)

        # Create a message from user1
        msg = Message(
            chat_id=123,
            msg_id=1,
            user_id=100,
            date=now - timedelta(days=1),
            text_len=10,
        )
        test_session.add(msg)
        await test_session.commit()

        # Add 1 reaction from another user and 1 self-reaction
        reaction_from_other = Reaction(
            chat_id=123,
            msg_id=1,
            user_id=200,
            reaction_emoji="👍",
            date=now,
        )
        self_reaction = Reaction(
            chat_id=123,
            msg_id=1,
            user_id=100,  # Same as message author
            reaction_emoji="❤️",
            date=now,
        )
        test_session.add_all([reaction_from_other, self_reaction])
        await test_session.commit()

        # Test: Get engagement metrics for user1
        service = EngagementScoringService(test_session)
        metrics = await service.get_engagement_metrics(chat_id=123, user_id=100, days=30)

        # Should only count 1 reaction (from other user), not self-reaction
        assert metrics.reactions_received == 1, (
            f"Expected 1 reaction from others, got {metrics.reactions_received}. "
            "Self-reactions should not be counted."
        )

    async def test_replies_received_excludes_self_replies(self, test_session):
        """Test that replies_received excludes self-replies."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user1 = User(user_id=100, first_name="User1")
        user2 = User(user_id=200, first_name="User2")
        test_session.add_all([chat, user1, user2])
        await test_session.commit()

        now = datetime.now(timezone.utc)

        # Create original message from user1
        original_msg = Message(
            chat_id=123,
            msg_id=1,
            user_id=100,
            date=now - timedelta(days=2),
            text_len=10,
        )
        test_session.add(original_msg)
        await test_session.commit()

        # Add 1 reply from another user and 1 self-reply
        reply_from_other = Message(
            chat_id=123,
            msg_id=2,
            user_id=200,
            date=now - timedelta(days=1),
            reply_to_msg_id=1,
            text_len=10,
        )
        self_reply = Message(
            chat_id=123,
            msg_id=3,
            user_id=100,  # Same as original message author
            date=now - timedelta(hours=12),
            reply_to_msg_id=1,
            text_len=10,
        )
        test_session.add_all([reply_from_other, self_reply])
        await test_session.commit()

        # Test: Get engagement metrics for user1
        service = EngagementScoringService(test_session)
        metrics = await service.get_engagement_metrics(chat_id=123, user_id=100, days=30)

        # Should only count 1 reply (from other user), not self-reply
        assert metrics.replies_received == 1, (
            f"Expected 1 reply from others, got {metrics.replies_received}. "
            "Self-replies should not be counted."
        )

    async def test_combined_fixes(self, test_session):
        """Test all fixes together in a realistic scenario."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user1 = User(user_id=100, first_name="User1")
        user2 = User(user_id=200, first_name="User2")
        user3 = User(user_id=300, first_name="User3")
        test_session.add_all([chat, user1, user2, user3])
        await test_session.commit()

        now = datetime.now(timezone.utc)

        # User1 sends 2 messages
        msg1 = Message(
            chat_id=123,
            msg_id=1,
            user_id=100,
            date=now - timedelta(days=2),
            text_len=50,
        )
        msg2 = Message(
            chat_id=123,
            msg_id=2,
            user_id=100,
            date=now - timedelta(days=1),
            text_len=30,
        )
        test_session.add_all([msg1, msg2])
        await test_session.commit()

        # Reactions on msg1:
        # - 1 active from user2 (should count)
        # - 1 removed from user3 (should NOT count)
        # - 1 self-reaction (should NOT count)
        reaction1 = Reaction(
            chat_id=123, msg_id=1, user_id=200, reaction_emoji="👍", date=now
        )
        reaction2 = Reaction(
            chat_id=123,
            msg_id=1,
            user_id=300,
            reaction_emoji="❤️",
            date=now,
            removed_at=now - timedelta(hours=1),
        )
        reaction3 = Reaction(
            chat_id=123, msg_id=1, user_id=100, reaction_emoji="🔥", date=now
        )

        # Reactions on msg2:
        # - 1 active from user3 (should count)
        reaction4 = Reaction(
            chat_id=123, msg_id=2, user_id=300, reaction_emoji="👏", date=now
        )

        test_session.add_all([reaction1, reaction2, reaction3, reaction4])
        await test_session.commit()

        # Replies to msg1:
        # - 1 from user2 (should count)
        # - 1 self-reply from user1 (should NOT count)
        reply1 = Message(
            chat_id=123,
            msg_id=10,
            user_id=200,
            date=now - timedelta(hours=12),
            reply_to_msg_id=1,
            text_len=20,
        )
        self_reply = Message(
            chat_id=123,
            msg_id=11,
            user_id=100,
            date=now - timedelta(hours=6),
            reply_to_msg_id=1,
            text_len=15,
        )
        test_session.add_all([reply1, self_reply])

        # User1 gives reactions (to test reactions_given):
        # - 2 active reactions (should count)
        # - 1 removed reaction (should NOT count)
        msg_from_user2 = Message(
            chat_id=123, msg_id=20, user_id=200, date=now - timedelta(days=1), text_len=40
        )
        msg_from_user3 = Message(
            chat_id=123, msg_id=21, user_id=300, date=now - timedelta(days=1), text_len=40
        )
        test_session.add_all([msg_from_user2, msg_from_user3])
        await test_session.commit()

        reaction_given1 = Reaction(
            chat_id=123, msg_id=20, user_id=100, reaction_emoji="👍", date=now
        )
        reaction_given2 = Reaction(
            chat_id=123, msg_id=21, user_id=100, reaction_emoji="❤️", date=now
        )
        reaction_given3 = Reaction(
            chat_id=123,
            msg_id=20,
            user_id=100,
            reaction_emoji="🔥",
            date=now,
            removed_at=now - timedelta(hours=1),
        )
        test_session.add_all([reaction_given1, reaction_given2, reaction_given3])
        await test_session.commit()

        # Test: Get engagement metrics for user1
        service = EngagementScoringService(test_session)
        metrics = await service.get_engagement_metrics(chat_id=123, user_id=100, days=30)

        # Verify all fixes
        assert metrics.reactions_received == 2, (
            f"Expected 2 reactions received (excluding removed and self), "
            f"got {metrics.reactions_received}"
        )
        assert metrics.reactions_given == 3, (
            f"Expected 3 reactions given (including self-reaction on own message, "
            f"excluding removed), got {metrics.reactions_given}"
        )
        assert metrics.replies_received == 1, (
            f"Expected 1 reply received (excluding self-reply), got {metrics.replies_received}"
        )
        assert metrics.message_count == 3, (  # 2 original + 1 self-reply
            f"Expected 3 messages from user1, got {metrics.message_count}"
        )

    async def test_scoring_methods_are_sync(self, test_session):
        """Test that internal scoring methods are synchronous (not async)."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        user = User(user_id=100, first_name="User1")
        test_session.add_all([chat, user])
        await test_session.commit()

        now = datetime.now(timezone.utc)

        # Add a few messages
        for i in range(5):
            msg = Message(
                chat_id=123,
                msg_id=i + 1,
                user_id=100,
                date=now - timedelta(days=i),
                text_len=50,
            )
            test_session.add(msg)
        await test_session.commit()

        # Calculate score (this should work without await on internal methods)
        service = EngagementScoringService(test_session)
        score = await service.calculate_engagement_score(chat_id=123, user_id=100, days=30)

        # Verify score is calculated correctly
        assert score.user_id == 100
        assert 0 <= score.total_score <= 100
        assert 0 <= score.activity_score <= 100
        assert 0 <= score.consistency_score <= 100
        assert 0 <= score.quality_score <= 100
        assert 0 <= score.interaction_score <= 100

    async def test_leaderboard_with_details_optimization(self, test_session):
        """Test the new get_leaderboard_with_details method for performance optimization."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        users = [User(user_id=100 + i, first_name=f"User{i}") for i in range(15)]
        test_session.add(chat)
        test_session.add_all(users)
        await test_session.commit()

        now = datetime.now(timezone.utc)

        # Add messages for each user (different amounts to create ranking)
        for i, user in enumerate(users):
            for j in range(10 - (i % 10)):  # Varying message counts
                msg = Message(
                    chat_id=123,
                    msg_id=i * 100 + j,
                    user_id=user.user_id,
                    date=now - timedelta(days=j),
                    text_len=50,
                )
                test_session.add(msg)
        await test_session.commit()

        # Test: Get leaderboard with details
        service = EngagementScoringService(test_session)
        leaderboard = await service.get_leaderboard_with_details(
            chat_id=123,
            days=30,
            min_messages=5,
            limit=10,
            include_metrics=True,
        )

        # Verify results
        assert len(leaderboard) <= 10, "Should return at most 10 users"
        assert all(len(item) == 3 for item in leaderboard), "Each item should be a 3-tuple"

        for score, user, metrics in leaderboard:
            assert score is not None, "Score should not be None"
            assert user is not None, "User should be fetched"
            assert metrics is not None, "Metrics should be included when requested"
            assert score.user_id == user.user_id, "Score and user should match"

    async def test_leaderboard_without_metrics(self, test_session):
        """Test get_leaderboard_with_details without metrics for performance."""
        # Setup
        chat = Chat(chat_id=123, title="Test", type=ChatType.GROUP)
        users = [User(user_id=100 + i, first_name=f"User{i}") for i in range(5)]
        test_session.add(chat)
        test_session.add_all(users)
        await test_session.commit()

        now = datetime.now(timezone.utc)

        # Add messages for each user
        for i, user in enumerate(users):
            for j in range(10):
                msg = Message(
                    chat_id=123,
                    msg_id=i * 100 + j,
                    user_id=user.user_id,
                    date=now - timedelta(days=j),
                    text_len=50,
                )
                test_session.add(msg)
        await test_session.commit()

        # Test: Get leaderboard without metrics
        service = EngagementScoringService(test_session)
        leaderboard = await service.get_leaderboard_with_details(
            chat_id=123,
            days=30,
            min_messages=5,
            limit=10,
            include_metrics=False,
        )

        # Verify results
        assert len(leaderboard) == 5, "Should return all 5 users"

        for score, user, metrics in leaderboard:
            assert score is not None, "Score should not be None"
            assert user is not None, "User should be fetched"
            assert metrics is None, "Metrics should be None when not requested"

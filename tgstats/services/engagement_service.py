"""User engagement scoring service.

Calculates engagement scores for users based on their activity patterns,
message content, and interaction with the community.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass

import structlog
from sqlalchemy import select, func
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Message, User, Chat, Reaction
from ..repositories.message_repository import MessageRepository
from ..repositories.user_repository import UserRepository

logger = structlog.get_logger(__name__)


@dataclass
class EngagementScore:
    """User engagement score breakdown."""

    user_id: int
    total_score: float
    activity_score: float
    consistency_score: float
    quality_score: float
    interaction_score: float
    percentile: Optional[float] = None


@dataclass
class EngagementMetrics:
    """Detailed engagement metrics for a user."""

    message_count: int
    avg_message_length: float
    days_active: int
    total_days: int
    url_count: int
    media_count: int
    reactions_given: int
    reactions_received: int
    replies_received: int
    reply_count: int


class EngagementScoringService:
    """Service for calculating user engagement scores."""

    # Scoring weights
    ACTIVITY_WEIGHT = 0.30  # 30% - Message volume
    CONSISTENCY_WEIGHT = 0.25  # 25% - Regular participation
    QUALITY_WEIGHT = 0.25  # 25% - Message quality
    INTERACTION_WEIGHT = 0.20  # 20% - Community interaction

    def __init__(self, session: AsyncSession):
        self.session = session
        self.message_repo = MessageRepository(session)
        self.user_repo = UserRepository(session)

    async def calculate_engagement_score(
        self,
        chat_id: int,
        user_id: int,
        days: int = 30,
        thread_id: Optional[int] = None,
    ) -> EngagementScore:
        """
        Calculate comprehensive engagement score for a user.

        Args:
            chat_id: Chat ID to analyze
            user_id: User ID to score
            days: Number of days to analyze (default: 30)

        Returns:
            EngagementScore with breakdown of scores
        """
        # Get engagement metrics
        metrics = await self._get_engagement_metrics(chat_id, user_id, days, thread_id)

        # Calculate individual scores
        activity_score = await self._calculate_activity_score(metrics, days)
        consistency_score = await self._calculate_consistency_score(metrics)
        quality_score = await self._calculate_quality_score(metrics)
        interaction_score = await self._calculate_interaction_score(metrics)

        # Calculate weighted total
        total_score = (
            activity_score * self.ACTIVITY_WEIGHT
            + consistency_score * self.CONSISTENCY_WEIGHT
            + quality_score * self.QUALITY_WEIGHT
            + interaction_score * self.INTERACTION_WEIGHT
        )

        logger.info(
            "Calculated engagement score",
            chat_id=chat_id,
            user_id=user_id,
            total_score=total_score,
            days=days,
        )

        return EngagementScore(
            user_id=user_id,
            total_score=round(total_score, 2),
            activity_score=round(activity_score, 2),
            consistency_score=round(consistency_score, 2),
            quality_score=round(quality_score, 2),
            interaction_score=round(interaction_score, 2),
        )

    async def calculate_chat_engagement_scores(
        self,
        chat_id: int,
        days: int = 30,
        min_messages: int = 5,
        thread_id: Optional[int] = None,
    ) -> List[EngagementScore]:
        """
        Calculate engagement scores for all active users in a chat.

        Args:
            chat_id: Chat ID to analyze
            days: Number of days to analyze
            min_messages: Minimum message count to include user

        Returns:
            List of EngagementScore objects sorted by total score
        """
        # Get active users
        since = datetime.now() - timedelta(days=days)

        query = (
            select(Message.user_id, func.count(Message.msg_id).label("count"))
            .where(Message.chat_id == chat_id)
            .where(Message.date >= since)
        )

        if thread_id is not None:
            query = query.where(Message.thread_id == thread_id)

        query = query.group_by(Message.user_id).having(func.count(Message.msg_id) >= min_messages)

        result = await self.session.execute(query)
        active_users = result.all()

        # Calculate scores for each user
        scores = []
        for user_id, _ in active_users:
            score = await self.calculate_engagement_score(chat_id, user_id, days, thread_id)
            scores.append(score)

        # Calculate percentiles
        scores.sort(key=lambda x: x.total_score, reverse=True)
        total_users = len(scores)

        for idx, score in enumerate(scores):
            score.percentile = round((total_users - idx) / total_users * 100, 1)

        logger.info(
            "Calculated engagement scores for chat",
            chat_id=chat_id,
            user_count=total_users,
            days=days,
        )

        return scores

    async def _get_engagement_metrics(
        self,
        chat_id: int,
        user_id: int,
        days: int,
        thread_id: Optional[int] = None,
    ) -> EngagementMetrics:
        """Get detailed engagement metrics for a user."""
        since = datetime.now() - timedelta(days=days)

        # Message statistics
        msg_query = select(
            func.count(Message.msg_id).label("message_count"),
            func.avg(Message.text_len).label("avg_length"),
            func.count(func.distinct(func.date_trunc("day", Message.date))).label("days_active"),
            func.sum(Message.urls_cnt).label("url_count"),
            func.count().filter(Message.media_type.isnot(None)).label("media_count"),
        ).where(Message.chat_id == chat_id, Message.user_id == user_id, Message.date >= since)

        if thread_id is not None:
            msg_query = msg_query.where(Message.thread_id == thread_id)

        msg_result = await self.session.execute(msg_query)
        msg_stats = msg_result.one()

        # Reaction statistics (reactions given)
        # Reactions given (limit to thread if thread_id provided)
        reactions_given_query = (
            select(func.count(Reaction.reaction_id))
            .join(
                Message, (Message.chat_id == Reaction.chat_id) & (Message.msg_id == Reaction.msg_id)
            )
            .where(Reaction.chat_id == chat_id, Reaction.user_id == user_id, Reaction.date >= since)
        )

        if thread_id is not None:
            reactions_given_query = reactions_given_query.where(Message.thread_id == thread_id)

        reactions_given = await self.session.scalar(reactions_given_query) or 0

        # Reactions received
        reactions_received_query = (
            select(func.count(Reaction.reaction_id))
            .join(
                Message, (Message.chat_id == Reaction.chat_id) & (Message.msg_id == Reaction.msg_id)
            )
            .where(Message.chat_id == chat_id, Message.user_id == user_id, Reaction.date >= since)
        )

        if thread_id is not None:
            reactions_received_query = reactions_received_query.where(
                Message.thread_id == thread_id
            )

        reactions_received = await self.session.scalar(reactions_received_query) or 0

        # Reply count (messages with reply_to_msg_id) -- replies sent by the user
        reply_query = select(func.count(Message.msg_id)).where(
            Message.chat_id == chat_id,
            Message.user_id == user_id,
            Message.reply_to_msg_id.isnot(None),
            Message.date >= since,
        )

        if thread_id is not None:
            reply_query = reply_query.where(Message.thread_id == thread_id)

        reply_count = await self.session.scalar(reply_query) or 0

        # Replies received: count messages that reply to messages authored by the user
        target = aliased(Message, name="target")
        replies_received_query = (
            select(func.count(Message.msg_id))
            .join(
                target,
                (Message.reply_to_msg_id == target.msg_id) & (Message.chat_id == target.chat_id),
            )
            .where(target.user_id == user_id, Message.chat_id == chat_id, Message.date >= since)
        )

        if thread_id is not None:
            replies_received_query = replies_received_query.where(Message.thread_id == thread_id)

        replies_received = await self.session.scalar(replies_received_query) or 0

        return EngagementMetrics(
            message_count=msg_stats.message_count or 0,
            avg_message_length=float(msg_stats.avg_length or 0),
            days_active=msg_stats.days_active or 0,
            total_days=days,
            url_count=msg_stats.url_count or 0,
            media_count=msg_stats.media_count or 0,
            reactions_given=reactions_given,
            reactions_received=reactions_received,
            replies_received=replies_received,
            reply_count=reply_count,
        )

    async def _calculate_activity_score(self, metrics: EngagementMetrics, days: int) -> float:
        """
        Calculate activity score based on message volume.

        Score components:
        - Messages per day (normalized)
        - Bonus for high activity (> 5 messages/day)
        """
        if days == 0:
            return 0.0

        messages_per_day = metrics.message_count / days

        # Base score: normalize to 0-80 range (reasonable max: 10 msg/day)
        base_score = min(messages_per_day / 10 * 80, 80)

        # Bonus for high activity
        if messages_per_day > 5:
            bonus = min((messages_per_day - 5) / 5 * 20, 20)
        else:
            bonus = 0

        return min(base_score + bonus, 100)

    async def _calculate_consistency_score(self, metrics: EngagementMetrics) -> float:
        """
        Calculate consistency score based on regular participation.

        Score components:
        - Days active ratio (% of days with activity)
        - Bonus for streaks (implied by high ratio)
        """
        if metrics.total_days == 0:
            return 0.0

        # Days active ratio
        days_ratio = metrics.days_active / metrics.total_days

        # Base score: 0-100 based on participation ratio
        base_score = days_ratio * 100

        return min(base_score, 100)

    async def _calculate_quality_score(self, metrics: EngagementMetrics) -> float:
        """
        Calculate quality score based on message content.

        Score components:
        - Average message length (longer = more thoughtful)
        - URL sharing (useful resources)
        - Media sharing (visual content)
        - Reactions received (message value)
        """
        score = 0.0

        # Message length score (25 points max)
        # Optimal range: 50-200 characters
        if metrics.avg_message_length > 0:
            if metrics.avg_message_length < 50:
                length_score = metrics.avg_message_length / 50 * 15
            elif metrics.avg_message_length <= 200:
                length_score = 15 + (metrics.avg_message_length - 50) / 150 * 10
            else:
                length_score = 25
            score += length_score

        # URL sharing score (25 points max)
        if metrics.message_count > 0:
            url_ratio = min(metrics.url_count / metrics.message_count, 0.3)
            score += url_ratio / 0.3 * 25

        # Media sharing score (25 points max)
        if metrics.message_count > 0:
            media_ratio = min(metrics.media_count / metrics.message_count, 0.4)
            score += media_ratio / 0.4 * 25

        # Reactions received score (25 points max)
        if metrics.message_count > 0:
            reactions_per_message = metrics.reactions_received / metrics.message_count
            score += min(reactions_per_message / 2 * 25, 25)

        return min(score, 100)

    async def _calculate_interaction_score(self, metrics: EngagementMetrics) -> float:
        """
        Calculate interaction score based on community engagement.

        Score components:
        - Reply count (active conversations)
        - Reactions given (engaging with others)
        """
        score = 0.0

        # Reply score (50 points max) - consider both replies sent and replies received
        if metrics.message_count > 0:
            reply_ratio = min(
                (metrics.reply_count + metrics.replies_received) / metrics.message_count, 0.5
            )
            score += reply_ratio / 0.5 * 50

        # Reactions given score (50 points max)
        # Compare reactions given to messages sent
        if metrics.message_count > 0:
            reactions_ratio = min(metrics.reactions_given / metrics.message_count, 1.0)
            score += reactions_ratio * 50

        return min(score, 100)

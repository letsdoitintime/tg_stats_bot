"""
Word Cloud Statistics Plugin.

Generates word frequency statistics from messages.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.ext import Application

from ..models import Message
from .base import PluginMetadata, StatisticsPlugin


class WordCloudPlugin(StatisticsPlugin):
    """Generate word frequency statistics for word clouds."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="word_cloud",
            version="1.0.0",
            description="Generates word frequency statistics for creating word clouds",
            author="TgStats Team",
            dependencies=[],
        )

    async def initialize(self, app: Application) -> None:
        """Initialize the plugin."""
        self._logger.info("word_cloud_plugin_initialized")
        # Could load stopwords, configure languages, etc.
        self.stopwords = set(
            [
                "the",
                "a",
                "an",
                "and",
                "or",
                "but",
                "is",
                "are",
                "was",
                "were",
                "in",
                "on",
                "at",
                "to",
                "for",
                "of",
                "with",
                "by",
                "from",
                "as",
                "this",
                "that",
                "these",
                "those",
                "it",
                "its",
                "i",
                "you",
                "he",
                "she",
                "we",
                "they",
                "my",
                "your",
                "his",
                "her",
                "our",
                "their",
            ]
        )

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        self._logger.info("word_cloud_plugin_shutdown")

    def get_stat_name(self) -> str:
        return "word_cloud"

    def get_stat_description(self) -> str:
        return "Word frequency analysis for word cloud generation"

    async def calculate_stats(
        self,
        session: AsyncSession,
        chat_id: int,
        days: int = 30,
        top_n: int = 100,
        min_word_length: int = 3,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Calculate word frequencies for a chat.

        Args:
            session: Database session
            chat_id: Chat ID to analyze
            days: Number of days to look back (default: 30)
            top_n: Return top N words (default: 100)
            min_word_length: Minimum word length (default: 3)

        Returns:
            Dictionary with word frequencies and metadata
        """
        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        # Query messages with text
        query = select(Message.text_raw).where(
            and_(
                Message.chat_id == chat_id,
                Message.text_raw.isnot(None),
                Message.text_raw != "",
                Message.date >= start_date,
                Message.date <= end_date,
            )
        )

        result = await session.execute(query)
        messages = result.scalars().all()

        # Count words
        word_counts = Counter()
        total_messages = 0

        for text in messages:
            if not text:
                continue

            total_messages += 1
            words = text.lower().split()

            for word in words:
                # Clean word (remove punctuation)
                clean_word = "".join(c for c in word if c.isalnum())

                # Filter by length and stopwords
                if len(clean_word) >= min_word_length and clean_word not in self.stopwords:
                    word_counts[clean_word] += 1

        # Get top N words
        top_words = dict(word_counts.most_common(top_n))

        return {
            "word_frequencies": top_words,
            "total_messages_analyzed": total_messages,
            "total_unique_words": len(word_counts),
            "top_n": top_n,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days,
            },
            "filters": {"min_word_length": min_word_length, "stopwords_count": len(self.stopwords)},
        }

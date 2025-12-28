"""Seed script to generate sample data for testing."""

import logging
import random
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from tgstats.db import get_sync_session
from tgstats.enums import ChatType, MediaType, MembershipStatus
from tgstats.models import Chat, GroupSettings, Membership, Message, Reaction, User

logger = logging.getLogger(__name__)


def create_sample_chats() -> List[Chat]:
    """Create sample chat data."""
    chats = [
        Chat(
            chat_id=-1001234567890,
            title="Tech Discussion Group",
            username="techdiscussion",
            type=ChatType.SUPERGROUP,
            is_forum=False,
        ),
        Chat(
            chat_id=-1001234567891,
            title="Random Chat Room",
            username="randomchat",
            type=ChatType.SUPERGROUP,
            is_forum=False,
        ),
    ]
    return chats


def create_sample_users() -> List[User]:
    """Create sample user data."""
    users = []

    # Create 50 users with varying activity patterns
    for i in range(1, 51):
        user = User(
            user_id=i,
            username=f"user{i}",
            first_name=f"User{i}",
            last_name=f"Lastname{i}",
            is_bot=False,
            language_code="en",
        )
        users.append(user)

    # Add a few bots
    for i in range(100, 103):
        bot = User(user_id=i, username=f"bot{i}", first_name=f"Bot{i}", is_bot=True)
        users.append(bot)

    return users


def create_sample_settings(chats: List[Chat]) -> List[GroupSettings]:
    """Create sample group settings."""
    settings = []

    for chat in chats:
        setting = GroupSettings(
            chat_id=chat.chat_id,
            store_text=True,
            text_retention_days=90,
            metadata_retention_days=365,
            timezone="Europe/Sofia" if chat.chat_id == -1001234567890 else "UTC",
            locale="en",
            capture_reactions=True,
        )
        settings.append(setting)

    return settings


def create_sample_memberships(chats: List[Chat], users: List[User]) -> List[Membership]:
    """Create sample membership data."""
    memberships = []
    base_date = datetime.utcnow() - timedelta(days=60)

    for chat in chats:
        # Most users join the first chat
        user_count = 40 if chat.chat_id == -1001234567890 else 25

        for i, user in enumerate(users[:user_count]):
            # Stagger join dates
            joined_at = base_date + timedelta(days=random.randint(0, 45))

            # Some users leave
            left_at = None
            if random.random() < 0.1:  # 10% leave
                left_at = joined_at + timedelta(days=random.randint(7, 30))

            membership = Membership(
                chat_id=chat.chat_id,
                user_id=user.user_id,
                joined_at=joined_at,
                left_at=left_at,
                status_current=MembershipStatus.LEFT if left_at else MembershipStatus.MEMBER,
            )
            memberships.append(membership)

    return memberships


def create_sample_messages(chats: List[Chat], users: List[User]) -> List[Message]:
    """Create sample message data for the last 15 days."""
    messages = []
    base_date = datetime.utcnow() - timedelta(days=15)

    # Different activity patterns for each chat
    chat_patterns = {
        -1001234567890: {  # Tech chat - more active during work hours
            "daily_messages": 150,
            "peak_hours": [9, 10, 11, 14, 15, 16],
            "active_users": 30,
        },
        -1001234567891: {  # Random chat - more evening activity
            "daily_messages": 80,
            "peak_hours": [18, 19, 20, 21, 22],
            "active_users": 20,
        },
    }

    msg_id_counter = 1

    for day in range(15):
        current_date = base_date + timedelta(days=day)

        # Weekend reduction
        weekend_factor = 0.6 if current_date.weekday() >= 5 else 1.0

        for chat in chats:
            pattern = chat_patterns[chat.chat_id]
            daily_target = int(pattern["daily_messages"] * weekend_factor)

            # Distribute messages throughout the day
            for hour in range(24):
                # More messages during peak hours
                hour_factor = 2.0 if hour in pattern["peak_hours"] else 0.5
                hour_messages = int((daily_target / 24) * hour_factor)

                # Add some randomness
                hour_messages = max(0, hour_messages + random.randint(-5, 10))

                for _ in range(hour_messages):
                    # Pick a random active user
                    active_users = users[: pattern["active_users"]]
                    user = random.choice(active_users)

                    # Random time within the hour
                    minute = random.randint(0, 59)
                    second = random.randint(0, 59)
                    message_time = current_date.replace(hour=hour, minute=minute, second=second)

                    # Generate message content
                    has_media = random.random() < 0.15  # 15% have media
                    media_type = MediaType.PHOTO if has_media else MediaType.TEXT

                    # Generate realistic text lengths
                    if has_media:
                        text_len = random.randint(0, 50)  # Short captions
                    else:
                        text_len = random.randint(10, 200)  # Regular messages

                    # URLs and emojis
                    urls_cnt = 1 if random.random() < 0.05 else 0  # 5% have URLs
                    emoji_cnt = random.randint(0, 5) if random.random() < 0.3 else 0

                    message = Message(
                        chat_id=chat.chat_id,
                        msg_id=msg_id_counter,
                        user_id=user.user_id,
                        date=message_time,
                        has_media=has_media,
                        media_type=media_type,
                        text_raw=(
                            f"Sample message {msg_id_counter}" if random.random() < 0.8 else None
                        ),
                        text_len=text_len,
                        urls_cnt=urls_cnt,
                        emoji_cnt=emoji_cnt,
                        source="bot",
                    )

                    messages.append(message)
                    msg_id_counter += 1

    return messages


def create_sample_reactions(messages: List[Message]) -> List[Reaction]:
    """Create sample reaction data."""
    reactions = []
    reaction_emojis = ["👍", "❤️", "😂", "😮", "😢", "🔥", "👏"]

    # Add reactions to ~20% of messages
    for message in messages:
        if random.random() < 0.2:
            # 1-3 reactions per message
            num_reactions = random.randint(1, 3)

            for _ in range(num_reactions):
                # Random user (could be anyone, not just chat members)
                reactor_id = random.randint(1, 50)
                emoji = random.choice(reaction_emojis)

                # Reaction happens within a few hours of the message
                reaction_time = message.date + timedelta(minutes=random.randint(1, 240))

                reaction = Reaction(
                    chat_id=message.chat_id,
                    msg_id=message.msg_id,
                    user_id=reactor_id,
                    reaction_emoji=emoji,
                    is_big=random.random() < 0.1,  # 10% are "big" reactions
                    date=reaction_time,
                )

                reactions.append(reaction)

    return reactions


def seed_database():
    """Seed the database with sample data."""
    logger.info("Starting database seeding...")

    with get_sync_session() as session:
        try:
            # Create sample data
            logger.info("Creating sample chats...")
            chats = create_sample_chats()
            session.add_all(chats)

            logger.info("Creating sample users...")
            users = create_sample_users()
            session.add_all(users)

            logger.info("Creating sample settings...")
            settings = create_sample_settings(chats)
            session.add_all(settings)

            logger.info("Creating sample memberships...")
            memberships = create_sample_memberships(chats, users)
            session.add_all(memberships)

            # Commit the base data first
            session.commit()

            logger.info("Creating sample messages...")
            messages = create_sample_messages(chats, users)

            # Add messages in batches to avoid memory issues
            batch_size = 1000
            for i in range(0, len(messages), batch_size):
                batch = messages[i : i + batch_size]
                session.add_all(batch)
                session.commit()
                logger.info(f"Added message batch {i//batch_size + 1}")

            logger.info("Creating sample reactions...")
            reactions = create_sample_reactions(messages)
            session.add_all(reactions)

            session.commit()

            # Print summary
            logger.info("Database seeding completed!")
            logger.info(f"Created:")
            logger.info(f"  - {len(chats)} chats")
            logger.info(f"  - {len(users)} users")
            logger.info(f"  - {len(memberships)} memberships")
            logger.info(f"  - {len(messages)} messages")
            logger.info(f"  - {len(reactions)} reactions")

            return True

        except Exception as e:
            logger.error(f"Error seeding database: {e}", exc_info=True)
            session.rollback()
            return False


if __name__ == "__main__":
    import os
    import sys

    # Add the project root to Python path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    success = seed_database()
    sys.exit(0 if success else 1)

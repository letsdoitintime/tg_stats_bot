"""Service interfaces using Python protocols for type checking."""

from datetime import datetime
from typing import List, Optional, Protocol, runtime_checkable

from telegram import Chat as TelegramChat
from telegram import Message as TelegramMessage
from telegram import User as TelegramUser

from ..models import Chat, GroupSettings, Membership, Message, Reaction, User


@runtime_checkable
class ChatServiceProtocol(Protocol):
    """Protocol for chat service interface."""

    async def get_or_create_chat(self, telegram_chat: TelegramChat) -> Chat:
        """Get or create a chat from Telegram chat object."""
        ...

    async def setup_chat(self, chat_id: int) -> GroupSettings:
        """Initialize default settings for a chat."""
        ...

    async def get_chat_settings(self, chat_id: int) -> Optional[GroupSettings]:
        """Get chat settings."""
        ...

    async def update_text_storage(self, chat_id: int, store_text: bool) -> Optional[GroupSettings]:
        """Update text storage setting."""
        ...

    async def update_reaction_capture(
        self, chat_id: int, capture_reactions: bool
    ) -> Optional[GroupSettings]:
        """Update reaction capture setting."""
        ...


@runtime_checkable
class UserServiceProtocol(Protocol):
    """Protocol for user service interface."""

    async def get_or_create_user(self, telegram_user: TelegramUser) -> User:
        """Get or create a user from Telegram user object."""
        ...

    async def handle_user_join(self, chat_id: int, user_id: int, join_date: datetime) -> Membership:
        """Handle user joining a chat."""
        ...

    async def handle_user_leave(
        self, chat_id: int, user_id: int, leave_date: datetime
    ) -> Optional[Membership]:
        """Handle user leaving a chat."""
        ...


@runtime_checkable
class MessageServiceProtocol(Protocol):
    """Protocol for message service interface."""

    async def process_message(self, telegram_message: TelegramMessage) -> Message:
        """Process and store a Telegram message."""
        ...

    async def get_message(self, chat_id: int, msg_id: int) -> Optional[Message]:
        """Get a message by chat_id and msg_id."""
        ...


@runtime_checkable
class ReactionServiceProtocol(Protocol):
    """Protocol for reaction service interface."""

    async def process_reaction_update(self, reaction_update) -> List[Reaction]:
        """Process a reaction update."""
        ...

    async def get_message_reactions(self, chat_id: int, msg_id: int) -> List[Reaction]:
        """Get all reactions for a message."""
        ...

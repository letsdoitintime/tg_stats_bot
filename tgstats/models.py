"""Database models using SQLAlchemy 2.x."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    JSON,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .enums import ChatType, MembershipStatus, MediaType


# Helper function for timezone-aware datetime columns
def datetime_column(nullable: bool = False, **kwargs) -> Mapped[datetime]:
    """Create timezone-aware datetime column."""
    return mapped_column(DateTime(timezone=True), nullable=nullable, **kwargs)


class Chat(Base):
    """Telegram chat information."""

    __tablename__ = "chats"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    username: Mapped[Optional[str]] = mapped_column(String(255))
    type: Mapped[ChatType] = mapped_column(String(20))
    is_forum: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    photo_small_file_id: Mapped[Optional[str]] = mapped_column(String(255))
    photo_big_file_id: Mapped[Optional[str]] = mapped_column(String(255))
    invite_link: Mapped[Optional[str]] = mapped_column(String(255))
    pinned_message_id: Mapped[Optional[int]] = mapped_column(Integer)
    permissions_json: Mapped[Optional[dict]] = mapped_column(JSON)
    slow_mode_delay: Mapped[Optional[int]] = mapped_column(Integer)
    message_auto_delete_time: Mapped[Optional[int]] = mapped_column(Integer)
    has_protected_content: Mapped[Optional[bool]] = mapped_column(Boolean)
    linked_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    settings: Mapped[Optional["GroupSettings"]] = relationship(
        "GroupSettings", back_populates="chat", uselist=False
    )
    memberships: Mapped[list["Membership"]] = relationship("Membership", back_populates="chat")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="chat")


class User(Base):
    """Telegram user information."""

    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    language_code: Mapped[Optional[str]] = mapped_column(String(10))
    is_premium: Mapped[Optional[bool]] = mapped_column(Boolean)
    added_to_attachment_menu: Mapped[Optional[bool]] = mapped_column(Boolean)
    can_join_groups: Mapped[Optional[bool]] = mapped_column(Boolean)
    can_read_all_group_messages: Mapped[Optional[bool]] = mapped_column(Boolean)
    supports_inline_queries: Mapped[Optional[bool]] = mapped_column(Boolean)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    memberships: Mapped[list["Membership"]] = relationship("Membership", back_populates="user")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="user")


class Membership(Base):
    """User membership in a chat."""

    __tablename__ = "memberships"

    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.chat_id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), primary_key=True)
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status_current: Mapped[MembershipStatus] = mapped_column(String(20))

    # Relationships
    chat: Mapped["Chat"] = relationship("Chat", back_populates="memberships")
    user: Mapped["User"] = relationship("User", back_populates="memberships")


class GroupSettings(Base):
    """Per-group configuration settings."""

    __tablename__ = "group_settings"

    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.chat_id"), primary_key=True)
    store_text: Mapped[bool] = mapped_column(Boolean, default=False)
    text_retention_days: Mapped[int] = mapped_column(Integer, default=90)
    metadata_retention_days: Mapped[int] = mapped_column(Integer, default=365)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    locale: Mapped[str] = mapped_column(String(10), default="en")
    capture_reactions: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    chat: Mapped["Chat"] = relationship("Chat", back_populates="settings")


class Message(Base):
    """Telegram message with analytics features."""

    __tablename__ = "messages"

    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.chat_id"), primary_key=True)
    msg_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    date: Mapped[datetime] = mapped_column(DateTime)
    edit_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    thread_id: Mapped[Optional[int]] = mapped_column(Integer)
    reply_to_msg_id: Mapped[Optional[int]] = mapped_column(Integer)
    has_media: Mapped[bool] = mapped_column(Boolean, default=False)
    media_type: Mapped[MediaType] = mapped_column(String(20), default=MediaType.TEXT)
    text_raw: Mapped[Optional[str]] = mapped_column(Text)
    text_len: Mapped[int] = mapped_column(Integer, default=0)
    urls_cnt: Mapped[int] = mapped_column(Integer, default=0)
    emoji_cnt: Mapped[int] = mapped_column(Integer, default=0)
    entities_json: Mapped[Optional[dict]] = mapped_column(JSON)
    caption_entities_json: Mapped[Optional[dict]] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(20), default="bot")

    # Forward information
    forward_from_user_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    forward_from_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    forward_from_message_id: Mapped[Optional[int]] = mapped_column(Integer)
    forward_signature: Mapped[Optional[str]] = mapped_column(String(255))
    forward_sender_name: Mapped[Optional[str]] = mapped_column(String(255))
    forward_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_automatic_forward: Mapped[Optional[bool]] = mapped_column(Boolean)

    # Additional message metadata
    via_bot_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    author_signature: Mapped[Optional[str]] = mapped_column(String(255))
    media_group_id: Mapped[Optional[str]] = mapped_column(String(255))
    has_protected_content: Mapped[Optional[bool]] = mapped_column(Boolean)
    web_page_json: Mapped[Optional[dict]] = mapped_column(JSON)

    # Media file metadata
    file_id: Mapped[Optional[str]] = mapped_column(String(255))
    file_unique_id: Mapped[Optional[str]] = mapped_column(String(255))
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger)
    file_name: Mapped[Optional[str]] = mapped_column(String(255))
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    duration: Mapped[Optional[int]] = mapped_column(Integer)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    thumbnail_file_id: Mapped[Optional[str]] = mapped_column(String(255))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="messages")
    reactions: Mapped[list["Reaction"]] = relationship("Reaction", back_populates="message")

    # Indexes
    __table_args__ = (
        Index("ix_messages_chat_date", "chat_id", "date"),
        Index("ix_messages_chat_user_date", "chat_id", "user_id", "date"),
        Index("ix_messages_forward_from", "forward_from_user_id"),
        Index("ix_messages_via_bot", "via_bot_id"),
        Index("ix_messages_media_type", "media_type"),
        Index("ix_messages_media_group_id", "media_group_id"),
        Index("ix_messages_reply_chain", "chat_id", "reply_to_msg_id"),
        Index("ix_messages_thread_id", "thread_id"),
        Index("ix_messages_deleted_at", "deleted_at"),
    )


class Reaction(Base):
    """Telegram message reactions."""

    __tablename__ = "reactions"

    reaction_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.chat_id"))
    msg_id: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    reaction_emoji: Mapped[str] = mapped_column(String(100))
    is_big: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    removed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    chat: Mapped["Chat"] = relationship("Chat", overlaps="reactions")
    user: Mapped[Optional["User"]] = relationship("User")
    message: Mapped["Message"] = relationship(
        "Message", back_populates="reactions", overlaps="chat"
    )

    # Indexes and constraints
    __table_args__ = (
        Index("ix_reactions_chat_date", "chat_id", "date"),
        Index("ix_reactions_emoji", "reaction_emoji"),
        Index("ix_reactions_msg", "chat_id", "msg_id"),
        Index(
            "ix_reactions_user_msg_emoji",
            "user_id",
            "chat_id",
            "msg_id",
            "reaction_emoji",
            unique=True,
        ),
        ForeignKeyConstraint(
            ["chat_id", "msg_id"],
            ["messages.chat_id", "messages.msg_id"],
            name="fk_reactions_message",
        ),
    )

"""add extended telegram fields

Revision ID: 005_add_extended_telegram_fields
Revises: d25c72be7a85
Create Date: 2025-12-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_add_extended_telegram_fields'
down_revision = '004_create_aggregates'
branch_label = None
depends_on = None


def upgrade() -> None:
    # Add new columns to chats table
    op.add_column('chats', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('chats', sa.Column('photo_small_file_id', sa.String(length=255), nullable=True))
    op.add_column('chats', sa.Column('photo_big_file_id', sa.String(length=255), nullable=True))
    op.add_column('chats', sa.Column('invite_link', sa.String(length=255), nullable=True))
    op.add_column('chats', sa.Column('pinned_message_id', sa.Integer(), nullable=True))
    op.add_column('chats', sa.Column('permissions_json', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('chats', sa.Column('slow_mode_delay', sa.Integer(), nullable=True))
    op.add_column('chats', sa.Column('message_auto_delete_time', sa.Integer(), nullable=True))
    op.add_column('chats', sa.Column('has_protected_content', sa.Boolean(), nullable=True))
    op.add_column('chats', sa.Column('linked_chat_id', sa.BigInteger(), nullable=True))

    # Add new columns to users table
    op.add_column('users', sa.Column('is_premium', sa.Boolean(), nullable=True))
    op.add_column('users', sa.Column('added_to_attachment_menu', sa.Boolean(), nullable=True))
    op.add_column('users', sa.Column('can_join_groups', sa.Boolean(), nullable=True))
    op.add_column('users', sa.Column('can_read_all_group_messages', sa.Boolean(), nullable=True))
    op.add_column('users', sa.Column('supports_inline_queries', sa.Boolean(), nullable=True))

    # Add new columns to messages table
    op.add_column('messages', sa.Column('caption_entities_json', postgresql.JSON(astext_type=sa.Text()), nullable=True))

    # Forward information
    op.add_column('messages', sa.Column('forward_from_user_id', sa.BigInteger(), nullable=True))
    op.add_column('messages', sa.Column('forward_from_chat_id', sa.BigInteger(), nullable=True))
    op.add_column('messages', sa.Column('forward_from_message_id', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('forward_signature', sa.String(length=255), nullable=True))
    op.add_column('messages', sa.Column('forward_sender_name', sa.String(length=255), nullable=True))
    op.add_column('messages', sa.Column('forward_date', sa.DateTime(), nullable=True))
    op.add_column('messages', sa.Column('is_automatic_forward', sa.Boolean(), nullable=True))

    # Additional message metadata
    op.add_column('messages', sa.Column('via_bot_id', sa.BigInteger(), nullable=True))
    op.add_column('messages', sa.Column('author_signature', sa.String(length=255), nullable=True))
    op.add_column('messages', sa.Column('media_group_id', sa.String(length=255), nullable=True))
    op.add_column('messages', sa.Column('has_protected_content', sa.Boolean(), nullable=True))
    op.add_column('messages', sa.Column('web_page_json', postgresql.JSON(astext_type=sa.Text()), nullable=True))

    # Media file metadata
    op.add_column('messages', sa.Column('file_id', sa.String(length=255), nullable=True))
    op.add_column('messages', sa.Column('file_unique_id', sa.String(length=255), nullable=True))
    op.add_column('messages', sa.Column('file_size', sa.BigInteger(), nullable=True))
    op.add_column('messages', sa.Column('file_name', sa.String(length=255), nullable=True))
    op.add_column('messages', sa.Column('mime_type', sa.String(length=100), nullable=True))
    op.add_column('messages', sa.Column('duration', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('width', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('height', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('thumbnail_file_id', sa.String(length=255), nullable=True))

    # Create indexes for commonly queried fields
    op.create_index('ix_messages_forward_from_user', 'messages', ['forward_from_user_id'], unique=False)
    op.create_index('ix_messages_forward_from_chat', 'messages', ['forward_from_chat_id'], unique=False)
    op.create_index('ix_messages_media_group_id', 'messages', ['media_group_id'], unique=False)
    op.create_index('ix_messages_via_bot', 'messages', ['via_bot_id'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_messages_via_bot', table_name='messages')
    op.drop_index('ix_messages_media_group_id', table_name='messages')
    op.drop_index('ix_messages_forward_from_chat', table_name='messages')
    op.drop_index('ix_messages_forward_from_user', table_name='messages')

    # Remove columns from messages table
    op.drop_column('messages', 'thumbnail_file_id')
    op.drop_column('messages', 'height')
    op.drop_column('messages', 'width')
    op.drop_column('messages', 'duration')
    op.drop_column('messages', 'mime_type')
    op.drop_column('messages', 'file_name')
    op.drop_column('messages', 'file_size')
    op.drop_column('messages', 'file_unique_id')
    op.drop_column('messages', 'file_id')
    op.drop_column('messages', 'web_page_json')
    op.drop_column('messages', 'has_protected_content')
    op.drop_column('messages', 'media_group_id')
    op.drop_column('messages', 'author_signature')
    op.drop_column('messages', 'via_bot_id')
    op.drop_column('messages', 'is_automatic_forward')
    op.drop_column('messages', 'forward_date')
    op.drop_column('messages', 'forward_sender_name')
    op.drop_column('messages', 'forward_signature')
    op.drop_column('messages', 'forward_from_message_id')
    op.drop_column('messages', 'forward_from_chat_id')
    op.drop_column('messages', 'forward_from_user_id')
    op.drop_column('messages', 'caption_entities_json')

    # Remove columns from users table
    op.drop_column('users', 'supports_inline_queries')
    op.drop_column('users', 'can_read_all_group_messages')
    op.drop_column('users', 'can_join_groups')
    op.drop_column('users', 'added_to_attachment_menu')
    op.drop_column('users', 'is_premium')

    # Remove columns from chats table
    op.drop_column('chats', 'linked_chat_id')
    op.drop_column('chats', 'has_protected_content')
    op.drop_column('chats', 'message_auto_delete_time')
    op.drop_column('chats', 'slow_mode_delay')
    op.drop_column('chats', 'permissions_json')
    op.drop_column('chats', 'pinned_message_id')
    op.drop_column('chats', 'invite_link')
    op.drop_column('chats', 'photo_big_file_id')
    op.drop_column('chats', 'photo_small_file_id')
    op.drop_column('chats', 'description')

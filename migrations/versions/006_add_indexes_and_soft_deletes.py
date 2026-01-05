"""Add missing indexes and soft deletes

Revision ID: 006_add_indexes_and_soft_deletes
Revises: 005_add_extended_telegram_fields
Create Date: 2025-12-16

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006_add_indexes_and_soft_deletes'
down_revision = '005_add_extended_telegram_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing indexes and soft delete columns."""

    # Get connection to check for existing indexes
    conn = op.get_bind()

    # Add soft delete columns to key models (check if they exist first)
    inspector = sa.inspect(conn)
    chats_columns = [col['name'] for col in inspector.get_columns('chats')]
    users_columns = [col['name'] for col in inspector.get_columns('users')]
    messages_columns = [col['name'] for col in inspector.get_columns('messages')]

    if 'deleted_at' not in chats_columns:
        op.add_column('chats', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    if 'deleted_at' not in users_columns:
        op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    if 'deleted_at' not in messages_columns:
        op.add_column('messages', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    # Helper function to check if index exists
    def index_exists(table_name: str, index_name: str) -> bool:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes

    # Add indexes for soft deletes
    if not index_exists('chats', 'ix_chats_deleted_at'):
        op.create_index('ix_chats_deleted_at', 'chats', ['deleted_at'], unique=False)
    if not index_exists('users', 'ix_users_deleted_at'):
        op.create_index('ix_users_deleted_at', 'users', ['deleted_at'], unique=False)
    if not index_exists('messages', 'ix_messages_deleted_at'):
        op.create_index('ix_messages_deleted_at', 'messages', ['deleted_at'], unique=False)

    # Add missing indexes for common query patterns
    if not index_exists('messages', 'ix_messages_forward_from'):
        op.create_index('ix_messages_forward_from', 'messages', ['forward_from_user_id'], unique=False)
    if not index_exists('messages', 'ix_messages_via_bot'):
        op.create_index('ix_messages_via_bot', 'messages', ['via_bot_id'], unique=False)
    if not index_exists('messages', 'ix_messages_media_type'):
        op.create_index('ix_messages_media_type', 'messages', ['media_type'], unique=False)
    if not index_exists('messages', 'ix_messages_media_group_id'):
        op.create_index('ix_messages_media_group_id', 'messages', ['media_group_id'], unique=False)

    # Add composite index for reply chains
    if not index_exists('messages', 'ix_messages_reply_chain'):
        op.create_index('ix_messages_reply_chain', 'messages', ['chat_id', 'reply_to_msg_id'], unique=False)

    # Add index for thread queries
    if not index_exists('messages', 'ix_messages_thread_id'):
        op.create_index('ix_messages_thread_id', 'messages', ['thread_id'], unique=False)

    # Add indexes for reaction queries
    if not index_exists('reactions', 'ix_reactions_user_emoji'):
        op.create_index('ix_reactions_user_emoji', 'reactions', ['user_id', 'reaction_emoji'], unique=False)

    # Add indexes for membership queries
    if not index_exists('memberships', 'ix_memberships_status'):
        op.create_index('ix_memberships_status', 'memberships', ['status_current'], unique=False)
    if not index_exists('memberships', 'ix_memberships_joined_at'):
        op.create_index('ix_memberships_joined_at', 'memberships', ['joined_at'], unique=False)
    if not index_exists('memberships', 'ix_memberships_left_at'):
        op.create_index('ix_memberships_left_at', 'memberships', ['left_at'], unique=False)


def downgrade() -> None:
    """Remove indexes and soft delete columns."""

    # Remove membership indexes
    op.drop_index('ix_memberships_left_at', table_name='memberships')
    op.drop_index('ix_memberships_joined_at', table_name='memberships')
    op.drop_index('ix_memberships_status', table_name='memberships')

    # Remove reaction indexes
    op.drop_index('ix_reactions_user_emoji', table_name='reactions')

    # Remove message indexes
    op.drop_index('ix_messages_thread_id', table_name='messages')
    op.drop_index('ix_messages_reply_chain', table_name='messages')
    op.drop_index('ix_messages_media_group_id', table_name='messages')
    op.drop_index('ix_messages_media_type', table_name='messages')
    op.drop_index('ix_messages_via_bot', table_name='messages')
    op.drop_index('ix_messages_forward_from', table_name='messages')

    # Remove soft delete indexes
    op.drop_index('ix_messages_deleted_at', table_name='messages')
    op.drop_index('ix_users_deleted_at', table_name='users')
    op.drop_index('ix_chats_deleted_at', table_name='chats')

    # Remove soft delete columns
    op.drop_column('messages', 'deleted_at')
    op.drop_column('users', 'deleted_at')
    op.drop_column('chats', 'deleted_at')

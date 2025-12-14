"""Initial database schema

Revision ID: 001
Revises: 
Create Date: 2025-01-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create chats table
    op.create_table('chats',
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('is_forum', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('chat_id')
    )
    
    # Create users table
    op.create_table('users',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('first_name', sa.String(length=255), nullable=True),
        sa.Column('last_name', sa.String(length=255), nullable=True),
        sa.Column('is_bot', sa.Boolean(), nullable=False),
        sa.Column('language_code', sa.String(length=10), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('user_id')
    )
    
    # Create group_settings table
    op.create_table('group_settings',
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('store_text', sa.Boolean(), nullable=False),
        sa.Column('text_retention_days', sa.Integer(), nullable=False),
        sa.Column('metadata_retention_days', sa.Integer(), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=False),
        sa.Column('locale', sa.String(length=10), nullable=False),
        sa.Column('capture_reactions', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['chat_id'], ['chats.chat_id'], ),
        sa.PrimaryKeyConstraint('chat_id')
    )
    
    # Create memberships table
    op.create_table('memberships',
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
        sa.Column('left_at', sa.DateTime(), nullable=True),
        sa.Column('status_current', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['chat_id'], ['chats.chat_id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('chat_id', 'user_id')
    )
    
    # Create messages table
    op.create_table('messages',
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('msg_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('edit_date', sa.DateTime(), nullable=True),
        sa.Column('thread_id', sa.Integer(), nullable=True),
        sa.Column('reply_to_msg_id', sa.Integer(), nullable=True),
        sa.Column('has_media', sa.Boolean(), nullable=False),
        sa.Column('media_type', sa.String(length=20), nullable=False),
        sa.Column('text_raw', sa.Text(), nullable=True),
        sa.Column('text_len', sa.Integer(), nullable=False),
        sa.Column('urls_cnt', sa.Integer(), nullable=False),
        sa.Column('emoji_cnt', sa.Integer(), nullable=False),
        sa.Column('entities_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['chat_id'], ['chats.chat_id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('chat_id', 'msg_id')
    )
    
    # Create indexes
    op.create_index('ix_messages_chat_date', 'messages', ['chat_id', 'date'], unique=False)
    op.create_index('ix_messages_chat_user_date', 'messages', ['chat_id', 'user_id', 'date'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_messages_chat_user_date', table_name='messages')
    op.drop_index('ix_messages_chat_date', table_name='messages')
    
    # Drop tables in reverse order
    op.drop_table('messages')
    op.drop_table('memberships')
    op.drop_table('group_settings')
    op.drop_table('users')
    op.drop_table('chats')

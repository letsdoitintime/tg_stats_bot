"""convert_datetime_columns_to_timestamptz

Revision ID: 0488f83f531c
Revises: 006_add_indexes_and_soft_deletes
Create Date: 2026-01-06 09:51:15.468611

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0488f83f531c'
down_revision = '006_add_indexes_and_soft_deletes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop all materialized views that depend on the date column
    op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_daily_mv CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_hourly_mv CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS user_activity_mv CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_daily_stats CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_30d_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS user_chat_daily_mv CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_hourly_heatmap_mv CASCADE")
    
    # Convert messages table datetime columns to timestamptz
    op.execute("""
        ALTER TABLE messages 
        ALTER COLUMN date TYPE TIMESTAMP WITH TIME ZONE 
        USING date AT TIME ZONE 'UTC'
    """)
    
    op.execute("""
        ALTER TABLE messages 
        ALTER COLUMN edit_date TYPE TIMESTAMP WITH TIME ZONE 
        USING edit_date AT TIME ZONE 'UTC'
    """)
    
    op.execute("""
        ALTER TABLE messages 
        ALTER COLUMN forward_date TYPE TIMESTAMP WITH TIME ZONE 
        USING forward_date AT TIME ZONE 'UTC'
    """)
    
    # Convert reactions table datetime columns to timestamptz
    op.execute("""
        ALTER TABLE reactions 
        ALTER COLUMN date TYPE TIMESTAMP WITH TIME ZONE 
        USING date AT TIME ZONE 'UTC'
    """)
    
    op.execute("""
        ALTER TABLE reactions 
        ALTER COLUMN removed_at TYPE TIMESTAMP WITH TIME ZONE 
        USING removed_at AT TIME ZONE 'UTC'
    """)
    
    # Convert memberships table datetime columns to timestamptz
    op.execute("""
        ALTER TABLE memberships 
        ALTER COLUMN joined_at TYPE TIMESTAMP WITH TIME ZONE 
        USING joined_at AT TIME ZONE 'UTC'
    """)
    
    op.execute("""
        ALTER TABLE memberships 
        ALTER COLUMN left_at TYPE TIMESTAMP WITH TIME ZONE 
        USING left_at AT TIME ZONE 'UTC'
    """)
    
    # Recreate materialized views with timezone-aware columns
    # These match the definitions from migration 004_create_aggregates.py
    
    # Chat daily aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW chat_daily_mv AS
        SELECT 
            chat_id,
            DATE(date AT TIME ZONE 'UTC') AS day,
            COUNT(*) as msg_cnt,
            COUNT(DISTINCT user_id) as dau,
            COUNT(DISTINCT CASE WHEN has_media THEN user_id END) as media_users,
            SUM(text_len) as total_text_len,
            AVG(text_len) as avg_text_len,
            COUNT(*) FILTER (WHERE urls_cnt > 0) as msgs_with_urls,
            COUNT(*) FILTER (WHERE emoji_cnt > 0) as msgs_with_emoji,
            COUNT(*) FILTER (WHERE thread_id IS NOT NULL) as thread_msgs
        FROM messages 
        WHERE date IS NOT NULL
        GROUP BY chat_id, DATE(date AT TIME ZONE 'UTC')
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_daily_mv_chat_date 
        ON chat_daily_mv(chat_id, day)
    """)
    
    # User-chat daily aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW user_chat_daily_mv AS
        SELECT 
            chat_id,
            user_id,
            DATE(date AT TIME ZONE 'UTC') AS day,
            COUNT(*) as msg_cnt,
            SUM(text_len) as total_text_len,
            COUNT(*) FILTER (WHERE has_media) as media_msgs,
            COUNT(*) FILTER (WHERE urls_cnt > 0) as msgs_with_urls,
            COUNT(*) FILTER (WHERE emoji_cnt > 0) as msgs_with_emoji,
            MAX(date) as last_msg_at
        FROM messages 
        WHERE date IS NOT NULL AND user_id IS NOT NULL
        GROUP BY chat_id, user_id, DATE(date AT TIME ZONE 'UTC')
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_chat_daily_mv 
        ON user_chat_daily_mv(chat_id, user_id, day)
    """)
    
    # Chat hourly heatmap
    op.execute("""
        CREATE MATERIALIZED VIEW chat_hourly_heatmap_mv AS
        SELECT 
            chat_id,
            DATE_TRUNC('hour', date) AS hour_bucket,
            EXTRACT(ISODOW FROM date) AS weekday,  -- 1=Monday, 7=Sunday
            EXTRACT(HOUR FROM date) AS hour,
            COUNT(*) as msg_cnt,
            COUNT(DISTINCT user_id) as unique_users
        FROM messages 
        WHERE date IS NOT NULL
        GROUP BY chat_id, DATE_TRUNC('hour', date), 
                 EXTRACT(ISODOW FROM date), EXTRACT(HOUR FROM date)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_hourly_heatmap_mv 
        ON chat_hourly_heatmap_mv(chat_id, weekday, hour)
    """)


def downgrade() -> None:
    # Drop all materialized views
    op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_daily_mv CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_hourly_mv CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS user_activity_mv CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_daily_stats CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_30d_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS user_chat_daily_mv CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_hourly_heatmap_mv CASCADE")
    
    # Revert to timestamp without time zone
    op.execute("""
        ALTER TABLE messages 
        ALTER COLUMN date TYPE TIMESTAMP WITHOUT TIME ZONE 
        USING date AT TIME ZONE 'UTC'
    """)
    
    op.execute("""
        ALTER TABLE messages 
        ALTER COLUMN edit_date TYPE TIMESTAMP WITHOUT TIME ZONE 
        USING edit_date AT TIME ZONE 'UTC'
    """)
    
    op.execute("""
        ALTER TABLE messages 
        ALTER COLUMN forward_date TYPE TIMESTAMP WITHOUT TIME ZONE 
        USING forward_date AT TIME ZONE 'UTC'
    """)
    
    op.execute("""
        ALTER TABLE reactions 
        ALTER COLUMN date TYPE TIMESTAMP WITHOUT TIME ZONE 
        USING date AT TIME ZONE 'UTC'
    """)
    
    op.execute("""
        ALTER TABLE reactions 
        ALTER COLUMN removed_at TYPE TIMESTAMP WITHOUT TIME ZONE 
        USING removed_at AT TIME ZONE 'UTC'
    """)
    
    op.execute("""
        ALTER TABLE memberships 
        ALTER COLUMN joined_at TYPE TIMESTAMP WITHOUT TIME ZONE 
        USING joined_at AT TIME ZONE 'UTC'
    """)
    
    op.execute("""
        ALTER TABLE memberships 
        ALTER COLUMN left_at TYPE TIMESTAMP WITHOUT TIME ZONE 
        USING left_at AT TIME ZONE 'UTC'
    """)
    
    # Recreate original materialized views without timezone
    op.execute("""
        CREATE MATERIALIZED VIEW chat_daily_mv AS
        SELECT 
            chat_id,
            DATE(date) AS day,
            COUNT(*) as msg_cnt,
            COUNT(DISTINCT user_id) as dau,
            COUNT(DISTINCT CASE WHEN has_media THEN user_id END) as media_users,
            SUM(text_len) as total_text_len,
            AVG(text_len) as avg_text_len,
            COUNT(*) FILTER (WHERE urls_cnt > 0) as msgs_with_urls,
            COUNT(*) FILTER (WHERE emoji_cnt > 0) as msgs_with_emoji,
            COUNT(*) FILTER (WHERE thread_id IS NOT NULL) as thread_msgs
        FROM messages 
        WHERE date IS NOT NULL
        GROUP BY chat_id, DATE(date)
    """)
    
    op.execute("""
        CREATE INDEX idx_chat_daily_mv_chat_date 
        ON chat_daily_mv(chat_id, day)
    """)
    
    op.execute("""
        CREATE MATERIALIZED VIEW user_chat_daily_mv AS
        SELECT 
            chat_id,
            user_id,
            DATE(date) AS day,
            COUNT(*) as msg_cnt,
            SUM(text_len) as total_text_len,
            COUNT(*) FILTER (WHERE has_media) as media_msgs,
            COUNT(*) FILTER (WHERE urls_cnt > 0) as msgs_with_urls,
            COUNT(*) FILTER (WHERE emoji_cnt > 0) as msgs_with_emoji,
            MAX(date) as last_msg_at
        FROM messages 
        WHERE date IS NOT NULL AND user_id IS NOT NULL
        GROUP BY chat_id, user_id, DATE(date)
    """)
    
    op.execute("""
        CREATE INDEX idx_user_chat_daily_mv 
        ON user_chat_daily_mv(chat_id, user_id, day)
    """)
    
    op.execute("""
        CREATE MATERIALIZED VIEW chat_hourly_heatmap_mv AS
        SELECT 
            chat_id,
            DATE_TRUNC('hour', date) AS hour_bucket,
            EXTRACT(ISODOW FROM date) AS weekday,
            EXTRACT(HOUR FROM date) AS hour,
            COUNT(*) as msg_cnt,
            COUNT(DISTINCT user_id) as unique_users
        FROM messages 
        WHERE date IS NOT NULL
        GROUP BY chat_id, DATE_TRUNC('hour', date), 
                 EXTRACT(ISODOW FROM date), EXTRACT(HOUR FROM date)
    """)
    
    op.execute("""
        CREATE INDEX idx_chat_hourly_heatmap_mv 
        ON chat_hourly_heatmap_mv(chat_id, weekday, hour)
    """)

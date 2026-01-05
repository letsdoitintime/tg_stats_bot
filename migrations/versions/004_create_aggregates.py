"""Create continuous aggregates and materialized views

Revision ID: 004_create_aggregates
Revises: 003_create_hypertable
Create Date: 2025-01-21 11:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004_create_aggregates'
down_revision = '003_create_hypertable'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create continuous aggregates or materialized views."""
    connection = op.get_bind()

    # Check if TimescaleDB extension exists
    try:
        result = connection.execute(
            sa.text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
        ).fetchone()

        if result:
            # TimescaleDB is available, create continuous aggregates
            create_timescale_aggregates()
        else:
            # Fallback to materialized views
            create_materialized_views()
    except Exception:
        # If there's any error checking for TimescaleDB, default to materialized views
        create_materialized_views()

    # Create indexes for both cases
    create_aggregate_indexes()


def create_timescale_aggregates():
    """Create TimescaleDB continuous aggregates."""

    # Chat daily aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW chat_daily
        WITH (timescaledb.continuous) AS
        SELECT 
            chat_id,
            time_bucket('1 day', date) AS day,
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
        GROUP BY chat_id, time_bucket('1 day', date)
        WITH NO DATA;
    """)

    # User-chat daily aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW user_chat_daily
        WITH (timescaledb.continuous) AS
        SELECT 
            chat_id,
            user_id,
            time_bucket('1 day', date) AS day,
            COUNT(*) as msg_cnt,
            SUM(text_len) as total_text_len,
            COUNT(*) FILTER (WHERE has_media) as media_msgs,
            COUNT(*) FILTER (WHERE urls_cnt > 0) as msgs_with_urls,
            COUNT(*) FILTER (WHERE emoji_cnt > 0) as msgs_with_emoji,
            MAX(date) as last_msg_at
        FROM messages 
        WHERE date IS NOT NULL AND user_id IS NOT NULL
        GROUP BY chat_id, user_id, time_bucket('1 day', date)
        WITH NO DATA;
    """)

    # Chat hourly heatmap
    op.execute("""
        CREATE MATERIALIZED VIEW chat_hourly_heatmap
        WITH (timescaledb.continuous) AS
        SELECT 
            chat_id,
            time_bucket('1 hour', date) AS hour_bucket,
            EXTRACT(ISODOW FROM date) AS weekday,  -- 1=Monday, 7=Sunday
            EXTRACT(HOUR FROM date) AS hour,
            COUNT(*) as msg_cnt,
            COUNT(DISTINCT user_id) as unique_users
        FROM messages 
        WHERE date IS NOT NULL
        GROUP BY chat_id, time_bucket('1 hour', date), 
                 EXTRACT(ISODOW FROM date), EXTRACT(HOUR FROM date)
        WITH NO DATA;
    """)


def create_materialized_views():
    """Create regular materialized views for PostgreSQL fallback."""

    # Chat daily aggregate
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
        GROUP BY chat_id, DATE(date);
    """)

    # User-chat daily aggregate
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
        GROUP BY chat_id, user_id, DATE(date);
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
                 EXTRACT(ISODOW FROM date), EXTRACT(HOUR FROM date);
    """)


def create_aggregate_indexes():
    """Create indexes for aggregate tables."""
    connection = op.get_bind()

    # Check if TimescaleDB extension exists
    try:
        result = connection.execute(
            sa.text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
        ).fetchone()

        if result:
            # Indexes for continuous aggregates
            op.execute("CREATE INDEX IF NOT EXISTS ix_chat_daily_chat_day ON chat_daily (chat_id, day);")
            op.execute("CREATE INDEX IF NOT EXISTS ix_user_chat_daily_chat_user_day ON user_chat_daily (chat_id, user_id, day);")
            op.execute("CREATE INDEX IF NOT EXISTS ix_chat_hourly_heatmap_chat_hour ON chat_hourly_heatmap (chat_id, hour_bucket);")
        else:
            # Indexes for materialized views
            op.execute("CREATE INDEX IF NOT EXISTS ix_chat_daily_mv_chat_day ON chat_daily_mv (chat_id, day);")
            op.execute("CREATE INDEX IF NOT EXISTS ix_user_chat_daily_mv_chat_user_day ON user_chat_daily_mv (chat_id, user_id, day);")
            op.execute("CREATE INDEX IF NOT EXISTS ix_chat_hourly_heatmap_mv_chat_hour ON chat_hourly_heatmap_mv (chat_id, hour_bucket);")
    except Exception:
        # Default to materialized view indexes
        try:
            op.execute("CREATE INDEX IF NOT EXISTS ix_chat_daily_mv_chat_day ON chat_daily_mv (chat_id, day);")
            op.execute("CREATE INDEX IF NOT EXISTS ix_user_chat_daily_mv_chat_user_day ON user_chat_daily_mv (chat_id, user_id, day);")
            op.execute("CREATE INDEX IF NOT EXISTS ix_chat_hourly_heatmap_mv_chat_hour ON chat_hourly_heatmap_mv (chat_id, hour_bucket);")
        except Exception:
            # If even materialized views don't exist, that's fine
            pass


def downgrade() -> None:
    """Drop aggregates and materialized views."""
    connection = op.get_bind()

    # Check if TimescaleDB extension exists
    result = connection.execute(
        sa.text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
    ).fetchone()

    if result:
        # Drop continuous aggregates
        op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_daily;")
        op.execute("DROP MATERIALIZED VIEW IF EXISTS user_chat_daily;")
        op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_hourly_heatmap;")
    else:
        # Drop materialized views
        op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_daily_mv;")
        op.execute("DROP MATERIALIZED VIEW IF EXISTS user_chat_daily_mv;")
        op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_hourly_heatmap_mv;")

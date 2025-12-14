"""Create messages hypertable

Revision ID: 003_create_hypertable
Revises: 002_enable_timescaledb
Create Date: 2025-01-21 11:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_create_hypertable'
down_revision = '002_enable_timescaledb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert messages table to hypertable if TimescaleDB is available."""
    # Check if TimescaleDB extension exists
    connection = op.get_bind()
    try:
        result = connection.execute(
            sa.text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
        ).fetchone()
        
        if result:
            # TimescaleDB is available, create hypertable
            op.execute("""
                SELECT create_hypertable(
                    'messages', 
                    by_range => 'date', 
                    if_not_exists => TRUE, 
                    chunk_time_interval => INTERVAL '7 days'
                );
            """)
    except Exception:
        # TimescaleDB not available or other error, skip hypertable creation
        pass


def downgrade() -> None:
    """Cannot easily convert hypertable back to regular table."""
    # In practice, you don't typically downgrade hypertables
    # This would require data migration which is complex
    pass

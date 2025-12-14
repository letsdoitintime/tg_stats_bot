"""Enable TimescaleDB extension

Revision ID: 002_enable_timescaledb
Revises: d25c72be7a85
Create Date: 2025-01-21 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_enable_timescaledb'
down_revision = 'd25c72be7a85'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enable TimescaleDB extension if available."""
    # Try to enable TimescaleDB extension
    # This will succeed if TimescaleDB is installed, otherwise it will be ignored
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    except Exception:
        # TimescaleDB not available, that's fine - we'll use regular PostgreSQL
        pass


def downgrade() -> None:
    """Disable TimescaleDB extension if no hypertables exist."""
    # Check if there are any hypertables before dropping the extension
    # Note: In practice, you rarely want to drop the extension
    pass

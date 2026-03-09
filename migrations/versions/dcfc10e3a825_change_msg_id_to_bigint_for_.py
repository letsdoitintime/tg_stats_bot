"""change_msg_id_to_bigint_for_compatibility

Revision ID: dcfc10e3a825
Revises: 0488f83f531c
Create Date: 2026-01-31 18:44:56.513545

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dcfc10e3a825'
down_revision = '0488f83f531c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Change msg_id and reply_to_msg_id from INTEGER to BIGINT for large chat compatibility."""
    # Change msg_id type (part of composite primary key)
    op.alter_column('messages', 'msg_id',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)
    
    # Change reply_to_msg_id type (foreign key reference)
    op.alter_column('messages', 'reply_to_msg_id',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)
    
    # Change reactions.msg_id type (foreign key reference)
    op.alter_column('reactions', 'msg_id',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)


def downgrade() -> None:
    """Revert msg_id columns back to INTEGER."""
    # Revert reactions.msg_id
    op.alter_column('reactions', 'msg_id',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False)
    
    # Revert messages.reply_to_msg_id
    op.alter_column('messages', 'reply_to_msg_id',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True)
    
    # Revert messages.msg_id
    op.alter_column('messages', 'msg_id',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False)

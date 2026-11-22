"""add idempotency_keys

Revision ID: 70937e06f915
Revises: d64c6657d3c0
Create Date: 2026-11-22 17:31:04.143251

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '70937e06f915'
down_revision: Union[str, Sequence[str], None] = 'd64c6657d3c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'idempotency_keys',
        sa.Column('key', sa.String(length=250), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('ticket_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
        sa.PrimaryKeyConstraint('key')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('idempotency_keys')

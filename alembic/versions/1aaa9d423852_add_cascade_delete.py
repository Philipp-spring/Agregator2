"""add cascade delete

Revision ID: 1aaa9d423852
Revises: 70937e06f915
Create Date: 2026-11-22 19:18:34.595723

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1aaa9d423852'
down_revision: Union[str, Sequence[str], None] = '70937e06f915'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table('idempotency_keys'):
        op.create_table(
            'idempotency_keys',
            sa.Column('key', sa.String(length=250), nullable=False),
            sa.Column('request_hash', sa.String(length=64), nullable=False),
            sa.Column('ticket_id', sa.UUID(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('key')
        )
    else:
        op.drop_constraint('idempotency_keys_ticket_id_fkey', 'idempotency_keys', type_='foreignkey')
        op.create_foreign_key(
            'idempotency_keys_ticket_id_fkey',
            'idempotency_keys',
            'tickets',
            ['ticket_id'],
            ['id'],
            ondelete='CASCADE'
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('idempotency_keys_ticket_id_fkey', 'idempotency_keys', type_='foreignkey')
    op.create_foreign_key(
        'idempotency_keys_ticket_id_fkey',
        'idempotency_keys',
        'tickets',
        ['ticket_id'],
        ['id']
    )


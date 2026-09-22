"""0008_add_weighbridge_events

Revision ID: 0008_add_weighbridge_events
Revises: 0007_add_showcase_discriminators
Create Date: 2026-09-22 11:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0008_add_weighbridge_events'
down_revision: Union[str, None] = '0007_add_showcase_discriminators'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'weighbridge_events' not in existing_tables:
        op.create_table(
            'weighbridge_events',
            sa.Column('event_id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('mandi_id', sa.Integer(), nullable=False),
            sa.Column('transaction_id', sa.String(length=64), nullable=True),
            sa.Column('scale_id', sa.String(length=50), server_default='SCALE-01', nullable=False),
            sa.Column('gross_weight_qt', sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column('tare_weight_qt', sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column('net_weight_qt', sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.ForeignKeyConstraint(['mandi_id'], ['mandis.mandi_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('event_id')
        )
        op.create_index('ix_weighbridge_events_event_id', 'weighbridge_events', ['event_id'], unique=False)
        op.create_index('ix_weighbridge_events_mandi_id', 'weighbridge_events', ['mandi_id'], unique=False)
        op.create_index('ix_weighbridge_events_transaction_id', 'weighbridge_events', ['transaction_id'], unique=False)
        op.create_index('ix_weighbridge_events_completed_at', 'weighbridge_events', ['completed_at'], unique=False)
        op.create_index('idx_weighbridge_events_mandi_completed', 'weighbridge_events', ['mandi_id', 'completed_at'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'weighbridge_events' in existing_tables:
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('weighbridge_events')}
        if 'idx_weighbridge_events_mandi_completed' in existing_indexes:
            op.drop_index('idx_weighbridge_events_mandi_completed', table_name='weighbridge_events')
        if 'ix_weighbridge_events_completed_at' in existing_indexes:
            op.drop_index('ix_weighbridge_events_completed_at', table_name='weighbridge_events')
        if 'ix_weighbridge_events_transaction_id' in existing_indexes:
            op.drop_index('ix_weighbridge_events_transaction_id', table_name='weighbridge_events')
        if 'ix_weighbridge_events_mandi_id' in existing_indexes:
            op.drop_index('ix_weighbridge_events_mandi_id', table_name='weighbridge_events')
        if 'ix_weighbridge_events_event_id' in existing_indexes:
            op.drop_index('ix_weighbridge_events_event_id', table_name='weighbridge_events')
        op.drop_table('weighbridge_events')

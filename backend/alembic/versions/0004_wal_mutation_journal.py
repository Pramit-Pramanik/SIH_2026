"""0004_wal_mutation_journal

Revision ID: 0004_wal_mutation_journal
Revises: 0003_crop_master_schema
Create Date: 2026-09-20 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0004_wal_mutation_journal'
down_revision: Union[str, None] = '0003_crop_master_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'wal_mutation_journal',
        sa.Column('client_mutation_id', sa.String(length=64), nullable=False),
        sa.Column('transaction_id', sa.String(length=36), nullable=False),
        sa.Column('server_receive_sequence', sa.BigInteger(), nullable=False),
        sa.Column('current_state', sa.String(length=30), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('signature_type', sa.String(length=30), server_default='INTEGRITY_METADATA', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint('client_mutation_id')
    )
    op.create_index('ix_wal_mutation_journal_client_mutation_id', 'wal_mutation_journal', ['client_mutation_id'], unique=False)
    op.create_index('ix_wal_mutation_journal_transaction_id', 'wal_mutation_journal', ['transaction_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_wal_mutation_journal_transaction_id', table_name='wal_mutation_journal')
    op.drop_index('ix_wal_mutation_journal_client_mutation_id', table_name='wal_mutation_journal')
    op.drop_table('wal_mutation_journal')

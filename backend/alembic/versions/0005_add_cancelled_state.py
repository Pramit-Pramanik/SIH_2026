"""0005_add_cancelled_state

Revision ID: 0005_add_cancelled_state
Revises: 0004_wal_mutation_journal
Create Date: 2026-09-20 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0005_add_cancelled_state'
down_revision: Union[str, None] = '0004_wal_mutation_journal'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VALID_PROCUREMENT_STATES = (
    'SLOT_BOOKED',
    'GATE_ENTRY_VERIFIED',
    'IN_QA_QUEUE',
    'QUALITY_APPROVED',
    'QUALITY_REJECTED',
    'ROUTED_TO_WEIGHBRIDGE',
    'WEIGHED_GROSS',
    'WEIGHED_TARE',
    'BILL_GENERATED',
    'DBT_PAYMENT_INITIATED',
    'PAYMENT_SETTLED',
    'PAYMENT_FAILED',
    'CANCELLED'
)

PREVIOUS_PROCUREMENT_STATES = (
    'SLOT_BOOKED',
    'GATE_ENTRY_VERIFIED',
    'IN_QA_QUEUE',
    'QUALITY_APPROVED',
    'QUALITY_REJECTED',
    'ROUTED_TO_WEIGHBRIDGE',
    'WEIGHED_GROSS',
    'WEIGHED_TARE',
    'BILL_GENERATED',
    'DBT_PAYMENT_INITIATED',
    'PAYMENT_SETTLED',
    'PAYMENT_FAILED'
)


def upgrade() -> None:
    with op.batch_alter_table('procurement_logs') as batch_op:
        batch_op.drop_constraint('chk_procurement_state_valid', type_='check')
        batch_op.create_check_constraint(
            'chk_procurement_state_valid',
            f"current_state IN {tuple(VALID_PROCUREMENT_STATES)}"
        )


def downgrade() -> None:
    with op.batch_alter_table('procurement_logs') as batch_op:
        batch_op.drop_constraint('chk_procurement_state_valid', type_='check')
        batch_op.create_check_constraint(
            'chk_procurement_state_valid',
            f"current_state IN {tuple(PREVIOUS_PROCUREMENT_STATES)}"
        )

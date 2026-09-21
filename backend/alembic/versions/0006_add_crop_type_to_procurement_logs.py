"""0006_add_crop_type_to_procurement_logs

Revision ID: 0006_add_crop_type_to_procurement_logs
Revises: 0005_add_cancelled_state
Create Date: 2026-09-21 08:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0006_add_crop_type_to_procurement_logs'
down_revision: Union[str, None] = '0005_add_cancelled_state'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('procurement_logs') as batch_op:
        batch_op.add_column(
            sa.Column('crop_type', sa.String(length=100), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table('procurement_logs') as batch_op:
        batch_op.drop_column('crop_type')

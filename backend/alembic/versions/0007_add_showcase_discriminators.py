"""0007_add_showcase_discriminators

Revision ID: 0007_add_showcase_discriminators
Revises: 0006_add_crop_type_to_procurement_logs
Create Date: 2026-09-21 19:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0007_add_showcase_discriminators'
down_revision: Union[str, None] = '0006_add_crop_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('procurement_logs') as batch_op:
        batch_op.add_column(
            sa.Column('is_showcase', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column('demo_run_id', sa.String(length=64), nullable=True)
        )
        batch_op.create_index('ix_procurement_logs_is_showcase', ['is_showcase'], unique=False)
        batch_op.create_index('ix_procurement_logs_demo_run_id', ['demo_run_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('procurement_logs') as batch_op:
        batch_op.drop_index('ix_procurement_logs_demo_run_id')
        batch_op.drop_index('ix_procurement_logs_is_showcase')
        batch_op.drop_column('demo_run_id')
        batch_op.drop_column('is_showcase')

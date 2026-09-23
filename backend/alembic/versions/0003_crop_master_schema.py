"""0003_crop_master_schema

Revision ID: 0003_crop_master_schema
Revises: 0002_user_auth_schema
Create Date: 2026-09-15 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0003_crop_master_schema'
down_revision: Union[str, None] = '0002_user_auth_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'crops',
        sa.Column('crop_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('crop_name', sa.String(length=100), nullable=False),
        sa.Column('crop_code', sa.String(length=20), nullable=False),
        sa.Column('category', sa.String(length=50), server_default='CEREAL', nullable=False),
        sa.Column('msp_price_inr', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('optimal_moisture_pct', sa.Numeric(precision=4, scale=2), server_default='14.00', nullable=False),
        sa.Column('max_moisture_pct', sa.Numeric(precision=4, scale=2), server_default='17.00', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint('msp_price_inr > 0', name='chk_crop_msp_positive'),
        sa.CheckConstraint('optimal_moisture_pct > 0 AND optimal_moisture_pct <= 100', name='chk_crop_optimal_moisture'),
        sa.CheckConstraint('max_moisture_pct > 0 AND max_moisture_pct <= 100', name='chk_crop_max_moisture'),
        sa.CheckConstraint('optimal_moisture_pct <= max_moisture_pct', name='chk_crop_moisture_bounds'),
        sa.PrimaryKeyConstraint('crop_id'),
        sa.UniqueConstraint('crop_name', name='uq_crops_crop_name')
    )
    op.create_index('ix_crops_crop_id', 'crops', ['crop_id'], unique=False)
    op.create_index('ix_crops_crop_code', 'crops', ['crop_code'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_crops_crop_code', table_name='crops')
    op.drop_index('ix_crops_crop_id', table_name='crops')
    op.drop_table('crops')

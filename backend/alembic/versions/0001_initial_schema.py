"""0001_initial_schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-15 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
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
    'PAYMENT_FAILED'
)

def upgrade() -> None:
    # 1. mandis
    op.create_table(
        'mandis',
        sa.Column('mandi_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('district', sa.String(length=50), nullable=False),
        sa.Column('state', sa.String(length=50), nullable=False),
        sa.Column('daily_capacity_qt', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('active_weighbridges', sa.Integer(), server_default='2', nullable=False),
        sa.Column('is_operational', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint('daily_capacity_qt > 0', name='chk_mandi_daily_capacity'),
        sa.CheckConstraint('active_weighbridges >= 1', name='chk_mandi_active_weighbridges'),
        sa.PrimaryKeyConstraint('mandi_id')
    )
    op.create_index('ix_mandis_mandi_id', 'mandis', ['mandi_id'], unique=False)

    # 2. farmers
    op.create_table(
        'farmers',
        sa.Column('farmer_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('aadhaar_hash', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('mobile_number', sa.String(length=15), nullable=False),
        sa.Column('bank_account_hash', sa.String(length=64), nullable=False),
        sa.Column('ifsc_code', sa.String(length=11), nullable=False),
        sa.Column('land_area_hectares', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('registered_crop_type', sa.String(length=50), nullable=False),
        sa.Column('production_ceiling_qt', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint('land_area_hectares > 0', name='chk_farmer_land_area'),
        sa.CheckConstraint('production_ceiling_qt > 0', name='chk_farmer_production_ceiling'),
        sa.PrimaryKeyConstraint('farmer_id'),
        sa.UniqueConstraint('aadhaar_hash')
    )
    op.create_index('ix_farmers_farmer_id', 'farmers', ['farmer_id'], unique=False)
    op.create_index('idx_farmers_aadhaar', 'farmers', ['aadhaar_hash'], unique=False)

    # 3. procurement_slots
    op.create_table(
        'procurement_slots',
        sa.Column('slot_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('mandi_id', sa.Integer(), nullable=False),
        sa.Column('scheduled_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('allocated_capacity_qt', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('booked_capacity_qt', sa.Numeric(precision=10, scale=2), server_default='0.00', nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint('allocated_capacity_qt > 0', name='chk_slot_allocated_capacity'),
        sa.CheckConstraint('booked_capacity_qt >= 0', name='chk_slot_booked_non_negative'),
        sa.CheckConstraint('booked_capacity_qt <= allocated_capacity_qt', name='chk_slot_capacity'),
        sa.ForeignKeyConstraint(['mandi_id'], ['mandis.mandi_id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('slot_id')
    )
    op.create_index('ix_procurement_slots_slot_id', 'procurement_slots', ['slot_id'], unique=False)
    op.create_index('idx_slots_date_mandi', 'procurement_slots', ['mandi_id', 'scheduled_date'], unique=False)

    # 4. procurement_logs
    op.create_table(
        'procurement_logs',
        sa.Column('transaction_id', sa.String(length=36), nullable=False),
        sa.Column('farmer_id', sa.Integer(), nullable=False),
        sa.Column('mandi_id', sa.Integer(), nullable=False),
        sa.Column('slot_id', sa.Integer(), nullable=True),
        sa.Column('scheduled_date', sa.Date(), nullable=False),
        sa.Column('crop_moisture_pct', sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column('gross_weight_qt', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('tare_weight_qt', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('net_weight_qt', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('total_payout_inr', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('current_state', sa.String(length=30), nullable=False),
        sa.Column('token_signature', sa.String(length=64), nullable=False),
        sa.Column('payout_block_hash', sa.String(length=64), nullable=True),
        sa.Column('client_mutation_id', sa.String(length=36), nullable=True),
        sa.Column('server_receive_sequence', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint('crop_moisture_pct >= 0 AND crop_moisture_pct <= 100', name='chk_crop_moisture_range'),
        sa.CheckConstraint('gross_weight_qt >= 0', name='chk_gross_weight_non_negative'),
        sa.CheckConstraint('tare_weight_qt >= 0', name='chk_tare_weight_non_negative'),
        sa.CheckConstraint('net_weight_qt >= 0', name='chk_net_weight_non_negative'),
        sa.CheckConstraint('total_payout_inr >= 0', name='chk_total_payout_non_negative'),
        sa.CheckConstraint(
            f"current_state IN {tuple(VALID_PROCUREMENT_STATES)}",
            name='chk_procurement_state_valid'
        ),
        sa.ForeignKeyConstraint(['farmer_id'], ['farmers.farmer_id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['mandi_id'], ['mandis.mandi_id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['slot_id'], ['procurement_slots.slot_id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('transaction_id')
    )
    op.create_index('ix_procurement_logs_transaction_id', 'procurement_logs', ['transaction_id'], unique=False)
    op.create_index('idx_procurement_mandi_state', 'procurement_logs', ['mandi_id', 'current_state'], unique=False)
    op.create_index('idx_procurement_farmer', 'procurement_logs', ['farmer_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_procurement_farmer', table_name='procurement_logs')
    op.drop_index('idx_procurement_mandi_state', table_name='procurement_logs')
    op.drop_index('ix_procurement_logs_transaction_id', table_name='procurement_logs')
    op.drop_table('procurement_logs')

    op.drop_index('idx_slots_date_mandi', table_name='procurement_slots')
    op.drop_index('ix_procurement_slots_slot_id', table_name='procurement_slots')
    op.drop_table('procurement_slots')

    op.drop_index('idx_farmers_aadhaar', table_name='farmers')
    op.drop_index('ix_farmers_farmer_id', table_name='farmers')
    op.drop_table('farmers')

    op.drop_index('ix_mandis_mandi_id', table_name='mandis')
    op.drop_table('mandis')

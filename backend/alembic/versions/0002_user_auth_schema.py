"""0002_user_auth_schema

Revision ID: 0002_user_auth_schema
Revises: 0001_initial_schema
Create Date: 2026-09-15 14:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002_user_auth_schema'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VALID_USER_ROLES = (
    'ADMIN',
    'SUPERVISOR',
    'INSPECTOR',
    'OPERATOR',
    'FARMER'
)


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('user_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=False),
        sa.Column('role', sa.String(length=30), server_default='OPERATOR', nullable=False),
        sa.Column('mandi_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.ForeignKeyConstraint(['mandi_id'], ['mandis.mandi_id'], name='fk_users_mandi_id'),
        sa.PrimaryKeyConstraint('user_id'),
        sa.CheckConstraint(
            f"role IN {VALID_USER_ROLES}",
            name='chk_user_valid_role'
        )
    )
    op.create_index('ix_users_user_id', 'users', ['user_id'], unique=False)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_username', table_name='users')
    op.drop_index('ix_users_user_id', table_name='users')
    op.drop_table('users')

"""Add system_limits table

Revision ID: 20260222_0001
Revises: 20260220_0001
Create Date: 2026-02-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260222_0001'
down_revision = '20260220_0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'system_limits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_system_limits_key', 'system_limits', ['key'], unique=True)


def downgrade():
    op.drop_index('ix_system_limits_key', table_name='system_limits')
    op.drop_table('system_limits')

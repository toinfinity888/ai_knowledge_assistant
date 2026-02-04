"""Add audit_logs table

Revision ID: 20250129_0004
Revises: 20250129_0003
Create Date: 2025-01-29

Changes:
- Create audit_logs table for NIS2/ANSSI compliance
- Track all administrative actions for security audits
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = '20250129_0004'
down_revision = '20250129_0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        # Actor information (denormalized for persistence even if user deleted)
        sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('actor_email', sa.String(255), nullable=False),
        # Action details
        sa.Column('action_type', sa.String(50), nullable=False, index=True),
        sa.Column('target_type', sa.String(50), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=True),
        # Company scope (null for global/platform actions)
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='SET NULL'), nullable=True),
        # Additional details
        sa.Column('details', JSON, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        # Timestamp
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create composite index for company-scoped queries
    op.create_index(
        'ix_audit_logs_company_action',
        'audit_logs',
        ['company_id', 'action_type', 'created_at']
    )

    # Create index for actor queries
    op.create_index(
        'ix_audit_logs_actor',
        'audit_logs',
        ['actor_user_id', 'created_at']
    )


def downgrade():
    op.drop_index('ix_audit_logs_actor', table_name='audit_logs')
    op.drop_index('ix_audit_logs_company_action', table_name='audit_logs')
    op.drop_table('audit_logs')

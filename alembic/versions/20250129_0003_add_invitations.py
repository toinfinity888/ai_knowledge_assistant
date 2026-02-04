"""Add invitations table

Revision ID: 20250129_0003
Revises: 20250129_0002
Create Date: 2025-01-29

Changes:
- Create invitations table for token-based user onboarding
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250129_0003'
down_revision = '20250129_0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'invitations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(255), nullable=False, index=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=True),
        sa.Column('role', sa.Enum('super_admin', 'admin', 'agent', 'viewer', name='userrole', create_type=False), nullable=False),
        sa.Column('token', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_accepted', sa.Boolean(), default=False, nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index for looking up pending invitations by company
    op.create_index(
        'ix_invitations_company_pending',
        'invitations',
        ['company_id', 'is_accepted'],
        postgresql_where=sa.text('is_accepted = false')
    )

    # Add constraint: non-super_admin invitations MUST have company_id
    op.execute("""
        ALTER TABLE invitations
        ADD CONSTRAINT chk_invitation_company_required
        CHECK (role = 'super_admin' OR company_id IS NOT NULL)
    """)


def downgrade():
    op.execute("ALTER TABLE invitations DROP CONSTRAINT IF EXISTS chk_invitation_company_required")
    op.drop_index('ix_invitations_company_pending', table_name='invitations')
    op.drop_table('invitations')

"""Add SUPER_ADMIN role support

Revision ID: 20250129_0002
Revises: 20250128_0001
Create Date: 2025-01-29

Changes:
- Add 'super_admin' value to userrole enum
- Make users.company_id nullable (SUPER_ADMIN users have no company)
- Add check constraint: non-super_admin users must have company_id
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250129_0002'
down_revision = '20250128_0001'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add 'super_admin' to the userrole enum
    # PostgreSQL requires special handling for adding enum values
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'super_admin'")

    # 2. Make company_id nullable for SUPER_ADMIN users
    op.alter_column(
        'users',
        'company_id',
        existing_type=sa.Integer(),
        nullable=True
    )

    # 3. Add check constraint: non-super_admin users MUST have company_id
    # This ensures data integrity - only super_admins can have NULL company_id
    op.execute("""
        ALTER TABLE users
        ADD CONSTRAINT chk_company_required
        CHECK (role = 'super_admin' OR company_id IS NOT NULL)
    """)


def downgrade():
    # Remove check constraint
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_company_required")

    # Make company_id NOT NULL again
    # First, delete any super_admin users (they would violate the NOT NULL constraint)
    op.execute("DELETE FROM users WHERE role = 'super_admin'")

    op.alter_column(
        'users',
        'company_id',
        existing_type=sa.Integer(),
        nullable=False
    )

    # Note: PostgreSQL doesn't support removing enum values easily
    # The 'super_admin' value will remain in the enum but won't be used

"""add_domain_schema_registry

Revision ID: ceff2aa652aa
Revises: 20250129_0004
Create Date: 2026-02-04 14:50:02.690800

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ceff2aa652aa'
down_revision: Union[str, None] = '20250129_0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('domain_schemas',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('display_order', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_domain_schemas_company_id'), 'domain_schemas', ['company_id'], unique=False)
    op.create_index(op.f('ix_domain_schemas_slug'), 'domain_schemas', ['slug'], unique=False)
    op.create_table('domain_schema_fields',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('schema_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('field_type', sa.String(length=50), nullable=True),
    sa.Column('is_required', sa.Boolean(), nullable=False),
    sa.Column('options', sa.JSON(), nullable=True),
    sa.Column('display_order', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['schema_id'], ['domain_schemas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_domain_schema_fields_schema_id'), 'domain_schema_fields', ['schema_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_domain_schema_fields_schema_id'), table_name='domain_schema_fields')
    op.drop_table('domain_schema_fields')
    op.drop_index(op.f('ix_domain_schemas_slug'), table_name='domain_schemas')
    op.drop_index(op.f('ix_domain_schemas_company_id'), table_name='domain_schemas')
    op.drop_table('domain_schemas')

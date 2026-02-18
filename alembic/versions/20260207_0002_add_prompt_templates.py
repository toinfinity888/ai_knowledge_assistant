"""Add prompt_templates table

Revision ID: 20260207_0002
Revises: 20260207_0001
Create Date: 2026-02-07
"""
from alembic import op
import sqlalchemy as sa

revision = '20260207_0002'
down_revision = '20260207_0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'prompt_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('prompt_key', sa.String(100), nullable=False),
        sa.Column('language', sa.String(10), default='en'),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'prompt_key', 'language', name='uq_company_prompt_language')
    )
    op.create_index('ix_prompt_templates_company_id', 'prompt_templates', ['company_id'])
    op.create_index('ix_prompt_templates_prompt_key', 'prompt_templates', ['prompt_key'])


def downgrade():
    op.drop_index('ix_prompt_templates_prompt_key')
    op.drop_index('ix_prompt_templates_company_id')
    op.drop_table('prompt_templates')

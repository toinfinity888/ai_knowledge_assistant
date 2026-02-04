"""Add multi-tenancy support

Revision ID: 20250128_0001
Revises:
Create Date: 2025-01-28

This migration adds:
- companies table for organization/tenant management
- users table for authentication
- refresh_tokens table for JWT refresh tokens
- company_id foreign key to call_sessions
- agent_user_id foreign key to call_sessions
- company_id foreign key to query_logs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250128_0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create companies table
    op.create_table(
        'companies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('plan', sa.String(length=50), nullable=False, server_default='free'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('ix_companies_slug', 'companies', ['slug'], unique=True)

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.Enum('admin', 'agent', 'viewer', name='userrole'), nullable=False, server_default='agent'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_company_id', 'users', ['company_id'], unique=False)

    # Create refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('device_info', sa.String(length=500), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash')
    )
    op.create_index('ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'], unique=True)
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'], unique=False)

    # Add company_id and agent_user_id to call_sessions
    # First, add columns as nullable
    op.add_column('call_sessions', sa.Column('company_id', sa.Integer(), nullable=True))
    op.add_column('call_sessions', sa.Column('agent_user_id', sa.Integer(), nullable=True))

    # Add foreign key constraints
    op.create_foreign_key(
        'fk_call_sessions_company_id',
        'call_sessions', 'companies',
        ['company_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_call_sessions_agent_user_id',
        'call_sessions', 'users',
        ['agent_user_id'], ['id'],
        ondelete='SET NULL'
    )

    # Create index for company_id on call_sessions
    op.create_index('ix_call_sessions_company_id', 'call_sessions', ['company_id'], unique=False)
    op.create_index('ix_call_sessions_agent_user_id', 'call_sessions', ['agent_user_id'], unique=False)

    # Add company_id to query_logs (nullable for backward compatibility)
    op.add_column('query_logs', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_query_logs_company_id',
        'query_logs', 'companies',
        ['company_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_query_logs_company_id', 'query_logs', ['company_id'], unique=False)


def downgrade() -> None:
    # Remove company_id from query_logs
    op.drop_index('ix_query_logs_company_id', table_name='query_logs')
    op.drop_constraint('fk_query_logs_company_id', 'query_logs', type_='foreignkey')
    op.drop_column('query_logs', 'company_id')

    # Remove columns from call_sessions
    op.drop_index('ix_call_sessions_agent_user_id', table_name='call_sessions')
    op.drop_index('ix_call_sessions_company_id', table_name='call_sessions')
    op.drop_constraint('fk_call_sessions_agent_user_id', 'call_sessions', type_='foreignkey')
    op.drop_constraint('fk_call_sessions_company_id', 'call_sessions', type_='foreignkey')
    op.drop_column('call_sessions', 'agent_user_id')
    op.drop_column('call_sessions', 'company_id')

    # Drop refresh_tokens table
    op.drop_index('ix_refresh_tokens_user_id', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_token_hash', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')

    # Drop users table
    op.drop_index('ix_users_company_id', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')

    # Drop userrole enum
    op.execute('DROP TYPE IF EXISTS userrole')

    # Drop companies table
    op.drop_index('ix_companies_slug', table_name='companies')
    op.drop_table('companies')

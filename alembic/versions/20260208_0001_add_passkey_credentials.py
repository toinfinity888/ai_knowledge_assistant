"""Add passkey_credentials table for WebAuthn/Passkeys authentication

Revision ID: 20260208_0001
Revises: 20260207_0002
Create Date: 2026-02-08

Changes:
- Add passkey_credentials table for storing WebAuthn credentials
- Supports passwordless login with biometrics, security keys, and platform authenticators
"""
from alembic import op
import sqlalchemy as sa


revision = '20260208_0001'
down_revision = '20260207_0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'passkey_credentials',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('credential_id', sa.LargeBinary(), nullable=False),
        sa.Column('credential_id_b64', sa.String(255), nullable=False),
        sa.Column('public_key', sa.LargeBinary(), nullable=False),
        sa.Column('sign_count', sa.Integer(), default=0, nullable=False),
        sa.Column('device_name', sa.String(100), nullable=True),
        sa.Column('aaguid', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('credential_id'),
        sa.UniqueConstraint('credential_id_b64'),
    )
    op.create_index('ix_passkey_credentials_user_id', 'passkey_credentials', ['user_id'])
    op.create_index('ix_passkey_credentials_credential_id_b64', 'passkey_credentials', ['credential_id_b64'], unique=True)


def downgrade():
    op.drop_index('ix_passkey_credentials_credential_id_b64', table_name='passkey_credentials')
    op.drop_index('ix_passkey_credentials_user_id', table_name='passkey_credentials')
    op.drop_table('passkey_credentials')

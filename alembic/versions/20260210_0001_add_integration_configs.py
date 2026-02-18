"""Add integration_configs table for enterprise telephony integrations

Revision ID: 20260210_0001
Revises: 20260208_0001
Create Date: 2026-02-10

Changes:
- Add integration_configs table for storing per-tenant integration configurations
- Supports cloud webhooks (Aircall, Genesys, Talkdesk) and SIPREC (on-premise PBX)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision = '20260210_0001'
down_revision = '20260208_0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'integration_configs',
        # Primary key
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),

        # Integration identification
        sa.Column('integration_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),

        # Type and provider
        sa.Column('integration_type', sa.String(50), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),

        # Status
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_primary', sa.Boolean(), default=False, nullable=False),

        # Mode 1: Cloud Webhook Configuration
        sa.Column('webhook_secret', sa.String(255), nullable=True),
        sa.Column('webhook_url_suffix', sa.String(100), nullable=True),
        sa.Column('transcription_source', sa.String(50), default='provider_asr', nullable=True),

        # Mode 2: SIPREC Configuration
        sa.Column('siprec_port', sa.Integer(), nullable=True),
        sa.Column('siprec_transport', sa.String(10), default='udp', nullable=True),
        sa.Column('allowed_sources', JSON, default=list, nullable=True),
        sa.Column('srtp_enabled', sa.Boolean(), default=True, nullable=True),

        # Common Configuration
        sa.Column('credentials', JSON, default=dict, nullable=True),
        sa.Column('settings', JSON, default=dict, nullable=True),
        sa.Column('metadata_mapping', JSON, default=dict, nullable=True),
        sa.Column('audio_settings', JSON, default=dict, nullable=True),

        # Health Monitoring
        sa.Column('health_status', sa.String(50), default='unknown', nullable=True),
        sa.Column('last_health_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_event_received', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), default=0, nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),

        # Statistics
        sa.Column('total_calls_processed', sa.Integer(), default=0, nullable=True),
        sa.Column('total_events_received', sa.Integer(), default=0, nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),

        # Constraints
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Indexes
    op.create_index('ix_integration_configs_company_id', 'integration_configs', ['company_id'])
    op.create_index('ix_integration_configs_integration_id', 'integration_configs', ['integration_id'])
    op.create_index('ix_integration_configs_provider', 'integration_configs', ['provider'])
    op.create_index('ix_integration_configs_is_active', 'integration_configs', ['is_active'])

    # Unique constraint: integration_id must be unique per company
    op.create_unique_constraint(
        'uq_integration_configs_company_integration',
        'integration_configs',
        ['company_id', 'integration_id']
    )


def downgrade():
    op.drop_constraint('uq_integration_configs_company_integration', 'integration_configs', type_='unique')
    op.drop_index('ix_integration_configs_is_active', table_name='integration_configs')
    op.drop_index('ix_integration_configs_provider', table_name='integration_configs')
    op.drop_index('ix_integration_configs_integration_id', table_name='integration_configs')
    op.drop_index('ix_integration_configs_company_id', table_name='integration_configs')
    op.drop_table('integration_configs')

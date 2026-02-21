"""Add analytics tables for metrics tracking

Revision ID: 20260220_0001
Revises: 20260219_0001
Create Date: 2026-02-20

Changes:
- Add session_feedback table for star ratings and outcomes
- Add field_edit_logs table for tracking manual field corrections
- Add analytics_daily_summary table for pre-aggregated metrics
- Extend query_logs with session tracking columns
"""
from alembic import op
import sqlalchemy as sa


revision = '20260220_0001'
down_revision = '20260219_0001'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create session_feedback table
    op.create_table(
        'session_feedback',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),

        # Foreign keys
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('agent_user_id', sa.Integer(), nullable=True),

        # 5-star ratings (1-5, NULL if skipped)
        sa.Column('solution_rating', sa.Integer(), nullable=True),
        sa.Column('speech_recognition_rating', sa.Integer(), nullable=True),

        # Outcome tracking
        sa.Column('solution_found', sa.Boolean(), nullable=True),
        sa.Column('issue_resolved', sa.Boolean(), nullable=True),

        # Optional comments
        sa.Column('comments', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),

        # Constraints
        sa.ForeignKeyConstraint(['session_id'], ['call_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_session_feedback_session_id', 'session_feedback', ['session_id'])
    op.create_index('ix_session_feedback_company_id', 'session_feedback', ['company_id'])
    op.create_index('ix_session_feedback_agent_user_id', 'session_feedback', ['agent_user_id'])
    op.create_index('ix_session_feedback_created_at', 'session_feedback', ['created_at'])

    # 2. Create field_edit_logs table
    op.create_table(
        'field_edit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),

        # Foreign keys
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('agent_user_id', sa.Integer(), nullable=True),

        # Field information
        sa.Column('field_slug', sa.String(100), nullable=False),
        sa.Column('field_name', sa.String(255), nullable=True),

        # Edit tracking
        sa.Column('original_value', sa.Text(), nullable=True),
        sa.Column('edited_value', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('edited_at', sa.DateTime(timezone=True), nullable=False),

        # Constraints
        sa.ForeignKeyConstraint(['session_id'], ['call_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_field_edit_logs_session_id', 'field_edit_logs', ['session_id'])
    op.create_index('ix_field_edit_logs_company_id', 'field_edit_logs', ['company_id'])
    op.create_index('ix_field_edit_logs_agent_user_id', 'field_edit_logs', ['agent_user_id'])
    op.create_index('ix_field_edit_logs_field_slug', 'field_edit_logs', ['field_slug'])

    # 3. Create analytics_daily_summary table
    op.create_table(
        'analytics_daily_summary',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),

        # Scope
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('agent_user_id', sa.Integer(), nullable=True),  # NULL = company total

        # Session counts
        sa.Column('total_sessions', sa.Integer(), default=0),
        sa.Column('sessions_with_feedback', sa.Integer(), default=0),

        # Search metrics
        sa.Column('total_searches', sa.Integer(), default=0),
        sa.Column('zero_result_searches', sa.Integer(), default=0),

        # Field edit metrics
        sa.Column('total_field_edits', sa.Integer(), default=0),

        # Outcome metrics
        sa.Column('solutions_found', sa.Integer(), default=0),
        sa.Column('issues_resolved', sa.Integer(), default=0),

        # Rating sums (for averaging)
        sa.Column('solution_rating_sum', sa.Integer(), default=0),
        sa.Column('solution_rating_count', sa.Integer(), default=0),
        sa.Column('speech_rating_sum', sa.Integer(), default=0),
        sa.Column('speech_rating_count', sa.Integer(), default=0),

        # Time metrics (in milliseconds)
        sa.Column('total_session_duration_ms', sa.BigInteger(), default=0),
        sa.Column('total_response_time_ms', sa.BigInteger(), default=0),
        sa.Column('response_time_count', sa.Integer(), default=0),

        # Suggestion metrics
        sa.Column('suggestions_shown', sa.Integer(), default=0),
        sa.Column('suggestions_clicked', sa.Integer(), default=0),
        sa.Column('suggestions_helpful', sa.Integer(), default=0),
        sa.Column('suggestions_not_helpful', sa.Integer(), default=0),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),

        # Constraints
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date', 'company_id', 'agent_user_id', name='uix_daily_summary'),
    )
    op.create_index('ix_analytics_daily_summary_date', 'analytics_daily_summary', ['date'])
    op.create_index('ix_analytics_daily_summary_company_id', 'analytics_daily_summary', ['company_id'])
    op.create_index('ix_analytics_daily_summary_agent_user_id', 'analytics_daily_summary', ['agent_user_id'])

    # 4. Extend query_logs with session tracking columns
    op.add_column('query_logs', sa.Column('session_id', sa.Integer(), nullable=True))
    op.add_column('query_logs', sa.Column('agent_user_id', sa.Integer(), nullable=True))
    op.add_column('query_logs', sa.Column('search_type', sa.String(50), nullable=True))

    op.create_foreign_key(
        'fk_query_logs_session_id',
        'query_logs', 'call_sessions',
        ['session_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_query_logs_agent_user_id',
        'query_logs', 'users',
        ['agent_user_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_query_logs_session_id', 'query_logs', ['session_id'])
    op.create_index('ix_query_logs_agent_user_id', 'query_logs', ['agent_user_id'])


def downgrade():
    # Remove query_logs extensions
    op.drop_index('ix_query_logs_agent_user_id', table_name='query_logs')
    op.drop_index('ix_query_logs_session_id', table_name='query_logs')
    op.drop_constraint('fk_query_logs_agent_user_id', 'query_logs', type_='foreignkey')
    op.drop_constraint('fk_query_logs_session_id', 'query_logs', type_='foreignkey')
    op.drop_column('query_logs', 'search_type')
    op.drop_column('query_logs', 'agent_user_id')
    op.drop_column('query_logs', 'session_id')

    # Drop analytics_daily_summary
    op.drop_index('ix_analytics_daily_summary_agent_user_id', table_name='analytics_daily_summary')
    op.drop_index('ix_analytics_daily_summary_company_id', table_name='analytics_daily_summary')
    op.drop_index('ix_analytics_daily_summary_date', table_name='analytics_daily_summary')
    op.drop_table('analytics_daily_summary')

    # Drop field_edit_logs
    op.drop_index('ix_field_edit_logs_field_slug', table_name='field_edit_logs')
    op.drop_index('ix_field_edit_logs_agent_user_id', table_name='field_edit_logs')
    op.drop_index('ix_field_edit_logs_company_id', table_name='field_edit_logs')
    op.drop_index('ix_field_edit_logs_session_id', table_name='field_edit_logs')
    op.drop_table('field_edit_logs')

    # Drop session_feedback
    op.drop_index('ix_session_feedback_created_at', table_name='session_feedback')
    op.drop_index('ix_session_feedback_agent_user_id', table_name='session_feedback')
    op.drop_index('ix_session_feedback_company_id', table_name='session_feedback')
    op.drop_index('ix_session_feedback_session_id', table_name='session_feedback')
    op.drop_table('session_feedback')

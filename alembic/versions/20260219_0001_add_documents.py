"""Add documents table for PDF knowledge base management

Revision ID: 20260219_0001
Revises: 20260210_0001
Create Date: 2026-02-19

Changes:
- Add documents table for tracking uploaded PDFs
- Documents are parsed, chunked, and stored as vectors in Qdrant
- Each document belongs to a company for multi-tenant isolation
"""
from alembic import op
import sqlalchemy as sa


revision = '20260219_0001'
down_revision = '20260210_0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'documents',
        # Primary key
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),

        # Company isolation (multi-tenancy)
        sa.Column('company_id', sa.Integer(), nullable=False),

        # File metadata
        sa.Column('filename', sa.String(255), nullable=False),  # Stored name (UUID-based)
        sa.Column('original_filename', sa.String(255), nullable=False),  # User's original filename
        sa.Column('file_size', sa.Integer(), nullable=False),  # Size in bytes
        sa.Column('mime_type', sa.String(100), default='application/pdf'),

        # Processing status
        sa.Column('status', sa.String(20), default='pending', nullable=False),
        sa.Column('chunk_count', sa.Integer(), default=0),
        sa.Column('error_message', sa.Text(), nullable=True),

        # Audit
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),

        # Constraints
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Indexes
    op.create_index('ix_documents_company_id', 'documents', ['company_id'])
    op.create_index('ix_documents_status', 'documents', ['status'])
    op.create_index('ix_documents_created_at', 'documents', ['created_at'])


def downgrade():
    op.drop_index('ix_documents_created_at', table_name='documents')
    op.drop_index('ix_documents_status', table_name='documents')
    op.drop_index('ix_documents_company_id', table_name='documents')
    op.drop_table('documents')

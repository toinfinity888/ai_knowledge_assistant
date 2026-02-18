"""Add source_metadata column to suggestions table

Revision ID: 20260207_0001
Revises: ceff2aa652aa
Create Date: 2026-02-07

Changes:
- Add source_metadata JSON column to suggestions table for RAG provenance
- Stores file names, pages, and similarity scores for each source document
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = '20260207_0001'
down_revision = 'ceff2aa652aa'
branch_labels = None
depends_on = None


def upgrade():
    # Add source_metadata column to suggestions table
    op.add_column(
        'suggestions',
        sa.Column('source_metadata', JSON, server_default='[]', nullable=True)
    )


def downgrade():
    op.drop_column('suggestions', 'source_metadata')

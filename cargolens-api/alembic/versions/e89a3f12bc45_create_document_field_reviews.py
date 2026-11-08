"""create_document_field_reviews

Revision ID: e89a3f12bc45
Revises: 93172d2d23d6
Create Date: 2026-11-04 20:51:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e89a3f12bc45'
down_revision: Union[str, None] = '93172d2d23d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create enum safely
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'field_review_action_enum') THEN
                CREATE TYPE field_review_action_enum AS ENUM ('CONFIRMED', 'CORRECTED');
            END IF;
        END $$;
        """
    )

    action_enum = postgresql.ENUM('CONFIRMED', 'CORRECTED', name='field_review_action_enum', create_type=False)

    # 2. Create document_field_reviews table
    op.create_table(
        'document_field_reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('shipment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('shipments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('extraction_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('structured_extractions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('action', action_enum, nullable=False),
        sa.Column('original_value', sa.Text(), nullable=True),
        sa.Column('corrected_value', sa.Text(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('reviewer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    op.create_index('ix_document_field_reviews_shipment_id', 'document_field_reviews', ['shipment_id'])
    op.create_index('ix_document_field_reviews_document_id', 'document_field_reviews', ['document_id'])
    op.create_index('ix_document_field_reviews_extraction_id', 'document_field_reviews', ['extraction_id'])
    op.create_index('ix_document_field_reviews_field_name', 'document_field_reviews', ['field_name'])
    op.create_index('ix_document_field_reviews_action', 'document_field_reviews', ['action'])
    op.create_index('ix_document_field_reviews_reviewer_id', 'document_field_reviews', ['reviewer_id'])
    op.create_index('ix_document_field_reviews_created_at', 'document_field_reviews', ['created_at'])
    op.create_index('ix_field_reviews_doc_field_created', 'document_field_reviews', ['document_id', 'field_name', 'created_at'])


def downgrade() -> None:
    op.drop_table('document_field_reviews')
    op.execute("DROP TYPE IF EXISTS field_review_action_enum;")

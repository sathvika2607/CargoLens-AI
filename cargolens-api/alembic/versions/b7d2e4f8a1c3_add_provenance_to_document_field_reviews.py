"""add_provenance_to_document_field_reviews

Revision ID: b7d2e4f8a1c3
Revises: f9b3c5e7d1a2
Create Date: 2026-11-06 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b7d2e4f8a1c3'
down_revision: Union[str, None] = 'f9b3c5e7d1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create review_provenance_enum safely
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'review_provenance_enum') THEN
                CREATE TYPE review_provenance_enum AS ENUM ('USER_ACTION', 'DEMO_SEED');
            END IF;
        END $$;
        """
    )

    provenance_enum = postgresql.ENUM('USER_ACTION', 'DEMO_SEED', name='review_provenance_enum', create_type=False)

    # 2. Add column with default USER_ACTION
    op.add_column(
        'document_field_reviews',
        sa.Column('provenance', provenance_enum, server_default=sa.text("'USER_ACTION'"), nullable=False),
    )
    op.create_index('ix_document_field_reviews_provenance', 'document_field_reviews', ['provenance'])

    # 3. Data migration: mark seeded demonstration review records belonging to SHP-24816 and SHP-24817 as DEMO_SEED
    op.execute(
        """
        UPDATE document_field_reviews
        SET provenance = 'DEMO_SEED'
        WHERE shipment_id IN (
            SELECT id FROM shipments WHERE shipment_number IN ('SHP-24816', 'SHP-24817')
        );
        """
    )


def downgrade() -> None:
    op.drop_index('ix_document_field_reviews_provenance', table_name='document_field_reviews')
    op.drop_column('document_field_reviews', 'provenance')
    op.execute("DROP TYPE IF EXISTS review_provenance_enum;")

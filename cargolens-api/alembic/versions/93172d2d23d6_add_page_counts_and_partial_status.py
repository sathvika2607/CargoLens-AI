"""add_page_counts_and_partial_status

Revision ID: 93172d2d23d6
Revises: 15aada95461f
Create Date: 2026-11-04 20:00:16.124751

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93172d2d23d6'
down_revision: Union[str, None] = '15aada95461f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add PARTIAL value to extraction_status_enum if not already present
    op.execute("ALTER TYPE extraction_status_enum ADD VALUE IF NOT EXISTS 'PARTIAL'")

    # 2. Add page count columns to structured_extractions
    op.add_column(
        'structured_extractions',
        sa.Column('total_page_count', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'structured_extractions',
        sa.Column('processed_page_count', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('structured_extractions', 'processed_page_count')
    op.drop_column('structured_extractions', 'total_page_count')

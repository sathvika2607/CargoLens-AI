"""add_is_demo_to_shipments

Revision ID: f9b3c5e7d1a2
Revises: e5a1b3c9d7f2
Create Date: 2026-11-05 22:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9b3c5e7d1a2'
down_revision: Union[str, None] = 'e5a1b3c9d7f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'shipments',
        sa.Column('is_demo', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
    op.create_index('ix_shipments_is_demo', 'shipments', ['is_demo'])
    # Backfill is_demo for existing synthetic demonstration consignments
    op.execute(
        "UPDATE shipments SET is_demo = TRUE WHERE client_name ILIKE '%[DEMO]%' OR shipment_number LIKE 'SHP-DEMO-%' OR shipment_number LIKE 'SHP-2481%'"
    )


def downgrade() -> None:
    op.drop_index('ix_shipments_is_demo', table_name='shipments')
    op.drop_column('shipments', 'is_demo')

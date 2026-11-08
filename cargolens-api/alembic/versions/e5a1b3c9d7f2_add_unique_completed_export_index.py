"""add_unique_completed_export_index

Revision ID: e5a1b3c9d7f2
Revises: c1f93018e472
Create Date: 2026-11-05 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5a1b3c9d7f2'
down_revision: Union[str, None] = 'c1f93018e472'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'uq_completed_export_per_shipment',
        'shipment_export_records',
        ['shipment_id'],
        unique=True,
        postgresql_where=sa.text("export_status = 'COMPLETED'"),
    )


def downgrade() -> None:
    op.drop_index(
        'uq_completed_export_per_shipment',
        table_name='shipment_export_records',
    )

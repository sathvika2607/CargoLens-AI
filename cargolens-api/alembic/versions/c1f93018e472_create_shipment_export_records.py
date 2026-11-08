"""create_shipment_export_records

Revision ID: c1f93018e472
Revises: e89a3f12bc45
Create Date: 2026-11-05 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c1f93018e472'
down_revision: Union[str, None] = 'e89a3f12bc45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create export_status_enum safely
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'export_status_enum') THEN
                CREATE TYPE export_status_enum AS ENUM ('COMPLETED', 'FAILED');
            END IF;
        END $$;
        """
    )

    export_status_enum = postgresql.ENUM('COMPLETED', 'FAILED', name='export_status_enum', create_type=False)

    # 2. Create shipment_export_records table
    op.create_table(
        'shipment_export_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('shipment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('shipments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('exported_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('template_name', sa.String(length=100), nullable=False, server_default='STANDARD_CUSTOMS_CLEARANCE'),
        sa.Column('template_version', sa.String(length=20), nullable=False, server_default='1.0'),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('sha256_checksum', sa.String(length=64), nullable=False),
        sa.Column('export_status', export_status_enum, nullable=False, server_default='COMPLETED'),
        sa.Column('row_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('snapshot_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('exported_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # 3. Create indices
    op.create_index('ix_shipment_export_records_shipment_id', 'shipment_export_records', ['shipment_id'])
    op.create_index('ix_shipment_export_records_exported_by', 'shipment_export_records', ['exported_by'])
    op.create_index('ix_shipment_export_records_sha256_checksum', 'shipment_export_records', ['sha256_checksum'])
    op.create_index('ix_shipment_export_records_export_status', 'shipment_export_records', ['export_status'])
    op.create_index('ix_shipment_export_records_exported_at', 'shipment_export_records', ['exported_at'])
    op.create_index('ix_shipment_exports_shipment_at', 'shipment_export_records', ['shipment_id', 'exported_at'])


def downgrade() -> None:
    op.drop_index('ix_shipment_exports_shipment_at', table_name='shipment_export_records')
    op.drop_index('ix_shipment_export_records_exported_at', table_name='shipment_export_records')
    op.drop_index('ix_shipment_export_records_export_status', table_name='shipment_export_records')
    op.drop_index('ix_shipment_export_records_sha256_checksum', table_name='shipment_export_records')
    op.drop_index('ix_shipment_export_records_exported_by', table_name='shipment_export_records')
    op.drop_index('ix_shipment_export_records_shipment_id', table_name='shipment_export_records')
    op.drop_table('shipment_export_records')
    op.execute("DROP TYPE IF EXISTS export_status_enum;")

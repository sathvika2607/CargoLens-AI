"""create_structured_extractions_and_validations

Revision ID: 15aada95461f
Revises: b81cf78118bb
Create Date: 2026-11-04 19:10:16.285913

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '15aada95461f'
down_revision: Union[str, None] = 'b81cf78118bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new enums safely if they don't already exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE validation_severity_enum AS ENUM ('ERROR', 'WARNING', 'INFO');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE validation_outcome_enum AS ENUM ('PASS', 'FAIL', 'MISSING_DATA', 'NOT_APPLICABLE', 'INFO');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Enum references with create_type=False so table creation never attempts duplicate type creation
    document_type_enum = postgresql.ENUM('COMMERCIAL_INVOICE', 'PACKING_LIST', 'BILL_OF_LADING', name='document_type_enum', create_type=False)
    extraction_status_enum = postgresql.ENUM('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', name='extraction_status_enum', create_type=False)
    validation_severity_enum = postgresql.ENUM('ERROR', 'WARNING', 'INFO', name='validation_severity_enum', create_type=False)
    validation_outcome_enum = postgresql.ENUM('PASS', 'FAIL', 'MISSING_DATA', 'NOT_APPLICABLE', 'INFO', name='validation_outcome_enum', create_type=False)

    op.create_table('shipment_validation_results',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('shipment_id', sa.UUID(), nullable=False),
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('rule_id', sa.String(length=100), nullable=False),
        sa.Column('rule_name', sa.String(length=200), nullable=False),
        sa.Column('severity', validation_severity_enum, nullable=False),
        sa.Column('outcome', validation_outcome_enum, nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('compared_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('source_document_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_shipment_validation_results_created_at'), 'shipment_validation_results', ['created_at'], unique=False)
    op.create_index(op.f('ix_shipment_validation_results_outcome'), 'shipment_validation_results', ['outcome'], unique=False)
    op.create_index(op.f('ix_shipment_validation_results_rule_id'), 'shipment_validation_results', ['rule_id'], unique=False)
    op.create_index(op.f('ix_shipment_validation_results_run_id'), 'shipment_validation_results', ['run_id'], unique=False)
    op.create_index(op.f('ix_shipment_validation_results_shipment_id'), 'shipment_validation_results', ['shipment_id'], unique=False)
    op.create_index('ix_validation_results_shipment_created', 'shipment_validation_results', ['shipment_id', 'created_at'], unique=False)
    op.create_index('ix_validation_results_shipment_run', 'shipment_validation_results', ['shipment_id', 'run_id'], unique=False)

    op.create_table('structured_extractions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('document_type', document_type_enum, nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('status', extraction_status_enum, nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('extraction_mode', sa.String(length=30), nullable=False),
        sa.Column('extracted_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('field_confidence_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('raw_response_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', 'attempt_number', name='uq_structured_extraction_attempt')
    )
    op.create_index('ix_structured_extractions_doc_attempt', 'structured_extractions', ['document_id', 'attempt_number'], unique=False)
    op.create_index(op.f('ix_structured_extractions_document_id'), 'structured_extractions', ['document_id'], unique=False)
    op.create_index(op.f('ix_structured_extractions_document_type'), 'structured_extractions', ['document_type'], unique=False)
    op.create_index(op.f('ix_structured_extractions_status'), 'structured_extractions', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_structured_extractions_status'), table_name='structured_extractions')
    op.drop_index(op.f('ix_structured_extractions_document_type'), table_name='structured_extractions')
    op.drop_index(op.f('ix_structured_extractions_document_id'), table_name='structured_extractions')
    op.drop_index('ix_structured_extractions_doc_attempt', table_name='structured_extractions')
    op.drop_table('structured_extractions')

    op.drop_index('ix_validation_results_shipment_run', table_name='shipment_validation_results')
    op.drop_index('ix_validation_results_shipment_created', table_name='shipment_validation_results')
    op.drop_index(op.f('ix_shipment_validation_results_shipment_id'), table_name='shipment_validation_results')
    op.drop_index(op.f('ix_shipment_validation_results_run_id'), table_name='shipment_validation_results')
    op.drop_index(op.f('ix_shipment_validation_results_rule_id'), table_name='shipment_validation_results')
    op.drop_index(op.f('ix_shipment_validation_results_outcome'), table_name='shipment_validation_results')
    op.drop_index(op.f('ix_shipment_validation_results_created_at'), table_name='shipment_validation_results')
    op.drop_table('shipment_validation_results')

    op.execute("DROP TYPE IF EXISTS validation_outcome_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS validation_severity_enum CASCADE")

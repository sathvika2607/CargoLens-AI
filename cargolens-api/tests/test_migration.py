import pytest
from sqlalchemy import text
from app.database import async_engine


@pytest.mark.asyncio
async def test_migration_tables_exist():
    """Verifies that all tables created by the initial migration exist in PostgreSQL."""
    async with async_engine.connect() as conn:
        res = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name;"
            )
        )
        tables = [row[0] for row in res.fetchall()]

    assert "alembic_version" in tables
    assert "users" in tables
    assert "refresh_tokens" in tables
    assert "shipments" in tables
    assert "documents" in tables
    assert "processing_jobs" in tables
    assert "document_extractions" in tables
    assert "document_extraction_pages" in tables
    assert "structured_extractions" in tables
    assert "shipment_validation_results" in tables
    assert "document_field_reviews" in tables
    assert "shipment_export_records" in tables


@pytest.mark.asyncio
async def test_shipments_table_columns_and_constraints():
    """Verifies that the shipments table has the expected columns and check constraints."""
    async with async_engine.connect() as conn:
        # Check columns
        res = await conn.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'shipments' ORDER BY column_name;"
            )
        )
        columns = {row[0]: row[1] for row in res.fetchall()}

        assert "id" in columns
        assert "shipment_number" in columns
        assert "client_name" in columns
        assert "origin_country" in columns
        assert "quantity" in columns
        assert "unit_price" in columns
        assert "gross_weight_kg" in columns
        assert "status" in columns
        assert "created_by" in columns

        # Check check constraints
        chk_res = await conn.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'shipments'::regclass AND contype = 'c';"
            )
        )
        constraints = [row[0] for row in chk_res.fetchall()]

        assert "chk_positive_quantity" in constraints
        assert "chk_positive_unit_price" in constraints
        assert "chk_positive_gross_weight" in constraints


@pytest.mark.asyncio
async def test_documents_and_jobs_table_columns_and_constraints():
    """Verifies that documents and processing_jobs tables have expected columns and check constraints."""
    async with async_engine.connect() as conn:
        # Check documents columns
        doc_cols_res = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'documents';"
            )
        )
        doc_cols = {row[0] for row in doc_cols_res.fetchall()}
        for expected_col in (
            "id",
            "shipment_id",
            "document_type",
            "original_filename",
            "storage_key",
            "mime_type",
            "file_extension",
            "file_size_bytes",
            "sha256_checksum",
            "version",
            "uploaded_by",
            "processing_status",
            "is_active",
        ):
            assert expected_col in doc_cols

        # Check documents constraints
        doc_chk_res = await conn.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'documents'::regclass AND contype = 'c';"
            )
        )
        doc_constraints = [row[0] for row in doc_chk_res.fetchall()]
        assert "chk_positive_file_size" in doc_constraints
        assert "chk_positive_document_version" in doc_constraints

        # Check documents unique constraints
        doc_u_res = await conn.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'documents'::regclass AND contype = 'u';"
            )
        )
        doc_u_constraints = [row[0] for row in doc_u_res.fetchall()]
        assert "uq_documents_shipment_checksum" in doc_u_constraints
        assert "uq_documents_shipment_type_version" in doc_u_constraints

        # Check processing_jobs columns
        job_cols_res = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'processing_jobs';"
            )
        )
        job_cols = {row[0] for row in job_cols_res.fetchall()}
        for expected_col in (
            "id",
            "document_id",
            "job_type",
            "status",
            "attempt_count",
            "max_attempts",
            "created_at",
            "lease_expires_at",
            "lease_token",
        ):
            assert expected_col in job_cols

        # Check processing_jobs constraints
        job_chk_res = await conn.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'processing_jobs'::regclass AND contype = 'c';"
            )
        )
        job_constraints = [row[0] for row in job_chk_res.fetchall()]
        assert "chk_positive_job_attempt_count" in job_constraints


@pytest.mark.asyncio
async def test_document_extractions_table_columns_and_constraints():
    """Verifies that document_extractions and document_extraction_pages tables have expected columns and unique constraints."""
    async with async_engine.connect() as conn:
        # Check document_extractions columns
        ext_cols_res = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'document_extractions';"
            )
        )
        ext_cols = {row[0] for row in ext_cols_res.fetchall()}
        for expected_col in (
            "id",
            "document_id",
            "attempt_number",
            "status",
            "extraction_method",
            "raw_text",
            "page_count",
            "processed_page_count",
            "failed_page_count",
            "avg_confidence",
            "character_count",
            "quality_status",
            "error_summary",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ):
            assert expected_col in ext_cols

        # Check unique constraint on document_extractions
        ext_u_res = await conn.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'document_extractions'::regclass AND contype = 'u';"
            )
        )
        ext_u_constraints = [row[0] for row in ext_u_res.fetchall()]
        assert "uq_document_extraction_attempt" in ext_u_constraints

        # Check document_extraction_pages columns
        page_cols_res = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'document_extraction_pages';"
            )
        )
        page_cols = {row[0] for row in page_cols_res.fetchall()}
        for expected_col in (
            "id",
            "extraction_id",
            "page_number",
            "extraction_method",
            "raw_text",
            "ocr_confidence",
            "character_count",
            "processing_status",
            "error_message",
            "created_at",
        ):
            assert expected_col in page_cols

        # Check unique constraint on document_extraction_pages
        page_u_res = await conn.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'document_extraction_pages'::regclass AND contype = 'u';"
            )
        )
        page_u_constraints = [row[0] for row in page_u_res.fetchall()]
        assert "uq_extraction_page_number" in page_u_constraints


@pytest.mark.asyncio
async def test_structured_extractions_and_validations_columns_and_constraints():
    """Verifies that structured_extractions and shipment_validation_results tables have expected schema."""
    async with async_engine.connect() as conn:
        # Check structured_extractions columns
        se_cols_res = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'structured_extractions';"
            )
        )
        se_cols = {row[0] for row in se_cols_res.fetchall()}
        for expected_col in (
            "id",
            "document_id",
            "document_type",
            "attempt_number",
            "status",
            "provider",
            "model",
            "extraction_mode",
            "total_page_count",
            "processed_page_count",
            "extracted_data",
            "field_confidence_summary",
            "raw_response_metadata",
            "error_summary",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ):
            assert expected_col in se_cols

        # Check unique constraint on structured_extractions (document_id, attempt_number)
        se_u_res = await conn.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'structured_extractions'::regclass AND contype = 'u';"
            )
        )
        se_u_constraints = [row[0] for row in se_u_res.fetchall()]
        assert "uq_structured_extraction_attempt" in se_u_constraints

        # Check shipment_validation_results columns
        vr_cols_res = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'shipment_validation_results';"
            )
        )
        vr_cols = {row[0] for row in vr_cols_res.fetchall()}
        for expected_col in (
            "id",
            "shipment_id",
            "run_id",
            "rule_id",
            "rule_name",
            "severity",
            "outcome",
            "explanation",
            "compared_values",
            "source_document_ids",
            "created_at",
        ):
            assert expected_col in vr_cols

        # Check document_field_reviews columns
        dfr_cols_res = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'document_field_reviews';"
            )
        )
        dfr_cols = {row[0] for row in dfr_cols_res.fetchall()}
        for expected_col in (
            "id",
            "shipment_id",
            "document_id",
            "extraction_id",
            "field_name",
            "action",
            "original_value",
            "corrected_value",
            "reason",
            "reviewer_id",
            "created_at",
        ):
            assert expected_col in dfr_cols


@pytest.mark.asyncio
async def test_shipment_export_records_columns_and_constraints():
    """Verifies that shipment_export_records table has expected columns and unique completed export index."""
    async with async_engine.connect() as conn:
        res = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'shipment_export_records';"
            )
        )
        cols = {row[0] for row in res.fetchall()}
        for expected_col in (
            "id",
            "shipment_id",
            "exported_by",
            "template_name",
            "template_version",
            "filename",
            "sha256_checksum",
            "export_status",
            "row_count",
            "file_size_bytes",
            "error_message",
            "snapshot_data",
            "exported_at",
        ):
            assert expected_col in cols

        # Check unique partial index for completed exports
        idx_res = await conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'shipment_export_records';"
            )
        )
        indexes = {row[0] for row in idx_res.fetchall()}
        assert "uq_completed_export_per_shipment" in indexes

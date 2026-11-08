import hashlib
import io
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple

import pymupdf
from sqlalchemy import select, delete, update, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.export import ShipmentExportRecord, ExportStatus
from app.models.extraction import ExtractionStatus
from app.models.field_review import DocumentFieldReview, FieldReviewActionType
from app.models.processing_job import ProcessingJob, JobStatus
from app.models.shipment import Shipment, ShipmentStatus
from app.models.structured_extraction import StructuredExtraction
from app.models.user import User, UserRole
from app.models.validation import ShipmentValidationResult, ValidationOutcome
from app.services.ai.base import BaseExtractionProvider, ProviderConfigurationError
from app.services.ai.claude_provider import ClaudeVisionExtractionProvider
from app.services.ai.fixture_provider import DeterministicFixtureExtractionProvider
from app.services.ai.service import StructuredExtractionService
from app.services.export.csv_exporter import CSVExportService, ExportTemplateType
from app.services.job_worker import JobWorkerService
from app.services.ocr.pipeline import OcrPipeline
from app.services.validation.engine import CrossDocumentValidationEngine
from app.storage import get_storage_service

logger = logging.getLogger("cargolens.simulation")


from app.services.documents.pdf_generator import create_synthetic_pdf, TradePdfGenerator


SCENARIOS_CATALOG = [
    {
        "id": "A",
        "code": "COMPLETE_WORKFLOW",
        "name": "Scenario A: Complete Consignment Triad (Awaiting Human Review)",
        "shipment_number": "SHP-DEMO-001",
        "client_name": "Apex Solar Technologies India [DEMO]",
        "description": "Full triad of Commercial Invoice, Packing List, and Bill of Lading with consistent weights (14,400 kg) and values. Passes all 11 cross-document validation rules and halts at REVIEW_REQUIRED for genuine executive/manager review (13 document-specific mandatory field reviews required across triad), verification, and export.",
        "expected_status": "REVIEW_REQUIRED",
        "expected_validation_outcome": "11/11 Rules Passed (Clean — Awaiting Human Review)",
        "triad_documents": ["Commercial Invoice", "Packing List", "Bill of Lading"],
    },
    {
        "id": "B",
        "code": "WEIGHT_DISCREPANCY",
        "name": "Scenario B: 45 kg Gross Weight Discrepancy",
        "shipment_number": "SHP-24811",
        "client_name": "Lumileds Global Trading [DEMO]",
        "description": "Commercial Invoice declares 3,120.00 kg while Packing List declares 3,165.00 kg. Validation engine identifies the exact 45.00 kg discrepancy, blocking premature verification.",
        "expected_status": "REVIEW_REQUIRED",
        "expected_validation_outcome": "GrossWeightConsistencyRule Failed (45.00 kg Mismatch)",
        "triad_documents": ["Commercial Invoice", "Packing List", "Bill of Lading"],
    },
    {
        "id": "C",
        "code": "MISSING_FINANCIAL",
        "name": "Scenario C: Missing Financial Information",
        "shipment_number": "SHP-24812",
        "client_name": "Klinger Fluid Control [DEMO]",
        "description": "180 units @ EUR 42.50 with omitted grand total. Platform computes EUR 7,650 for guidance but strictly refrains from fabricating it as the extracted total.",
        "expected_status": "REVIEW_REQUIRED",
        "expected_validation_outcome": "InvoiceArithmeticRule Failed (Grand Total Missing)",
        "triad_documents": ["Commercial Invoice", "Packing List", "Bill of Lading"],
    },
    {
        "id": "D",
        "code": "LOW_CONFIDENCE",
        "name": "Scenario D: Low-Confidence Field Review",
        "shipment_number": "SHP-DEMO-LOWCONF",
        "client_name": "Rotork Controls International [DEMO]",
        "description": "Synthetic document with simulated optical noise resulting in extraction confidence < 0.70 for container and invoice numbers, requiring executive review.",
        "expected_status": "REVIEW_REQUIRED",
        "expected_validation_outcome": "Review Required (Low-Confidence Fields Flagged)",
        "triad_documents": ["Commercial Invoice", "Packing List", "Bill of Lading"],
    },
    {
        "id": "E",
        "code": "INCOMPLETE_SET",
        "name": "Scenario E: Incomplete Document Set",
        "shipment_number": "SHP-DEMO-INCOMPLETE",
        "client_name": "Siemens Industrial Automation [DEMO]",
        "description": "Consignment with only Commercial Invoice uploaded. Packing List and Bill of Lading missing, correctly gating workflow in DOCUMENTS_PENDING.",
        "expected_status": "DOCUMENTS_PENDING",
        "expected_validation_outcome": "Missing Required Documents (PL & BL Pending)",
        "triad_documents": ["Commercial Invoice"],
    },
]


class SimulationEngine:
    """
    End-to-End Demonstration and Simulation Engine for CargoLens AI.
    Executes actual application workflows across document generation, storage,
    OCR processing, structured extraction, cross-document validation, human review,
    readiness evaluation, and CSV export.
    """

    @staticmethod
    async def clean_shipment(session: AsyncSession, shipment_number: str) -> None:
        """
        Cleanly removes a prior demo shipment and its physical storage files.
        Enforces strict safety: only deletes if is_demo is True.
        Never deletes non-demo shipments, even if shipment number matches.
        """
        stmt = select(Shipment).where(
            and_(
                Shipment.shipment_number == shipment_number,
                Shipment.is_demo.is_(True),
            )
        )
        res = await session.execute(stmt)
        shipment = res.scalar_one_or_none()
        if not shipment:
            return

        storage = get_storage_service()
        docs_stmt = select(Document).where(Document.shipment_id == shipment.id)
        docs = (await session.execute(docs_stmt)).scalars().all()
        for doc in docs:
            if doc.storage_key:
                try:
                    await storage.delete_file(doc.storage_key)
                except Exception as e:
                    logger.warning(f"Failed to delete storage file {doc.storage_key}: {e}")

        await session.execute(delete(Shipment).where(Shipment.id == shipment.id))
        await session.commit()

    @staticmethod
    async def clean_all_demo(session: AsyncSession) -> int:
        """
        Cleanly removes all demo shipments explicitly marked with is_demo=True.
        Cleans physical storage files from disk and relies on foreign-key CASCADE for relations.
        Never touches shipments without is_demo=True, even if their client_name contains '[DEMO]'.
        """
        stmt = select(Shipment).where(Shipment.is_demo.is_(True))
        res = await session.execute(stmt)
        demo_shipments = res.scalars().all()

        if not demo_shipments:
            return 0

        storage = get_storage_service()
        demo_ids = [s.id for s in demo_shipments]

        docs_stmt = select(Document).where(Document.shipment_id.in_(demo_ids))
        docs = (await session.execute(docs_stmt)).scalars().all()
        for doc in docs:
            if doc.storage_key:
                try:
                    await storage.delete_file(doc.storage_key)
                except Exception as e:
                    logger.warning(f"Failed to delete storage file {doc.storage_key}: {e}")

        await session.execute(delete(Shipment).where(Shipment.id.in_(demo_ids)))
        await session.commit()
        logger.info(f"Cleaned {len(demo_shipments)} demo shipment records and associated storage files.")
        return len(demo_shipments)

    @classmethod
    def get_provider(cls, provider_type: str) -> BaseExtractionProvider:
        """Instantiates the appropriate extraction provider."""
        clean_choice = provider_type.strip().lower()
        if clean_choice == "claude":
            if not settings.ANTHROPIC_API_KEY or not settings.ANTHROPIC_API_KEY.strip():
                raise ProviderConfigurationError(
                    "Anthropic API key is not configured. Please set ANTHROPIC_API_KEY in environment or .env, "
                    "or select the Deterministic Development Fixture."
                )
            return ClaudeVisionExtractionProvider()
        return DeterministicFixtureExtractionProvider()

    @classmethod
    async def _upload_and_queue_document(
        cls,
        session: AsyncSession,
        shipment_id: uuid.UUID,
        doc_type: DocumentType,
        filename: str,
        pdf_bytes: bytes,
        creator_user_id: uuid.UUID,
    ) -> Tuple[Document, ProcessingJob]:
        """Saves PDF to storage, registers Document and queues ProcessingJob."""
        storage = get_storage_service()
        storage_key = storage.get_safe_storage_key("pdf")
        sha256_hash = hashlib.sha256(pdf_bytes).hexdigest()
        file_size = len(pdf_bytes)

        async def stream_generator():
            yield pdf_bytes

        await storage.save_file(stream_generator(), storage_key)

        doc = Document(
            shipment_id=shipment_id,
            document_type=doc_type,
            original_filename=filename,
            storage_key=storage_key,
            mime_type="application/pdf",
            file_extension="pdf",
            file_size_bytes=file_size,
            sha256_checksum=sha256_hash,
            uploaded_by=creator_user_id,
            processing_status=DocumentProcessingStatus.PENDING,
            version=1,
            is_active=True,
        )
        session.add(doc)
        await session.flush()

        job = ProcessingJob(
            document_id=doc.id,
            job_type="DOCUMENT_INGESTION",
            status=JobStatus.PENDING,
            attempt_count=0,
            max_attempts=3,
        )
        session.add(job)
        await session.flush()

        return doc, job

    @classmethod
    async def _process_document_through_ocr(
        cls,
        session: AsyncSession,
        doc: Document,
        job: ProcessingJob,
    ) -> None:
        """Executes the genuine OCR pipeline and worker lease completion."""
        ocr = OcrPipeline()
        # Read file bytes from storage
        storage = get_storage_service()
        chunks = []
        async for chunk in storage.get_file_stream(doc.storage_key):
            chunks.append(chunk)
        file_bytes = b"".join(chunks)

        # Execute OCR
        extraction_result = await ocr.process_document(
            file_bytes=file_bytes,
            file_extension="pdf",
            document_id=doc.id,
        )

        # Claim job lease
        lease_token = uuid.uuid4()
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now(timezone.utc)
        job.attempt_count += 1
        job.lease_token = lease_token
        job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=60)
        await session.flush()

        # Persist OCR extraction
        await JobWorkerService.persist_extraction(
            session, doc.id, extraction_result, lease_token=lease_token
        )

        # Complete job
        await JobWorkerService.complete_job(
            session,
            job.id,
            lease_token=lease_token,
            doc_status=DocumentProcessingStatus.COMPLETED,
        )
        await session.commit()
        await session.refresh(doc)

    @classmethod
    async def _execute_structured_extraction(
        cls,
        session: AsyncSession,
        doc: Document,
        provider: BaseExtractionProvider,
    ) -> StructuredExtraction:
        """Executes structured extraction via the provider-neutral AI service."""
        ai_service = StructuredExtractionService(provider=provider)
        extraction_rec = await ai_service.execute_extraction(session, doc)
        return extraction_rec

    @classmethod
    async def simulate_scenario(
        cls,
        session: AsyncSession,
        scenario_code: str,
        creator_user: User,
        manager_user: User,
        provider_type: str = "fixture",
    ) -> Dict[str, Any]:
        """
        Executes a single scenario end-to-end through real application components.
        """
        scenario_code = scenario_code.upper().strip()
        provider = cls.get_provider(provider_type)

        if scenario_code in ("A", "COMPLETE_WORKFLOW"):
            return await cls._run_scenario_a(
                session, creator_user, manager_user, provider
            )
        elif scenario_code in ("B", "WEIGHT_DISCREPANCY"):
            return await cls._run_scenario_b(
                session, creator_user, manager_user, provider
            )
        elif scenario_code in ("C", "MISSING_FINANCIAL"):
            return await cls._run_scenario_c(
                session, creator_user, manager_user, provider
            )
        elif scenario_code in ("D", "LOW_CONFIDENCE"):
            return await cls._run_scenario_d(
                session, creator_user, manager_user, provider
            )
        elif scenario_code in ("E", "INCOMPLETE_SET"):
            return await cls._run_scenario_e(
                session, creator_user, manager_user, provider
            )
        else:
            raise ValueError(f"Unknown scenario code: '{scenario_code}'")

    @classmethod
    async def simulate_all(
        cls,
        session: AsyncSession,
        creator_user: User,
        manager_user: User,
        provider_type: str = "fixture",
    ) -> List[Dict[str, Any]]:
        """Executes all 5 demonstration scenarios in order."""
        results = []
        for code in ["COMPLETE_WORKFLOW", "WEIGHT_DISCREPANCY", "MISSING_FINANCIAL", "LOW_CONFIDENCE", "INCOMPLETE_SET"]:
            res = await cls.simulate_scenario(
                session=session,
                scenario_code=code,
                creator_user=creator_user,
                manager_user=manager_user,
                provider_type=provider_type,
            )
            results.append(res)
        return results

    # =========================================================================
    # Individual Scenario Implementations
    # =========================================================================

    @classmethod
    async def _run_scenario_a(
        cls,
        session: AsyncSession,
        creator_user: User,
        manager_user: User,
        provider: BaseExtractionProvider,
    ) -> Dict[str, Any]:
        """
        Scenario A: Complete Consignment Triad (Clean validation, awaiting human review).
        Generates full triad (CI, PL, BL) with consistent weights and financial values.
        Executes OCR and AI structured extraction.
        Runs cross-document validation: 11/11 rules pass!
        Strictly halts at REVIEW_REQUIRED so that human approval is genuinely performed
        by the reviewer through the standard application workspace.
        """
        shipment_number = "SHP-DEMO-001"
        await cls.clean_shipment(session, shipment_number)

        shipment = Shipment(
            shipment_number=shipment_number,
            client_name="Apex Solar Technologies India [DEMO]",
            origin_country="Vietnam",
            product_description="High-efficiency commercial solar inverter units 5kW",
            quantity=Decimal("1200.00"),
            unit_price=Decimal("28.0000"),
            currency="USD",
            gross_weight_kg=Decimal("14400.000"),
            status=ShipmentStatus.CREATED,
            created_by=creator_user.id,
            is_demo=True,
        )
        session.add(shipment)
        await session.commit()
        await session.refresh(shipment)

        # 1. Commercial Invoice
        ci_pdf = create_synthetic_pdf(
            "Commercial Invoice",
            [
                "Invoice Number: INV-2026-9011",
                "Invoice Date: 2026-10-18",
                "Seller: Apex Solar Vietnam Ltd.",
                "Buyer: Apex Solar Technologies India Pvt Ltd",
                "Port of Loading: Da Nang, Vietnam",
                "Port of Discharge: Nhava Sheva (INNSA), India",
                "Currency: USD",
                "Item: Commercial Solar Inverter Units 5kW",
                "Quantity: 1,200 PCS",
                "Unit Price: USD 28.00",
                "Subtotal: USD 33,600.00",
                "Grand Total: USD 33,600.00",
                "Gross Weight: 14,400.00 KG",
                "Net Weight: 13,200.00 KG",
                "Package Count: 60 Pallets",
            ],
        )
        ci_doc, ci_job = await cls._upload_and_queue_document(
            session, shipment.id, DocumentType.COMMERCIAL_INVOICE, "INV-2026-9011.pdf", ci_pdf, creator_user.id
        )

        # 2. Packing List
        pl_pdf = create_synthetic_pdf(
            "Packing List",
            [
                "Invoice Reference: INV-2026-9011",
                "Exporter: Apex Solar Vietnam Ltd.",
                "Importer: Apex Solar Technologies India Pvt Ltd",
                "Package Count: 60 Pallets",
                "Package Type: PALLETS",
                "Container Numbers: CMAU7891234",
                "Gross Weight: 14,400.00 KG",
                "Net Weight: 13,200.00 KG",
                "Item: Commercial Solar Inverter Units 5kW | Quantity: 1,200 PCS | Package Count: 60 Pallets",
            ],
        )
        pl_doc, pl_job = await cls._upload_and_queue_document(
            session, shipment.id, DocumentType.PACKING_LIST, "PL-2026-9011.pdf", pl_pdf, creator_user.id
        )

        # 3. Bill of Lading
        bl_pdf = create_synthetic_pdf(
            "Bill of Lading",
            [
                "Bill of Lading Number: BL-2026-9011",
                "Shipper: Apex Solar Vietnam Ltd.",
                "Consignee: Apex Solar Technologies India Pvt Ltd",
                "Notify Party: Apex Solar Technologies India Pvt Ltd",
                "Vessel: CMA CGM BIANCA",
                "Voyage: 041W",
                "Port of Loading: Da Nang, Vietnam",
                "Port of Discharge: Nhava Sheva (INNSA), India",
                "Goods Description: Commercial Solar Inverter Units 5kW",
                "Container Numbers: CMAU7891234",
                "Seal Numbers: CMA9821034",
                "Package Count: 60 Pallets",
                "Gross Weight: 14,400.00 KG",
            ],
        )
        bl_doc, bl_job = await cls._upload_and_queue_document(
            session, shipment.id, DocumentType.BILL_OF_LADING, "BL-2026-9011.pdf", bl_pdf, creator_user.id
        )

        shipment.status = ShipmentStatus.PROCESSING
        await session.commit()

        # Run OCR
        for doc, job in [(ci_doc, ci_job), (pl_doc, pl_job), (bl_doc, bl_job)]:
            await cls._process_document_through_ocr(session, doc, job)

        # Run Structured AI Extractions
        ci_ext = await cls._execute_structured_extraction(session, ci_doc, provider)
        pl_ext = await cls._execute_structured_extraction(session, pl_doc, provider)
        bl_ext = await cls._execute_structured_extraction(session, bl_doc, provider)

        # Run Cross-Document Validation
        val_engine = CrossDocumentValidationEngine()
        val_results = await val_engine.run_validation(session, shipment.id)

        # Simulation strictly halts at REVIEW_REQUIRED after successful extraction and validation.
        # Genuine human approval is preserved: simulation NEVER automatically creates human review
        # records, never bypasses human approval, and never automatically transitions to VERIFIED/EXPORTED.
        shipment.status = ShipmentStatus.REVIEW_REQUIRED
        await session.commit()
        await session.refresh(shipment)

        return cls._format_result(
            scenario_type="COMPLETE_WORKFLOW",
            shipment=shipment,
            docs=[ci_doc, pl_doc, bl_doc],
            ext=ci_ext,
            val_results=val_results,
            human_reviews_count=0,
            export_summary=None,
            notable_discrepancy="Full triad uploaded and validated (11/11 rules passed). Awaiting genuine human review, confirmation, and verification.",
        )

    @classmethod
    async def _run_scenario_b(
        cls,
        session: AsyncSession,
        creator_user: User,
        manager_user: User,
        provider: BaseExtractionProvider,
    ) -> Dict[str, Any]:
        """Scenario B: 45 kg Gross Weight Discrepancy (SHP-24811)."""
        shipment_number = "SHP-24811"
        await cls.clean_shipment(session, shipment_number)

        shipment = Shipment(
            shipment_number=shipment_number,
            client_name="Lumileds Global Trading [DEMO]",
            origin_country="China",
            product_description="LED panel light 40W 600x600 IP40 Commercial Grade",
            quantity=Decimal("2400.00"),
            unit_price=Decimal("6.8000"),
            currency="USD",
            gross_weight_kg=Decimal("3120.000"),
            status=ShipmentStatus.CREATED,
            created_by=creator_user.id,
            is_demo=True,
        )
        session.add(shipment)
        await session.commit()
        await session.refresh(shipment)

        # 1. Commercial Invoice (Gross weight: 3,120.00 KG)
        ci_pdf = create_synthetic_pdf(
            "Commercial Invoice",
            [
                "Invoice Number: INV-2026-24811",
                "Invoice Date: 2026-10-15",
                "Seller: Shenzhen Lumileds Opto Co., Ltd.",
                "Buyer: Lumileds Global Trading India Pvt Ltd",
                "Port of Loading: Shenzhen, China",
                "Port of Discharge: Nhava Sheva (INNSA), India",
                "Currency: USD",
                "Item: LED panel light 40W 600x600 IP40 Commercial Grade",
                "Quantity: 2,400 PCS",
                "Unit Price: USD 6.80",
                "Subtotal: USD 16,320.00",
                "Gross Weight: 3,120.00 KG",
                "Net Weight: 2,880.00 KG",
                "Package Count: 120 Cartons",
            ],
        )
        ci_doc, ci_job = await cls._upload_and_queue_document(
            session, shipment.id, DocumentType.COMMERCIAL_INVOICE, "INV-2026-24811.pdf", ci_pdf, creator_user.id
        )

        # 2. Packing List (Gross weight: 3,165.00 KG -> 45 kg mismatch!)
        pl_pdf = create_synthetic_pdf(
            "Packing List",
            [
                "Invoice Reference: INV-2026-24811",
                "Exporter: Shenzhen Lumileds Opto Co., Ltd.",
                "Importer: Lumileds Global Trading India Pvt Ltd",
                "Package Count: 120 Cartons",
                "Package Type: CARTONS",
                "Container Numbers: MSCU1029384",
                "Gross Weight: 3,165.00 KG",
                "Net Weight: 2,880.00 KG",
                "Item: LED panel light 40W - 20 pcs per carton x 120 cartons = 2,400 pcs",
            ],
        )
        pl_doc, pl_job = await cls._upload_and_queue_document(
            session, shipment.id, DocumentType.PACKING_LIST, "PL-2026-24811.pdf", pl_pdf, creator_user.id
        )

        # 3. Bill of Lading (Gross weight: 3,120.00 KG)
        bl_pdf = create_synthetic_pdf(
            "Bill of Lading",
            [
                "Bill of Lading Number: MEDUSH109283",
                "Shipper: Shenzhen Lumileds Opto Co., Ltd.",
                "Consignee: Lumileds Global Trading India Pvt Ltd",
                "Notify Party: Lumileds Global Trading India Pvt Ltd",
                "Vessel: MSC LORETTA",
                "Voyage: 2603E",
                "Port of Loading: Shenzhen, China",
                "Port of Discharge: Nhava Sheva (INNSA), India",
                "Goods Description: LED panel light 40W 600x600 IP40 Commercial Grade",
                "Container Numbers: MSCU1029384",
                "Seal Numbers: MSC8392102",
                "Package Count: 120 Cartons",
                "Gross Weight: 3,120.00 KG",
            ],
        )
        bl_doc, bl_job = await cls._upload_and_queue_document(
            session, shipment.id, DocumentType.BILL_OF_LADING, "BL-2026-24811.pdf", bl_pdf, creator_user.id
        )

        shipment.status = ShipmentStatus.PROCESSING
        await session.commit()

        # Run OCR
        for doc, job in [(ci_doc, ci_job), (pl_doc, pl_job), (bl_doc, bl_job)]:
            await cls._process_document_through_ocr(session, doc, job)

        # Run Structured AI Extractions
        ci_ext = await cls._execute_structured_extraction(session, ci_doc, provider)
        await cls._execute_structured_extraction(session, pl_doc, provider)
        await cls._execute_structured_extraction(session, bl_doc, provider)

        # Run Validation
        val_engine = CrossDocumentValidationEngine()
        val_results = await val_engine.run_validation(session, shipment.id)

        shipment.status = ShipmentStatus.REVIEW_REQUIRED
        await session.commit()
        await session.refresh(shipment)

        return cls._format_result(
            scenario_type="WEIGHT_DISCREPANCY",
            shipment=shipment,
            docs=[ci_doc, pl_doc, bl_doc],
            ext=ci_ext,
            val_results=val_results,
            human_reviews_count=0,
            notable_discrepancy="Gross weight mismatch: Commercial Invoice declares 3,120.00 kg, Packing List declares 3,165.00 kg (Discrepancy: 45.00 kg)",
        )

    @classmethod
    async def _run_scenario_c(
        cls,
        session: AsyncSession,
        creator_user: User,
        manager_user: User,
        provider: BaseExtractionProvider,
    ) -> Dict[str, Any]:
        """Scenario C: Missing Financial Information (SHP-24812)."""
        shipment_number = "SHP-24812"
        await cls.clean_shipment(session, shipment_number)

        shipment = Shipment(
            shipment_number=shipment_number,
            client_name="Klinger Fluid Control [DEMO]",
            origin_country="Germany",
            product_description="Steel ball valve DN50 PN40 Flanged End Industrial Grade",
            quantity=Decimal("180.00"),
            unit_price=Decimal("42.5000"),
            currency="EUR",
            gross_weight_kg=Decimal("1460.000"),
            status=ShipmentStatus.CREATED,
            created_by=creator_user.id,
            is_demo=True,
        )
        session.add(shipment)
        await session.commit()
        await session.refresh(shipment)

        # 1. Commercial Invoice: Grand Total intentionally omitted from lines!
        ci_pdf = create_synthetic_pdf(
            "Commercial Invoice",
            [
                "Invoice Number: INV-2026-24812",
                "Invoice Date: 2026-10-16",
                "Seller: Klinger Fluid Control GmbH & Co. KG",
                "Buyer: Klinger India Flow Solutions Pvt Ltd",
                "Port of Loading: Hamburg, Germany",
                "Port of Discharge: Nhava Sheva (INNSA), India",
                "Currency: EUR",
                "Item: Steel ball valve DN50 PN40 Flanged End",
                "Quantity: 180 PCS",
                "Unit Price: EUR 42.50",
                "Subtotal: EUR 7,650.00",
                "Gross Weight: 1,460.00 KG",
                "Net Weight: 1,320.00 KG",
                "Package Count: 15 Wooden Crates",
            ],
        )
        ci_doc, ci_job = await cls._upload_and_queue_document(
            session, shipment.id, DocumentType.COMMERCIAL_INVOICE, "INV-2026-24812.pdf", ci_pdf, creator_user.id
        )

        # 2. Packing List
        pl_pdf = create_synthetic_pdf(
            "Packing List",
            [
                "Invoice Reference: INV-2026-24812",
                "Exporter: Klinger Fluid Control GmbH & Co. KG",
                "Importer: Klinger India Flow Solutions Pvt Ltd",
                "Package Count: 15 Wooden Crates",
                "Package Type: WOODEN CRATES",
                "Container Numbers: HLCU9021834",
                "Gross Weight: 1,460.00 KG",
                "Net Weight: 1,320.00 KG",
                "Item: Steel ball valve DN50 - 12 pcs per crate x 15 crates = 180 pcs",
            ],
        )
        pl_doc, pl_job = await cls._upload_and_queue_document(
            session, shipment.id, DocumentType.PACKING_LIST, "PL-2026-24812.pdf", pl_pdf, creator_user.id
        )

        # 3. Bill of Lading
        bl_pdf = create_synthetic_pdf(
            "Bill of Lading",
            [
                "Bill of Lading Number: HLCUDE2093847",
                "Shipper: Klinger Fluid Control GmbH & Co. KG",
                "Consignee: Klinger India Flow Solutions Pvt Ltd",
                "Notify Party: Klinger India Flow Solutions Pvt Ltd",
                "Vessel: HAPAG-LLOYD AL ZUBARA",
                "Voyage: 2640W",
                "Port of Loading: Hamburg, Germany",
                "Port of Discharge: Nhava Sheva (INNSA), India",
                "Container Numbers: HLCU9021834",
                "Seal Numbers: HL7492019",
                "Package Count: 15 Wooden Crates",
                "Gross Weight: 1,460.00 KG",
            ],
        )
        bl_doc, bl_job = await cls._upload_and_queue_document(
            session, shipment.id, DocumentType.BILL_OF_LADING, "BL-2026-24812.pdf", bl_pdf, creator_user.id
        )

        shipment.status = ShipmentStatus.PROCESSING
        await session.commit()

        # Run OCR
        for doc, job in [(ci_doc, ci_job), (pl_doc, pl_job), (bl_doc, bl_job)]:
            await cls._process_document_through_ocr(session, doc, job)

        # Run Structured AI Extractions
        ci_ext = await cls._execute_structured_extraction(session, ci_doc, provider)
        await cls._execute_structured_extraction(session, pl_doc, provider)
        await cls._execute_structured_extraction(session, bl_doc, provider)

        # Run Validation
        val_engine = CrossDocumentValidationEngine()
        val_results = await val_engine.run_validation(session, shipment.id)

        shipment.status = ShipmentStatus.REVIEW_REQUIRED
        await session.commit()
        await session.refresh(shipment)

        return cls._format_result(
            scenario_type="MISSING_FINANCIAL",
            shipment=shipment,
            docs=[ci_doc, pl_doc, bl_doc],
            ext=ci_ext,
            val_results=val_results,
            human_reviews_count=0,
            notable_discrepancy="Missing invoice grand total: calculated line sum is 7,650.00 EUR, but arithmetic sum is protected and not fabricated as confirmed invoice total",
        )

    @classmethod
    async def _run_scenario_d(
        cls,
        session: AsyncSession,
        creator_user: User,
        manager_user: User,
        provider: BaseExtractionProvider,
    ) -> Dict[str, Any]:
        """Scenario D: Low-Confidence Field Review (SHP-DEMO-LOWCONF)."""
        shipment_number = "SHP-DEMO-LOWCONF"
        await cls.clean_shipment(session, shipment_number)

        shipment = Shipment(
            shipment_number=shipment_number,
            client_name="Rotork Controls International [DEMO]",
            origin_country="United Kingdom",
            product_description="Electro-hydraulic valve actuators and control modules",
            quantity=Decimal("50.00"),
            unit_price=Decimal("420.0000"),
            currency="GBP",
            gross_weight_kg=Decimal("850.000"),
            status=ShipmentStatus.CREATED,
            created_by=creator_user.id,
            is_demo=True,
        )
        session.add(shipment)
        await session.commit()
        await session.refresh(shipment)

        # 1. Commercial Invoice with low confidence marker
        ci_pdf = create_synthetic_pdf(
            "Commercial Invoice",
            [
                "Invoice Number: INV-2026-ROTORK-99",
                "Invoice Date: 2026-10-19",
                "Seller: Rotork Controls Ltd.",
                "Buyer: Rotork India Control Systems Pvt Ltd",
                "Port of Loading: Southampton, United Kingdom",
                "Port of Discharge: Nhava Sheva (INNSA), India",
                "Currency: GBP",
                "Item: Electro-hydraulic valve actuators",
                "Quantity: 50 PCS",
                "Unit Price: GBP 420.00",
                "Subtotal: GBP 21,000.00",
                "Grand Total: GBP 21,000.00",
                "Gross Weight: 850.00 KG",
                "Net Weight: 780.00 KG",
                "Package Count: 10 Wooden Cases",
            ],
            is_low_confidence=True,
        )
        ci_doc, ci_job = await cls._upload_and_queue_document(
            session, shipment.id, DocumentType.COMMERCIAL_INVOICE, "INV-ROTORK-99.pdf", ci_pdf, creator_user.id
        )

        # 2. Packing List
        pl_pdf = create_synthetic_pdf(
            "Packing List",
            [
                "Invoice Reference: INV-2026-ROTORK-99",
                "Exporter: Rotork Controls Ltd.",
                "Importer: Rotork India Control Systems Pvt Ltd",
                "Package Count: 10 Wooden Cases",
                "Package Type: WOODEN CASES",
                "Container Numbers: OOCU8912301",
                "Gross Weight: 850.00 KG",
                "Net Weight: 780.00 KG",
                "Item: Valve Actuators - 5 pcs per case x 10 cases = 50 pcs",
            ],
            is_low_confidence=True,
        )
        pl_doc, pl_job = await cls._upload_and_queue_document(
            session, shipment.id, DocumentType.PACKING_LIST, "PL-ROTORK-99.pdf", pl_pdf, creator_user.id
        )

        # 3. Bill of Lading
        bl_pdf = create_synthetic_pdf(
            "Bill of Lading",
            [
                "Bill of Lading Number: OOLU29018471",
                "Shipper: Rotork Controls Ltd.",
                "Consignee: Rotork India Control Systems Pvt Ltd",
                "Notify Party: Rotork India Control Systems Pvt Ltd",
                "Vessel: OOCL HONG KONG",
                "Voyage: 182W",
                "Port of Loading: Southampton, United Kingdom",
                "Port of Discharge: Nhava Sheva (INNSA), India",
                "Container Numbers: OOCU8912301",
                "Seal Numbers: OOC890123",
                "Package Count: 10 Wooden Cases",
                "Gross Weight: 850.00 KG",
            ],
            is_low_confidence=True,
        )
        bl_doc, bl_job = await cls._upload_and_queue_document(
            session, shipment.id, DocumentType.BILL_OF_LADING, "BL-ROTORK-99.pdf", bl_pdf, creator_user.id
        )

        shipment.status = ShipmentStatus.PROCESSING
        await session.commit()

        # Run OCR
        for doc, job in [(ci_doc, ci_job), (pl_doc, pl_job), (bl_doc, bl_job)]:
            await cls._process_document_through_ocr(session, doc, job)

        # Run Structured AI Extractions
        ci_ext = await cls._execute_structured_extraction(session, ci_doc, provider)
        await cls._execute_structured_extraction(session, pl_doc, provider)
        await cls._execute_structured_extraction(session, bl_doc, provider)

        # Run Validation
        val_engine = CrossDocumentValidationEngine()
        val_results = await val_engine.run_validation(session, shipment.id)

        shipment.status = ShipmentStatus.REVIEW_REQUIRED
        await session.commit()
        await session.refresh(shipment)

        return cls._format_result(
            scenario_type="LOW_CONFIDENCE",
            shipment=shipment,
            docs=[ci_doc, pl_doc, bl_doc],
            ext=ci_ext,
            val_results=val_results,
            human_reviews_count=0,
            notable_discrepancy="Low-confidence field extraction (< 0.70) detected. Mandatory human review overlay required.",
        )

    @classmethod
    async def _run_scenario_e(
        cls,
        session: AsyncSession,
        creator_user: User,
        manager_user: User,
        provider: BaseExtractionProvider,
    ) -> Dict[str, Any]:
        """Scenario E: Incomplete Document Set (Only CI uploaded, PL and BL missing)."""
        shipment_number = "SHP-DEMO-INCOMPLETE"
        await cls.clean_shipment(session, shipment_number)

        shipment = Shipment(
            shipment_number=shipment_number,
            client_name="Siemens Industrial Automation [DEMO]",
            origin_country="Germany",
            product_description="Programmable logic controllers and input/output modules",
            quantity=Decimal("300.00"),
            unit_price=Decimal("115.0000"),
            currency="EUR",
            gross_weight_kg=Decimal("420.000"),
            status=ShipmentStatus.CREATED,
            created_by=creator_user.id,
            is_demo=True,
        )
        session.add(shipment)
        await session.commit()
        await session.refresh(shipment)

        # Only Commercial Invoice uploaded
        ci_pdf = create_synthetic_pdf(
            "Commercial Invoice",
            [
                "Invoice Number: INV-2026-SIEMENS-102",
                "Invoice Date: 2026-10-20",
                "Seller: Siemens AG Industry Sector",
                "Buyer: Siemens India Industrial Systems Ltd",
                "Port of Loading: Bremen, Germany",
                "Port of Discharge: Nhava Sheva (INNSA), India",
                "Currency: EUR",
                "Item: Simatic S7-1500 PLC Modules",
                "Quantity: 300 PCS",
                "Unit Price: EUR 115.00",
                "Subtotal: EUR 34,500.00",
                "Grand Total: EUR 34,500.00",
                "Gross Weight: 420.00 KG",
                "Net Weight: 380.00 KG",
                "Package Count: 25 Boxes",
            ],
        )
        ci_doc, ci_job = await cls._upload_and_queue_document(
            session, shipment.id, DocumentType.COMMERCIAL_INVOICE, "INV-SIEMENS-102.pdf", ci_pdf, creator_user.id
        )

        # Run OCR on CI
        await cls._process_document_through_ocr(session, ci_doc, ci_job)

        # Run Structured AI Extractions
        ci_ext = await cls._execute_structured_extraction(session, ci_doc, provider)

        # Validation engine
        val_engine = CrossDocumentValidationEngine()
        val_results = await val_engine.run_validation(session, shipment.id)

        # Kept in DOCUMENTS_PENDING because PL and BL are missing
        shipment.status = ShipmentStatus.DOCUMENTS_PENDING
        await session.commit()
        await session.refresh(shipment)

        return cls._format_result(
            scenario_type="INCOMPLETE_SET",
            shipment=shipment,
            docs=[ci_doc],
            ext=ci_ext,
            val_results=val_results,
            human_reviews_count=0,
            notable_discrepancy="Incomplete document triad: Packing List and Bill of Lading are missing. Verification strictly gated.",
        )

    @classmethod
    def _format_result(
        cls,
        scenario_type: str,
        shipment: Shipment,
        docs: List[Document],
        ext: Optional[StructuredExtraction],
        val_results: List[ShipmentValidationResult],
        human_reviews_count: int,
        export_summary: Optional[Dict[str, Any]] = None,
        notable_discrepancy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Formats standard response dictionary for a completed scenario run."""
        docs_summary = [
            {
                "id": str(d.id),
                "document_type": d.document_type.value,
                "filename": d.original_filename,
                "file_size_bytes": d.file_size_bytes,
                "sha256_checksum": d.sha256_checksum,
                "status": d.processing_status.value,
            }
            for d in docs
        ]

        ext_summary = None
        if ext:
            conf_sum = ext.field_confidence_summary or {}
            ext_summary = {
                "provider": ext.provider,
                "model": ext.model,
                "status": ext.status.value,
                "average_confidence": conf_sum.get("average_confidence"),
                "low_confidence_fields": conf_sum.get("low_confidence_fields", []),
                "missing_fields": conf_sum.get("missing_fields", []),
            }

        passed_cnt = sum(1 for r in val_results if r.outcome == ValidationOutcome.PASS)
        failed_cnt = sum(1 for r in val_results if r.outcome == ValidationOutcome.FAIL)
        missing_cnt = sum(1 for r in val_results if r.outcome == ValidationOutcome.MISSING_DATA)

        val_summary = {
            "total_rules": len(val_results),
            "passed_count": passed_cnt,
            "failed_count": failed_cnt,
            "missing_data_count": missing_cnt,
            "has_blocking_failures": failed_cnt > 0,
            "notable_discrepancy": notable_discrepancy,
        }

        first_doc_id = str(docs[0].id) if docs else None
        review_url = f"/review/{shipment.id}/{first_doc_id}" if first_doc_id else None

        return {
            "scenario_type": scenario_type,
            "shipment_id": shipment.id,
            "shipment_number": shipment.shipment_number,
            "client_name": shipment.client_name,
            "status": shipment.status.value,
            "documents": docs_summary,
            "extraction": ext_summary,
            "validation": val_summary,
            "human_reviews_count": human_reviews_count,
            "verification_ready": (shipment.status in (ShipmentStatus.VERIFIED, ShipmentStatus.EXPORTED)),
            "export": export_summary,
            "workspace_url": f"/shipments/{shipment.id}",
            "review_url": review_url,
        }

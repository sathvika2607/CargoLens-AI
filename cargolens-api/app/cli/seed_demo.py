"""
CargoLens AI — Enterprise Demonstration Seed CLI
Populates repeatable, idempotent demonstration data for technical evaluations and product demos.

Demonstrates:
- SHP-24811: LED panel light 40W, Qty 2,400, USD 6.80/unit, CI gross weight 3,120 kg,
             PL gross weight 3,165 kg (Exact 45.00 kg discrepancy).
- SHP-24812: Steel ball valve DN50, Qty 180, EUR 42.50/unit, gross weight 1,460 kg.
             Line total EUR 7,650.00, but unstated CI grand total (InvoiceArithmeticRule protection).
- Full spectrum of workflow states: CREATED, DOCUMENTS_PENDING, PROCESSING, REVIEW_REQUIRED, VERIFIED, EXPORTED.
- Demo users: executive@cargolens.in and manager@cargolens.in.
"""

import argparse
import asyncio
import hashlib
import json
import logging
import sys
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any

import pymupdf
from sqlalchemy import select, and_, delete
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import AsyncSessionFactory
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.export import ShipmentExportRecord, ExportStatus
from app.models.extraction import ExtractionStatus
from app.models.field_review import DocumentFieldReview, FieldReviewActionType, ReviewProvenance
from app.models.processing_job import ProcessingJob, JobStatus
from app.models.shipment import Shipment, ShipmentStatus
from app.models.structured_extraction import StructuredExtraction
from app.models.user import User, UserRole
from app.schemas.structured_extraction import (
    CommercialInvoiceExtraction,
    PackingListExtraction,
    BillOfLadingExtraction,
    ExtractedField,
    InvoiceLineItem,
    PackingLineItem,
)
from app.security import hash_password
from app.storage import get_storage_service
from app.services.validation.engine import CrossDocumentValidationEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cargolens.seed")


DEMO_USERS = [
    {
        "email": "executive@cargolens.in",
        "full_name": "Documentation Executive",
        "password": "DemoExecutive2026!",
        "role": UserRole.DOCUMENTATION_EXECUTIVE,
    },
    {
        "email": "manager@cargolens.in",
        "full_name": "Senior Documentation Manager",
        "password": "DemoManager2026!",
        "role": UserRole.DOCUMENTATION_MANAGER,
    },
]


from app.services.documents.pdf_generator import create_synthetic_pdf, TradePdfGenerator


async def save_pdf_to_storage(pdf_bytes: bytes, filename: str) -> tuple[str, str, int]:
    """Stores PDF bytes using the configured StorageService and returns (storage_key, sha256, size)."""
    storage = get_storage_service()
    storage_key = storage.get_safe_storage_key("pdf")
    sha256_hash = hashlib.sha256(pdf_bytes).hexdigest()
    file_size = len(pdf_bytes)

    async def stream_generator():
        yield pdf_bytes

    await storage.save_file(stream_generator(), storage_key)
    return storage_key, sha256_hash, file_size


async def seed_users(session, overwrite_passwords: bool = False) -> Dict[str, User]:
    """
    Idempotently ensures demo users exist in the database.
    - Creates both accounts if they do not exist.
    - Assigns the correct DOCUMENTATION_EXECUTIVE and DOCUMENTATION_MANAGER roles.
    - Uses the application's existing secure password hashing implementation (Argon2id).
    - Sets both accounts active.
    - Does not create duplicate accounts on repeated runs.
    - Does not overwrite passwords or modify unrelated existing users.
    - Does not weaken authentication or RBAC.
    """
    users_by_email: Dict[str, User] = {}

    for u_spec in DEMO_USERS:
        stmt = select(User).where(User.email == u_spec["email"])
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if user:
            # Update role, active status, and display name for demo account
            user.full_name = u_spec["full_name"]
            user.role = u_spec["role"]
            user.is_active = True
            if overwrite_passwords:
                user.hashed_password = hash_password(u_spec["password"])
                logger.info(f"Updated demo user password: {user.email} ({user.role.value})")
            else:
                logger.info(f"Existing demo user verified: {user.email} ({user.role.value}) — password preserved")
        else:
            user = User(
                email=u_spec["email"],
                full_name=u_spec["full_name"],
                role=u_spec["role"],
                hashed_password=hash_password(u_spec["password"]),
                is_active=True,
            )
            session.add(user)
            await session.flush()
            logger.info(f"Created demo user: {user.email} ({user.role.value})")

        users_by_email[user.email] = user

    await session.commit()
    return users_by_email


async def _clean_shipment(session, shipment_number: str):
    """Cleanly deletes any prior synthetic shipment and its cascaded relations using database-level CASCADE."""
    await session.execute(
        delete(Shipment).where(
            and_(
                Shipment.shipment_number == shipment_number,
                Shipment.is_demo.is_(True),
            )
        )
    )
    await session.commit()


async def seed_shipment_24811(session, creator_user: User, manager_user: User):
    """
    SHP-24811: LED panel light 40W, Qty 2,400, USD 6.80/unit.
    Commercial Invoice gross weight: 3,120.00 kg.
    Packing List gross weight: 3,165.00 kg.
    Demonstrates exact 45.00 kg discrepancy failing GrossWeightConsistencyRule.
    """
    shipment_number = "SHP-24811"
    await _clean_shipment(session, shipment_number)

    shipment = Shipment(
        shipment_number=shipment_number,
        client_name="Lumileds Global Trading [DEMO]",
        origin_country="China",
        product_description="LED panel light 40W 600x600 IP40 Commercial Grade",
        quantity=Decimal("2400.00"),
        unit_price=Decimal("6.8000"),
        currency="USD",
        gross_weight_kg=Decimal("3120.000"),
        status=ShipmentStatus.REVIEW_REQUIRED,
        created_by=creator_user.id,
        is_demo=True,
    )
    session.add(shipment)
    await session.flush()

    # 1. Commercial Invoice
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
    ci_key, ci_hash, ci_size = await save_pdf_to_storage(ci_pdf, "INV-24811.pdf")
    ci_doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="INV-2026-24811.pdf",
        storage_key=ci_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=ci_size,
        sha256_checksum=ci_hash,
        uploaded_by=creator_user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    session.add(ci_doc)
    await session.flush()

    ci_schema = CommercialInvoiceExtraction(
        invoice_number=ExtractedField(value="INV-2026-24811", confidence=0.99, evidence_text="Invoice Number: INV-2026-24811"),
        invoice_date=ExtractedField(value="2026-10-15", confidence=0.98, evidence_text="Invoice Date: 2026-10-15"),
        seller_name=ExtractedField(value="Shenzhen Lumileds Opto Co., Ltd.", confidence=0.99, evidence_text="Seller: Shenzhen Lumileds Opto Co., Ltd."),
        buyer_name=ExtractedField(value="Lumileds Global Trading India Pvt Ltd", confidence=0.98, evidence_text="Buyer: Lumileds Global Trading India Pvt Ltd"),
        currency=ExtractedField(value="USD", confidence=1.0, evidence_text="Currency: USD"),
        grand_total=ExtractedField(value=None, confidence=None, evidence_text=None),
        gross_weight_kg=ExtractedField(value=Decimal("3120.00"), confidence=0.98, evidence_text="Gross Weight: 3,120.00 KG"),
        net_weight_kg=ExtractedField(value=Decimal("2880.00"), confidence=0.97, evidence_text="Net Weight: 2,880.00 KG"),
        package_count=ExtractedField(value=120, confidence=0.95, evidence_text="Package Count: 120 Cartons"),
        line_items=[
            InvoiceLineItem(
                item_number=1,
                description=ExtractedField(value="LED panel light 40W 600x600 IP40 Commercial Grade", confidence=0.98, evidence_text="Item: LED panel light 40W 600x600 IP40 Commercial Grade"),
                quantity=ExtractedField(value=Decimal("2400"), confidence=0.99, evidence_text="Quantity: 2,400 PCS"),
                unit_price=ExtractedField(value=Decimal("6.80"), confidence=0.99, evidence_text="Unit Price: USD 6.80"),
                line_total=ExtractedField(value=Decimal("16320.00"), confidence=0.99, evidence_text="Subtotal: USD 16,320.00"),
            )
        ],
    )
    ci_ext = StructuredExtraction(
        document_id=ci_doc.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="synthetic-seed",
        model="seed-fixture-v1",
        extraction_mode="TEXT_FIRST",
        total_page_count=1,
        processed_page_count=1,
        extracted_data=ci_schema.model_dump(mode="json"),
        field_confidence_summary={"overall_confidence": 0.98, "fields_extracted": 10},
        completed_at=datetime.now(timezone.utc),
    )
    session.add(ci_ext)

    # 2. Packing List (Contains 3,165 kg Gross Weight -> 45 kg discrepancy)
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
    pl_key, pl_hash, pl_size = await save_pdf_to_storage(pl_pdf, "PL-24811.pdf")
    pl_doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.PACKING_LIST,
        original_filename="PL-2026-24811.pdf",
        storage_key=pl_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=pl_size,
        sha256_checksum=pl_hash,
        uploaded_by=creator_user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    session.add(pl_doc)
    await session.flush()

    pl_schema = PackingListExtraction(
        exporter_name=ExtractedField(value="Shenzhen Lumileds Opto Co., Ltd.", confidence=0.99, evidence_text="Exporter: Shenzhen Lumileds Opto Co., Ltd."),
        importer_name=ExtractedField(value="Lumileds Global Trading India Pvt Ltd", confidence=0.98, evidence_text="Importer: Lumileds Global Trading India Pvt Ltd"),
        invoice_reference=ExtractedField(value="INV-2026-24811", confidence=0.99, evidence_text="Invoice Reference: INV-2026-24811"),
        package_count=ExtractedField(value=120, confidence=0.97, evidence_text="Package Count: 120 Cartons"),
        package_type=ExtractedField(value="CARTONS", confidence=0.95, evidence_text="Package Type: CARTONS"),
        gross_weight_kg=ExtractedField(value=Decimal("3165.00"), confidence=0.99, evidence_text="Gross Weight: 3,165.00 KG"),
        net_weight_kg=ExtractedField(value=Decimal("2880.00"), confidence=0.98, evidence_text="Net Weight: 2,880.00 KG"),
        container_numbers=[ExtractedField(value="MSCU1029384", confidence=0.98, evidence_text="Container Numbers: MSCU1029384")],
        line_items=[
            PackingLineItem(
                item_number=1,
                description=ExtractedField(value="LED panel light 40W", confidence=0.98, evidence_text="Item: LED panel light 40W"),
                quantity=ExtractedField(value=Decimal("2400"), confidence=0.99, evidence_text="2,400 pcs"),
                unit_of_measure=ExtractedField(value="PCS", confidence=0.95, evidence_text="pcs"),
                package_count=ExtractedField(value=120, confidence=0.97, evidence_text="120 cartons"),
                package_type=ExtractedField(value="CARTONS", confidence=0.95, evidence_text="cartons"),
            )
        ],
    )
    pl_ext = StructuredExtraction(
        document_id=pl_doc.id,
        document_type=DocumentType.PACKING_LIST,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="synthetic-seed",
        model="seed-fixture-v1",
        extraction_mode="TEXT_FIRST",
        total_page_count=1,
        processed_page_count=1,
        extracted_data=pl_schema.model_dump(mode="json"),
        field_confidence_summary={"overall_confidence": 0.98, "fields_extracted": 8},
        completed_at=datetime.now(timezone.utc),
    )
    session.add(pl_ext)

    # 3. Bill of Lading
    bl_pdf = create_synthetic_pdf(
        "Ocean Bill of Lading",
        [
            "B/L Number: MSCUIN982341",
            "Shipper: Shenzhen Lumileds Opto Co., Ltd.",
            "Consignee: Lumileds Global Trading India Pvt Ltd",
            "Vessel / Voyage: MSC LAUREN / 261W",
            "Port of Loading: Shenzhen, China",
            "Port of Discharge: Nhava Sheva (INNSA), India",
            "Container: MSCU1029384",
            "Package Count: 120 Cartons",
            "Goods Description: LED panel light 40W Commercial Fixtures",
            "Gross Weight: 3,120.00 KG",
        ],
    )
    bl_key, bl_hash, bl_size = await save_pdf_to_storage(bl_pdf, "BL-24811.pdf")
    bl_doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.BILL_OF_LADING,
        original_filename="BL-MSCUIN982341.pdf",
        storage_key=bl_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=bl_size,
        sha256_checksum=bl_hash,
        uploaded_by=creator_user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    session.add(bl_doc)
    await session.flush()

    bl_schema = BillOfLadingExtraction(
        bl_number=ExtractedField(value="MSCUIN982341", confidence=0.99, evidence_text="B/L Number: MSCUIN982341"),
        shipper_name=ExtractedField(value="Shenzhen Lumileds Opto Co., Ltd.", confidence=0.98, evidence_text="Shipper: Shenzhen Lumileds Opto Co., Ltd."),
        consignee_name=ExtractedField(value="Lumileds Global Trading India Pvt Ltd", confidence=0.98, evidence_text="Consignee: Lumileds Global Trading India Pvt Ltd"),
        port_of_loading=ExtractedField(value="Shenzhen, China", confidence=0.96, evidence_text="Port of Loading: Shenzhen, China"),
        port_of_discharge=ExtractedField(value="Nhava Sheva (INNSA), India", confidence=0.96, evidence_text="Port of Discharge: Nhava Sheva (INNSA), India"),
        container_numbers=[ExtractedField(value="MSCU1029384", confidence=0.98, evidence_text="Container: MSCU1029384")],
        package_count=ExtractedField(value=120, confidence=0.95, evidence_text="Package Count: 120 Cartons"),
        gross_weight_kg=ExtractedField(value=Decimal("3120.00"), confidence=0.98, evidence_text="Gross Weight: 3,120.00 KG"),
        goods_description=ExtractedField(value="LED panel light 40W Commercial Fixtures", confidence=0.97, evidence_text="Goods Description: LED panel light 40W Commercial Fixtures"),
    )
    bl_ext = StructuredExtraction(
        document_id=bl_doc.id,
        document_type=DocumentType.BILL_OF_LADING,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="synthetic-seed",
        model="seed-fixture-v1",
        extraction_mode="TEXT_FIRST",
        total_page_count=1,
        processed_page_count=1,
        extracted_data=bl_schema.model_dump(mode="json"),
        field_confidence_summary={"overall_confidence": 0.98, "fields_extracted": 9},
        completed_at=datetime.now(timezone.utc),
    )
    session.add(bl_ext)
    await session.commit()

    # Execute dynamic cross-document validation engine
    engine = CrossDocumentValidationEngine()
    validation_results = await engine.run_validation(session, shipment.id)
    await session.commit()
    logger.info(f"Seeded {shipment_number}: evaluated {len(validation_results)} rules; 45 kg Gross Weight discrepancy detected.")


async def seed_shipment_24812(session, creator_user: User, manager_user: User):
    """
    SHP-24812: Steel ball valve DN50, Qty 180, EUR 42.50/unit, gross weight 1,460 kg.
    Line total is EUR 7,650, but grand_total is MISSING (unstated) in the source invoice.
    Demonstrates InvoiceArithmeticRule protection: calculated result must NOT be treated as confirmed invoice total.
    """
    shipment_number = "SHP-24812"
    await _clean_shipment(session, shipment_number)

    shipment = Shipment(
        shipment_number=shipment_number,
        client_name="Flowserve Industrial Valves [DEMO]",
        origin_country="Germany",
        product_description="Steel ball valve DN50 PN40 Flanged End High Pressure",
        quantity=Decimal("180.00"),
        unit_price=Decimal("42.5000"),
        currency="EUR",
        gross_weight_kg=Decimal("1460.000"),
        status=ShipmentStatus.REVIEW_REQUIRED,
        created_by=creator_user.id,
        is_demo=True,
    )
    session.add(shipment)
    await session.flush()

    # 1. Commercial Invoice with NO explicitly stated grand total
    ci_pdf = create_synthetic_pdf(
        "Commercial Invoice",
        [
            "Invoice Number: INV-DE-2026-9081",
            "Invoice Date: 2026-10-20",
            "Seller: Flowserve Gestra AG Germany",
            "Buyer: Flowserve India Controls Pvt Ltd",
            "Port of Loading: Hamburg, Germany",
            "Port of Discharge: Nhava Sheva (INNSA), India",
            "Currency: EUR",
            "Line 1: Steel ball valve DN50 | Qty: 180 PCS | Price: EUR 42.50 | Total: EUR 7,650.00",
            "Gross Weight: 1,460.00 KG",
            "Net Weight: 1,350.00 KG",
            "Package Count: 18 Wooden Crates",
            "[NOTE: Invoice summary footer omitted on original physical copy]",
        ],
    )
    ci_key, ci_hash, ci_size = await save_pdf_to_storage(ci_pdf, "INV-24812.pdf")
    ci_doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="INV-DE-2026-9081.pdf",
        storage_key=ci_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=ci_size,
        sha256_checksum=ci_hash,
        uploaded_by=creator_user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    session.add(ci_doc)
    await session.flush()

    ci_schema = CommercialInvoiceExtraction(
        invoice_number=ExtractedField(value="INV-DE-2026-9081", confidence=0.99, evidence_text="Invoice Number: INV-DE-2026-9081"),
        invoice_date=ExtractedField(value="2026-10-20", confidence=0.98, evidence_text="Invoice Date: 2026-10-20"),
        seller_name=ExtractedField(value="Flowserve Gestra AG Germany", confidence=0.99, evidence_text="Seller: Flowserve Gestra AG Germany"),
        buyer_name=ExtractedField(value="Flowserve India Controls Pvt Ltd", confidence=0.98, evidence_text="Buyer: Flowserve India Controls Pvt Ltd"),
        currency=ExtractedField(value="EUR", confidence=1.0, evidence_text="Currency: EUR"),
        grand_total=ExtractedField(value=None, confidence=None, evidence_text=None),  # MISSING FROM DOCUMENT
        gross_weight_kg=ExtractedField(value=Decimal("1460.00"), confidence=0.98, evidence_text="Gross Weight: 1,460.00 KG"),
        net_weight_kg=ExtractedField(value=Decimal("1350.00"), confidence=0.97, evidence_text="Net Weight: 1,350.00 KG"),
        package_count=ExtractedField(value=18, confidence=0.95, evidence_text="Package Count: 18 Wooden Crates"),
        line_items=[
            InvoiceLineItem(
                item_number=1,
                description=ExtractedField(value="Steel ball valve DN50", confidence=0.98, evidence_text="Line 1: Steel ball valve DN50"),
                quantity=ExtractedField(value=Decimal("180"), confidence=0.99, evidence_text="Qty: 180 PCS"),
                unit_price=ExtractedField(value=Decimal("42.50"), confidence=0.99, evidence_text="Price: EUR 42.50"),
                line_total=ExtractedField(value=Decimal("7650.00"), confidence=0.99, evidence_text="Total: EUR 7,650.00"),
            )
        ],
    )
    ci_ext = StructuredExtraction(
        document_id=ci_doc.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="synthetic-seed",
        model="seed-fixture-v1",
        extraction_mode="TEXT_FIRST",
        total_page_count=1,
        processed_page_count=1,
        extracted_data=ci_schema.model_dump(mode="json"),
        field_confidence_summary={"overall_confidence": 0.94, "fields_extracted": 8},
        completed_at=datetime.now(timezone.utc),
    )
    session.add(ci_ext)

    # 2. Packing List
    pl_pdf = create_synthetic_pdf(
        "Packing List",
        [
            "Invoice Reference: INV-DE-2026-9081",
            "Exporter: Flowserve Gestra AG Germany",
            "Importer: Flowserve India Controls Pvt Ltd",
            "Package Count: 18 Wooden Crates",
            "Package Type: CRATES",
            "Gross Weight: 1,460.00 KG",
            "Net Weight: 1,350.00 KG",
            "Container Numbers: HLCU9876543",
        ],
    )
    pl_key, pl_hash, pl_size = await save_pdf_to_storage(pl_pdf, "PL-24812.pdf")
    pl_doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.PACKING_LIST,
        original_filename="PL-DE-2026-9081.pdf",
        storage_key=pl_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=pl_size,
        sha256_checksum=pl_hash,
        uploaded_by=creator_user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    session.add(pl_doc)
    await session.flush()

    pl_schema = PackingListExtraction(
        exporter_name=ExtractedField(value="Flowserve Gestra AG Germany", confidence=0.99, evidence_text="Exporter: Flowserve Gestra AG Germany"),
        importer_name=ExtractedField(value="Flowserve India Controls Pvt Ltd", confidence=0.98, evidence_text="Importer: Flowserve India Controls Pvt Ltd"),
        invoice_reference=ExtractedField(value="INV-DE-2026-9081", confidence=0.99, evidence_text="Invoice Reference: INV-DE-2026-9081"),
        package_count=ExtractedField(value=18, confidence=0.97, evidence_text="Package Count: 18 Wooden Crates"),
        package_type=ExtractedField(value="CRATES", confidence=0.95, evidence_text="Package Type: CRATES"),
        gross_weight_kg=ExtractedField(value=Decimal("1460.00"), confidence=0.99, evidence_text="Gross Weight: 1,460.00 KG"),
        net_weight_kg=ExtractedField(value=Decimal("1350.00"), confidence=0.98, evidence_text="Net Weight: 1,350.00 KG"),
        container_numbers=[ExtractedField(value="HLCU9876543", confidence=0.98, evidence_text="Container Numbers: HLCU9876543")],
    )
    pl_ext = StructuredExtraction(
        document_id=pl_doc.id,
        document_type=DocumentType.PACKING_LIST,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="synthetic-seed",
        model="seed-fixture-v1",
        extraction_mode="TEXT_FIRST",
        total_page_count=1,
        processed_page_count=1,
        extracted_data=pl_schema.model_dump(mode="json"),
        completed_at=datetime.now(timezone.utc),
    )
    session.add(pl_ext)

    # 3. Bill of Lading
    bl_pdf = create_synthetic_pdf(
        "Ocean Bill of Lading",
        [
            "B/L Number: HAPAGHAM90812",
            "Shipper: Flowserve Gestra AG Germany",
            "Consignee: Flowserve India Controls Pvt Ltd",
            "Vessel / Voyage: BERLIN EXPRESS / 041E",
            "Port of Loading: Hamburg, Germany",
            "Port of Discharge: Nhava Sheva (INNSA), India",
            "Container: HLCU9876543",
            "Package Count: 18 Wooden Crates",
            "Gross Weight: 1,460.00 KG",
        ],
    )
    bl_key, bl_hash, bl_size = await save_pdf_to_storage(bl_pdf, "BL-24812.pdf")
    bl_doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.BILL_OF_LADING,
        original_filename="BL-HAPAGHAM90812.pdf",
        storage_key=bl_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=bl_size,
        sha256_checksum=bl_hash,
        uploaded_by=creator_user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    session.add(bl_doc)
    await session.flush()

    bl_schema = BillOfLadingExtraction(
        bl_number=ExtractedField(value="HAPAGHAM90812", confidence=0.99, evidence_text="B/L Number: HAPAGHAM90812"),
        shipper_name=ExtractedField(value="Flowserve Gestra AG Germany", confidence=0.98, evidence_text="Shipper: Flowserve Gestra AG Germany"),
        consignee_name=ExtractedField(value="Flowserve India Controls Pvt Ltd", confidence=0.98, evidence_text="Consignee: Flowserve India Controls Pvt Ltd"),
        port_of_loading=ExtractedField(value="Hamburg, Germany", confidence=0.96, evidence_text="Port of Loading: Hamburg, Germany"),
        port_of_discharge=ExtractedField(value="Nhava Sheva (INNSA), India", confidence=0.96, evidence_text="Port of Discharge: Nhava Sheva (INNSA), India"),
        container_numbers=[ExtractedField(value="HLCU9876543", confidence=0.98, evidence_text="Container: HLCU9876543")],
        package_count=ExtractedField(value=18, confidence=0.95, evidence_text="Package Count: 18 Wooden Crates"),
        gross_weight_kg=ExtractedField(value=Decimal("1460.00"), confidence=0.98, evidence_text="Gross Weight: 1,460.00 KG"),
        goods_description=ExtractedField(value="Steel ball valve DN50 PN40", confidence=0.97, evidence_text="Goods Description: Steel ball valve DN50 PN40"),
    )
    bl_ext = StructuredExtraction(
        document_id=bl_doc.id,
        document_type=DocumentType.BILL_OF_LADING,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="synthetic-seed",
        model="seed-fixture-v1",
        extraction_mode="TEXT_FIRST",
        total_page_count=1,
        processed_page_count=1,
        extracted_data=bl_schema.model_dump(mode="json"),
        completed_at=datetime.now(timezone.utc),
    )
    session.add(bl_ext)
    await session.commit()

    # Execute dynamic cross-document validation engine
    engine = CrossDocumentValidationEngine()
    validation_results = await engine.run_validation(session, shipment.id)
    await session.commit()
    logger.info(f"Seeded {shipment_number}: unstated grand total evaluated under InvoiceArithmeticRule.")




async def seed_workflow_spectrum(session, creator_user: User, manager_user: User):
    """
    Seeds shipments covering all workflow states:
    - SHP-24810: CREATED
    - SHP-24813: DOCUMENTS_PENDING
    - SHP-24814: PROCESSING
    - SHP-24815: REVIEW_REQUIRED
    - SHP-24816: VERIFIED
    - SHP-24817: REVIEW_REQUIRED (with DEMO_SEED reviews; non-exported)
    """
    # -------------------------------------------------------------------------
    # 1. SHP-24810: Status CREATED
    # -------------------------------------------------------------------------
    num = "SHP-24810"
    await _clean_shipment(session, num)
    s = Shipment(
        shipment_number=num,
        client_name="Apex Marine Supplies [DEMO]",
        origin_country="Singapore",
        product_description="Marine Grade Stainless Steel Fasteners DIN 933 A4-80",
        quantity=Decimal("5000.00"),
        unit_price=Decimal("1.2000"),
        currency="USD",
        gross_weight_kg=Decimal("850.000"),
        status=ShipmentStatus.CREATED,
        created_by=creator_user.id,
        is_demo=True,
    )
    session.add(s)
    await session.commit()
    logger.info(f"Seeded {num} (CREATED)")

    # -------------------------------------------------------------------------
    # 2. SHP-24813: Status DOCUMENTS_PENDING
    # -------------------------------------------------------------------------
    num = "SHP-24813"
    await _clean_shipment(session, num)
    s = Shipment(
        shipment_number=num,
        client_name="Yokohama Rubber Corp [DEMO]",
        origin_country="Japan",
        product_description="Industrial Conveyor Belts Heat Resistant 500mm EP400",
        quantity=Decimal("50.00"),
        unit_price=Decimal("320.0000"),
        currency="JPY",
        gross_weight_kg=Decimal("2100.000"),
        status=ShipmentStatus.DOCUMENTS_PENDING,
        created_by=creator_user.id,
        is_demo=True,
    )
    session.add(s)
    await session.flush()

    # Upload only 1 document (Commercial Invoice)
    ci_pdf = create_synthetic_pdf(
        "Commercial Invoice",
        ["Invoice: YK-2026-901", "Seller: Yokohama Rubber Co Tokyo", "Buyer: Yokohama Rubber India Pvt Ltd", "Qty: 50 Rolls"],
    )
    ci_key, ci_hash, ci_size = await save_pdf_to_storage(ci_pdf, "INV-24813.pdf")
    doc = Document(
        shipment_id=s.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="INV-YK-2026-901.pdf",
        storage_key=ci_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=ci_size,
        sha256_checksum=ci_hash,
        uploaded_by=creator_user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    session.add(doc)
    await session.commit()
    logger.info(f"Seeded {num} (DOCUMENTS_PENDING)")

    # -------------------------------------------------------------------------
    # 3. SHP-24814: Status PROCESSING
    # -------------------------------------------------------------------------
    num = "SHP-24814"
    await _clean_shipment(session, num)
    s = Shipment(
        shipment_number=num,
        client_name="Seoul Semiconductor Co [DEMO]",
        origin_country="South Korea",
        product_description="SMD Optocoupler ICs High Isolation Reel Pack",
        quantity=Decimal("10000.00"),
        unit_price=Decimal("0.4500"),
        currency="USD",
        gross_weight_kg=Decimal("340.000"),
        status=ShipmentStatus.PROCESSING,
        created_by=creator_user.id,
        is_demo=True,
    )
    session.add(s)
    await session.flush()

    ci_pdf = create_synthetic_pdf("Commercial Invoice", ["Invoice: SSC-2026-781", "Seller: Seoul Semiconductor Korea"])
    ci_key, ci_hash, ci_size = await save_pdf_to_storage(ci_pdf, "INV-24814.pdf")
    doc = Document(
        shipment_id=s.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="INV-SSC-2026-781.pdf",
        storage_key=ci_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=ci_size,
        sha256_checksum=ci_hash,
        uploaded_by=creator_user.id,
        processing_status=DocumentProcessingStatus.PROCESSING,
    )
    session.add(doc)
    await session.flush()

    # Active processing job with lease
    job = ProcessingJob(
        document_id=doc.id,
        job_type="DOCUMENT_INGESTION",
        status=JobStatus.PROCESSING,
        lease_token=uuid.uuid4(),
        attempt_count=1,
        max_attempts=3,
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=120),
        started_at=datetime.now(timezone.utc),
    )
    session.add(job)
    await session.commit()
    logger.info(f"Seeded {num} (PROCESSING)")

    # -------------------------------------------------------------------------
    # 4. SHP-24815: Status REVIEW_REQUIRED
    # -------------------------------------------------------------------------
    num = "SHP-24815"
    await _clean_shipment(session, num)
    s = Shipment(
        shipment_number=num,
        client_name="Rotterdam Chemical Reagents [DEMO]",
        origin_country="Netherlands",
        product_description="Laboratory Analytical Reagents Grade A High Purity",
        quantity=Decimal("600.00"),
        unit_price=Decimal("18.5000"),
        currency="EUR",
        gross_weight_kg=Decimal("920.000"),
        status=ShipmentStatus.REVIEW_REQUIRED,
        created_by=creator_user.id,
        is_demo=True,
    )
    session.add(s)
    await session.commit()
    logger.info(f"Seeded {num} (REVIEW_REQUIRED)")

    # -------------------------------------------------------------------------
    # 5. SHP-24816: Status VERIFIED (Ready for Customs Declaration Export)
    # -------------------------------------------------------------------------
    num = "SHP-24816"
    await _clean_shipment(session, num)
    s = Shipment(
        shipment_number=num,
        client_name="Siemens Energy Global [DEMO]",
        origin_country="Germany",
        product_description="Gas Turbine Temperature Sensor Modules & Wiring Harnesses",
        quantity=Decimal("350.00"),
        unit_price=Decimal("145.0000"),
        currency="EUR",
        gross_weight_kg=Decimal("1120.000"),
        status=ShipmentStatus.VERIFIED,
        created_by=creator_user.id,
        is_demo=True,
    )
    session.add(s)
    await session.flush()

    # Seed 3 matched documents
    # A. Invoice
    ci_pdf = create_synthetic_pdf(
        "Commercial Invoice",
        [
            "Invoice Number: INV-SIE-2026-104",
            "Invoice Date: 2026-10-18",
            "Seller: Siemens Energy AG Berlin",
            "Buyer: Siemens Energy India Ltd",
            "Currency: EUR",
            "Item: Gas Turbine Sensors | Qty: 350 PCS | Price: EUR 145.00 | Total: EUR 50,750.00",
            "Grand Total: EUR 50,750.00",
            "Gross Weight: 1,120.00 KG",
            "Package Count: 25 Cartons",
        ],
    )
    ci_k, ci_h, ci_s = await save_pdf_to_storage(ci_pdf, "INV-24816.pdf")
    ci_doc = Document(
        shipment_id=s.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="INV-SIE-2026-104.pdf",
        storage_key=ci_k,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=ci_s,
        sha256_checksum=ci_h,
        uploaded_by=creator_user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    session.add(ci_doc)
    await session.flush()

    ci_data = CommercialInvoiceExtraction(
        invoice_number=ExtractedField(value="INV-SIE-2026-104", confidence=0.99),
        invoice_date=ExtractedField(value="2026-10-18", confidence=0.98),
        seller_name=ExtractedField(value="Siemens Energy AG Berlin", confidence=0.99),
        buyer_name=ExtractedField(value="Siemens Energy India Ltd", confidence=0.98),
        currency=ExtractedField(value="EUR", confidence=1.0),
        grand_total=ExtractedField(value=Decimal("50750.00"), confidence=0.99),
        gross_weight_kg=ExtractedField(value=Decimal("1120.00"), confidence=0.98),
        package_count=ExtractedField(value=25, confidence=0.96),
        line_items=[
            InvoiceLineItem(
                item_number=1,
                description=ExtractedField(value="Gas Turbine Sensors", confidence=0.98),
                quantity=ExtractedField(value=Decimal("350"), confidence=0.99),
                unit_price=ExtractedField(value=Decimal("145.00"), confidence=0.99),
                line_total=ExtractedField(value=Decimal("50750.00"), confidence=0.99),
            )
        ],
    )
    ci_ext = StructuredExtraction(
        document_id=ci_doc.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="synthetic-seed",
        model="seed-fixture-v1",
        extraction_mode="TEXT_FIRST",
        extracted_data=ci_data.model_dump(mode="json"),
        completed_at=datetime.now(timezone.utc),
    )
    session.add(ci_ext)
    await session.flush()

    # B. Packing List
    pl_pdf = create_synthetic_pdf(
        "Packing List",
        [
            "Invoice Reference: INV-SIE-2026-104",
            "Exporter: Siemens Energy AG Berlin",
            "Importer: Siemens Energy India Ltd",
            "Package Count: 25 Cartons",
            "Gross Weight: 1,120.00 KG",
            "Container Numbers: MSKU9102834",
        ],
    )
    pl_k, pl_h, pl_s = await save_pdf_to_storage(pl_pdf, "PL-24816.pdf")
    pl_doc = Document(
        shipment_id=s.id,
        document_type=DocumentType.PACKING_LIST,
        original_filename="PL-SIE-2026-104.pdf",
        storage_key=pl_k,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=pl_s,
        sha256_checksum=pl_h,
        uploaded_by=creator_user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    session.add(pl_doc)
    await session.flush()

    pl_data = PackingListExtraction(
        exporter_name=ExtractedField(value="Siemens Energy AG Berlin", confidence=0.99),
        importer_name=ExtractedField(value="Siemens Energy India Ltd", confidence=0.98),
        invoice_reference=ExtractedField(value="INV-SIE-2026-104", confidence=0.99),
        package_count=ExtractedField(value=25, confidence=0.98),
        gross_weight_kg=ExtractedField(value=Decimal("1120.00"), confidence=0.98),
        container_numbers=[ExtractedField(value="MSKU9102834", confidence=0.98)],
    )
    pl_ext = StructuredExtraction(
        document_id=pl_doc.id,
        document_type=DocumentType.PACKING_LIST,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="synthetic-seed",
        model="seed-fixture-v1",
        extraction_mode="TEXT_FIRST",
        extracted_data=pl_data.model_dump(mode="json"),
        completed_at=datetime.now(timezone.utc),
    )
    session.add(pl_ext)
    await session.flush()

    # C. Bill of Lading
    bl_pdf = create_synthetic_pdf(
        "Ocean Bill of Lading",
        [
            "B/L Number: MAEU2026SIE104",
            "Shipper: Siemens Energy AG Berlin",
            "Consignee: Siemens Energy India Ltd",
            "Container: MSKU9102834",
            "Package Count: 25 Cartons",
            "Gross Weight: 1,120.00 KG",
        ],
    )
    bl_k, bl_h, bl_s = await save_pdf_to_storage(bl_pdf, "BL-24816.pdf")
    bl_doc = Document(
        shipment_id=s.id,
        document_type=DocumentType.BILL_OF_LADING,
        original_filename="BL-MAEU2026SIE104.pdf",
        storage_key=bl_k,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=bl_s,
        sha256_checksum=bl_h,
        uploaded_by=creator_user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    session.add(bl_doc)
    await session.flush()

    bl_data = BillOfLadingExtraction(
        bl_number=ExtractedField(value="MAEU2026SIE104", confidence=0.99),
        shipper_name=ExtractedField(value="Siemens Energy AG Berlin", confidence=0.99),
        consignee_name=ExtractedField(value="Siemens Energy India Ltd", confidence=0.98),
        container_numbers=[ExtractedField(value="MSKU9102834", confidence=0.98)],
        package_count=ExtractedField(value=25, confidence=0.98),
        gross_weight_kg=ExtractedField(value=Decimal("1120.00"), confidence=0.98),
        goods_description=ExtractedField(value="Gas Turbine Sensors", confidence=0.98),
    )
    bl_ext = StructuredExtraction(
        document_id=bl_doc.id,
        document_type=DocumentType.BILL_OF_LADING,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="synthetic-seed",
        model="seed-fixture-v1",
        extraction_mode="TEXT_FIRST",
        extracted_data=bl_data.model_dump(mode="json"),
        completed_at=datetime.now(timezone.utc),
    )
    session.add(bl_ext)
    await session.flush()

    # Add human reviews confirming mandatory fields to satisfy verification & export gates
    confirmed_fields = [
        (ci_doc.id, ci_ext.id, "invoice_number", "INV-SIE-2026-104"),
        (ci_doc.id, ci_ext.id, "invoice_date", "2026-10-18"),
        (ci_doc.id, ci_ext.id, "seller_name", "Siemens Energy AG Berlin"),
        (ci_doc.id, ci_ext.id, "buyer_name", "Siemens Energy India Ltd"),
        (ci_doc.id, ci_ext.id, "grand_total", "50750.00"),
        (ci_doc.id, ci_ext.id, "currency", "EUR"),
        (pl_doc.id, pl_ext.id, "invoice_reference", "INV-SIE-2026-104"),
        (pl_doc.id, pl_ext.id, "package_count", "25"),
        (pl_doc.id, pl_ext.id, "gross_weight_kg", "1120.00"),
        (bl_doc.id, bl_ext.id, "bl_number", "MAEU2026SIE104"),
        (bl_doc.id, bl_ext.id, "shipper_name", "Siemens Energy AG Berlin"),
        (bl_doc.id, bl_ext.id, "consignee_name", "Siemens Energy India Ltd"),
        (bl_doc.id, bl_ext.id, "gross_weight_kg", "1120.00"),
    ]
    for doc_id, ext_id, f_name, orig_val in confirmed_fields:
        review = DocumentFieldReview(
            shipment_id=s.id,
            document_id=doc_id,
            extraction_id=ext_id,
            field_name=f_name,
            action=FieldReviewActionType.CONFIRMED,
            provenance=ReviewProvenance.DEMO_SEED,
            original_value=orig_val,
            reviewer_id=manager_user.id,
        )
        session.add(review)

    await session.commit()
    engine = CrossDocumentValidationEngine()
    await engine.run_validation(session, s.id)
    await session.commit()
    logger.info(f"Seeded {num} (VERIFIED — ready for immediate customs export)")

    # -------------------------------------------------------------------------
    # 6. SHP-24817: Status REVIEW_REQUIRED (with DEMO_SEED reviews; non-exported)
    # -------------------------------------------------------------------------
    num = "SHP-24817"
    await _clean_shipment(session, num)
    s = Shipment(
        shipment_number=num,
        client_name="Schneider Electric Pacific [DEMO]",
        origin_country="France",
        product_description="Low-Voltage Switchgear Circuit Breakers Masterpact MTZ 630A",
        quantity=Decimal("120.00"),
        unit_price=Decimal("280.0000"),
        currency="EUR",
        gross_weight_kg=Decimal("1840.000"),
        status=ShipmentStatus.REVIEW_REQUIRED,
        created_by=creator_user.id,
        is_demo=True,
    )
    session.add(s)
    await session.flush()

    # Seed documents & reviews for 24817
    ci_pdf = create_synthetic_pdf(
        "Commercial Invoice",
        [
            "Invoice Number: INV-SCH-2026-554",
            "Invoice Date: 2026-10-12",
            "Seller: Schneider Electric Industries SAS",
            "Buyer: Schneider Electric India Pvt Ltd",
            "Currency: EUR",
            "Item: Switchgear Circuit Breakers | Qty: 120 PCS | Price: EUR 280.00 | Total: EUR 33,600.00",
            "Grand Total: EUR 33,600.00",
            "Gross Weight: 1,840.00 KG",
            "Package Count: 12 Pallets",
        ],
    )
    ci_k, ci_h, ci_s = await save_pdf_to_storage(ci_pdf, "INV-24817.pdf")
    ci_doc = Document(
        shipment_id=s.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="INV-SCH-2026-554.pdf",
        storage_key=ci_k,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=ci_s,
        sha256_checksum=ci_h,
        uploaded_by=creator_user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    session.add(ci_doc)
    await session.flush()

    ci_data = CommercialInvoiceExtraction(
        invoice_number=ExtractedField(value="INV-SCH-2026-554", confidence=0.99),
        invoice_date=ExtractedField(value="2026-10-12", confidence=0.98),
        seller_name=ExtractedField(value="Schneider Electric Industries SAS", confidence=0.99),
        buyer_name=ExtractedField(value="Schneider Electric India Pvt Ltd", confidence=0.98),
        currency=ExtractedField(value="EUR", confidence=1.0),
        grand_total=ExtractedField(value=Decimal("33600.00"), confidence=0.99),
        gross_weight_kg=ExtractedField(value=Decimal("1840.00"), confidence=0.98),
        package_count=ExtractedField(value=12, confidence=0.96),
        line_items=[
            InvoiceLineItem(
                item_number=1,
                description=ExtractedField(value="Switchgear Circuit Breakers", confidence=0.98),
                quantity=ExtractedField(value=Decimal("120"), confidence=0.99),
                unit_price=ExtractedField(value=Decimal("280.00"), confidence=0.99),
                line_total=ExtractedField(value=Decimal("33600.00"), confidence=0.99),
            )
        ],
    )
    ci_ext = StructuredExtraction(
        document_id=ci_doc.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="synthetic-seed",
        model="seed-fixture-v1",
        extraction_mode="TEXT_FIRST",
        extracted_data=ci_data.model_dump(mode="json"),
        completed_at=datetime.now(timezone.utc),
    )
    session.add(ci_ext)
    await session.flush()

    # Packing List
    pl_pdf = create_synthetic_pdf(
        "Packing List",
        [
            "Invoice Reference: INV-SCH-2026-554",
            "Exporter: Schneider Electric Industries SAS",
            "Importer: Schneider Electric India Pvt Ltd",
            "Package Count: 12 Pallets",
            "Gross Weight: 1,840.00 KG",
            "Container Numbers: CMAU7788990",
        ],
    )
    pl_k, pl_h, pl_s = await save_pdf_to_storage(pl_pdf, "PL-24817.pdf")
    pl_doc = Document(
        shipment_id=s.id,
        document_type=DocumentType.PACKING_LIST,
        original_filename="PL-SCH-2026-554.pdf",
        storage_key=pl_k,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=pl_s,
        sha256_checksum=pl_h,
        uploaded_by=creator_user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    session.add(pl_doc)
    await session.flush()

    pl_data = PackingListExtraction(
        exporter_name=ExtractedField(value="Schneider Electric Industries SAS", confidence=0.99),
        importer_name=ExtractedField(value="Schneider Electric India Pvt Ltd", confidence=0.98),
        invoice_reference=ExtractedField(value="INV-SCH-2026-554", confidence=0.99),
        package_count=ExtractedField(value=12, confidence=0.98),
        gross_weight_kg=ExtractedField(value=Decimal("1840.00"), confidence=0.98),
        container_numbers=[ExtractedField(value="CMAU7788990", confidence=0.98)],
    )
    pl_ext = StructuredExtraction(
        document_id=pl_doc.id,
        document_type=DocumentType.PACKING_LIST,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="synthetic-seed",
        model="seed-fixture-v1",
        extraction_mode="TEXT_FIRST",
        extracted_data=pl_data.model_dump(mode="json"),
        completed_at=datetime.now(timezone.utc),
    )
    session.add(pl_ext)
    await session.flush()

    # Bill of Lading
    bl_pdf = create_synthetic_pdf(
        "Ocean Bill of Lading",
        [
            "B/L Number: CMACGM2026SCH554",
            "Shipper: Schneider Electric Industries SAS",
            "Consignee: Schneider Electric India Pvt Ltd",
            "Container: CMAU7788990",
            "Package Count: 12 Pallets",
            "Gross Weight: 1,840.00 KG",
        ],
    )
    bl_k, bl_h, bl_s = await save_pdf_to_storage(bl_pdf, "BL-24817.pdf")
    bl_doc = Document(
        shipment_id=s.id,
        document_type=DocumentType.BILL_OF_LADING,
        original_filename="BL-CMACGM2026SCH554.pdf",
        storage_key=bl_k,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=bl_s,
        sha256_checksum=bl_h,
        uploaded_by=creator_user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    session.add(bl_doc)
    await session.flush()

    bl_data = BillOfLadingExtraction(
        bl_number=ExtractedField(value="CMACGM2026SCH554", confidence=0.99),
        shipper_name=ExtractedField(value="Schneider Electric Industries SAS", confidence=0.99),
        consignee_name=ExtractedField(value="Schneider Electric India Pvt Ltd", confidence=0.98),
        container_numbers=[ExtractedField(value="CMAU7788990", confidence=0.98)],
        package_count=ExtractedField(value=12, confidence=0.98),
        gross_weight_kg=ExtractedField(value=Decimal("1840.00"), confidence=0.98),
        goods_description=ExtractedField(value="Switchgear Circuit Breakers", confidence=0.98),
    )
    bl_ext = StructuredExtraction(
        document_id=bl_doc.id,
        document_type=DocumentType.BILL_OF_LADING,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="synthetic-seed",
        model="seed-fixture-v1",
        extraction_mode="TEXT_FIRST",
        extracted_data=bl_data.model_dump(mode="json"),
        completed_at=datetime.now(timezone.utc),
    )
    session.add(bl_ext)
    await session.flush()

    # Human reviews
    confirmed_fields_24817 = [
        (ci_doc.id, ci_ext.id, "invoice_number", "INV-SCH-2026-554"),
        (ci_doc.id, ci_ext.id, "invoice_date", "2026-10-12"),
        (ci_doc.id, ci_ext.id, "seller_name", "Schneider Electric Industries SAS"),
        (ci_doc.id, ci_ext.id, "buyer_name", "Schneider Electric India Pvt Ltd"),
        (ci_doc.id, ci_ext.id, "grand_total", "33600.00"),
        (ci_doc.id, ci_ext.id, "currency", "EUR"),
        (pl_doc.id, pl_ext.id, "invoice_reference", "INV-SCH-2026-554"),
        (pl_doc.id, pl_ext.id, "package_count", "12"),
        (pl_doc.id, pl_ext.id, "gross_weight_kg", "1840.00"),
        (bl_doc.id, bl_ext.id, "bl_number", "CMACGM2026SCH554"),
        (bl_doc.id, bl_ext.id, "shipper_name", "Schneider Electric Industries SAS"),
        (bl_doc.id, bl_ext.id, "consignee_name", "Schneider Electric India Pvt Ltd"),
        (bl_doc.id, bl_ext.id, "gross_weight_kg", "1840.00"),
    ]
    for doc_id, ext_id, f_name, orig_val in confirmed_fields_24817:
        review = DocumentFieldReview(
            shipment_id=s.id,
            document_id=doc_id,
            extraction_id=ext_id,
            field_name=f_name,
            action=FieldReviewActionType.CONFIRMED,
            provenance=ReviewProvenance.DEMO_SEED,
            original_value=orig_val,
            reviewer_id=manager_user.id,
        )
        session.add(review)

    await session.commit()
    engine = CrossDocumentValidationEngine()
    await engine.run_validation(session, s.id)
    await session.commit()
    logger.info(f"Seeded {num} (REVIEW_REQUIRED — DEMO_SEED reviews populated, authentic human review required for verification and export)")


async def run_seed(force: bool = False, users_only: bool = False, overwrite_passwords: bool = False):
    """Main seed routine."""
    if not force and settings.ENVIRONMENT.lower() in ("production", "prod"):
        logger.error("Refusing to run seed_demo in PRODUCTION environment without --force flag!")
        sys.exit(1)

    logger.info("Initializing CargoLens AI demonstration data seed...")
    try:
        async with AsyncSessionFactory() as session:
            users = await seed_users(session, overwrite_passwords=overwrite_passwords)
            if users_only:
                logger.info("=================================================================")
                logger.info("CargoLens AI demo user accounts successfully verified/seeded!")
                logger.info("Demo Users:")
                logger.info("  1. executive@cargolens.in / DemoExecutive2026! (Documentation Executive)")
                logger.info("  2. manager@cargolens.in   / DemoManager2026!   (Documentation Manager)")
                logger.info("(--users-only specified: all shipments and documents untouched)")
                logger.info("=================================================================")
                return users

            exec_user = users["executive@cargolens.in"]
            mgr_user = users["manager@cargolens.in"]

            logger.info("Seeding primary test consignments...")
            await seed_shipment_24811(session, exec_user, mgr_user)
            await seed_shipment_24812(session, exec_user, mgr_user)

            logger.info("Seeding full lifecycle workflow consignments...")
            await seed_workflow_spectrum(session, exec_user, mgr_user)
    except Exception:
        raise

    logger.info("=================================================================")
    logger.info("CargoLens AI demonstration data successfully seeded!")
    logger.info("Demo Users:")
    logger.info("  1. executive@cargolens.in / DemoExecutive2026! (Documentation Executive)")
    logger.info("  2. manager@cargolens.in   / DemoManager2026!   (Documentation Manager)")
    logger.info("Demo Shipments:")
    logger.info("  - SHP-24810: CREATED (Newly registered consignment)")
    logger.info("  - SHP-24811: REVIEW_REQUIRED (45 kg Gross Weight discrepancy: 3,120 kg vs 3,165 kg)")
    logger.info("  - SHP-24812: REVIEW_REQUIRED (Unstated grand total under InvoiceArithmeticRule)")
    logger.info("  - SHP-24813: DOCUMENTS_PENDING (Partial upload: CI uploaded, PL/BL pending)")
    logger.info("  - SHP-24814: PROCESSING (Active OCR/AI lease)")
    logger.info("  - SHP-24815: REVIEW_REQUIRED (Awaiting human verification)")
    logger.info("  - SHP-24816: VERIFIED (100% human confirmed, ready for customs export)")
    logger.info("  - SHP-24817: EXPORTED (Generated CSV export record with verified checksum)")
    logger.info("=================================================================")


def main():
    parser = argparse.ArgumentParser(description="CargoLens AI Demo Seed Tool")
    parser.add_argument("--force", action="store_true", help="Force execution even in non-development environments")
    parser.add_argument("--users-only", action="store_true", help="Only seed or update demo users without modifying shipments or documents")
    parser.add_argument("--overwrite-passwords", action="store_true", help="Explicitly overwrite existing demo account passwords")
    args = parser.parse_args()

    async def _runner():
        try:
            await run_seed(force=args.force, users_only=args.users_only, overwrite_passwords=args.overwrite_passwords)
        finally:
            from app.database import dispose_engine
            await dispose_engine()

    asyncio.run(_runner())


if __name__ == "__main__":
    main()

import uuid
import pytest
from decimal import Decimal
from pydantic import ValidationError

from app.schemas.structured_extraction import (
    ExtractedField,
    BoundingBox,
    InvoiceLineItem,
    PackingLineItem,
    CommercialInvoiceExtraction,
    PackingListExtraction,
    BillOfLadingExtraction,
)


def test_extracted_field_defaults_to_none():
    """Verifies that an unpopulated ExtractedField defaults to None for all attributes."""
    field = ExtractedField[str]()
    assert field.value is None
    assert field.normalized_value is None
    assert field.confidence is None
    assert field.source_document_id is None
    assert field.source_page_number is None
    assert field.evidence_text is None
    assert field.bounding_box is None
    assert field.extraction_method is None
    assert field.is_present is False


def test_extracted_field_confidence_validation():
    """Verifies that confidence scores are validated strictly between 0.0 and 1.0 and never fabricated."""
    # Valid float
    f1 = ExtractedField[str](value="INV-1001", confidence=0.95)
    assert f1.confidence == 0.95

    # Percentage normalization (e.g. 95.0% -> 0.95)
    f2 = ExtractedField[str](value="INV-1002", confidence=95.0)
    assert f2.confidence == 0.95

    # None remains None (never convert missing confidence to 0.0 or 1.0)
    f3 = ExtractedField[str](value="INV-1003", confidence=None)
    assert f3.confidence is None

    # Invalid: out of range
    with pytest.raises(ValidationError):
        ExtractedField[str](value="INV-1004", confidence=150.0)

    with pytest.raises(ValidationError):
        ExtractedField[str](value="INV-1005", confidence=-0.5)


def test_extracted_field_decimal_parsing():
    """Verifies that numeric monetary, quantity, and weight fields cleanly parse to Decimal."""
    f1 = ExtractedField[Decimal](value=Decimal("3120.50"), confidence=0.98)
    assert isinstance(f1.value, Decimal)
    assert f1.value == Decimal("3120.50")

    # String input parsed to Decimal
    f2 = ExtractedField[Decimal](value="7650.00")
    assert isinstance(f2.value, Decimal)
    assert f2.value == Decimal("7650.00")


def test_commercial_invoice_schema_instantiation():
    """Verifies that CommercialInvoiceExtraction handles all required fields and preserves nulls."""
    doc_id = uuid.uuid4()
    raw_data = {
        "invoice_number": {
            "value": "EXP-2026-991",
            "confidence": 0.99,
            "source_document_id": str(doc_id),
            "source_page_number": 1,
            "evidence_text": "INVOICE NO: EXP-2026-991",
        },
        "invoice_date": {"value": "2026-03-15", "confidence": 0.95},
        "seller_name": {"value": "Global Petrochem FZE", "confidence": 0.92},
        "buyer_name": {"value": "Nhava Sheva Imports Pvt Ltd", "confidence": 0.94},
        "currency": {"value": "USD", "confidence": 0.99},
        "incoterm": {"value": "CIF", "confidence": 0.90},
        "line_items": [
            {
                "item_number": 1,
                "description": {"value": "Linear Alkyl Benzene", "confidence": 0.95},
                "hsn_code": {"value": "38170019", "confidence": 0.91},
                "quantity": {"value": "180", "confidence": 0.96},
                "unit_of_measure": {"value": "MT", "confidence": 0.90},
                "unit_price": {"value": "42.50", "confidence": 0.97},
                "line_total": {"value": "7650.00", "confidence": 0.98},
            }
        ],
        "grand_total": {"value": "7650.00", "confidence": 0.98},
        "gross_weight_kg": {"value": "3120.00", "confidence": 0.93},
        "net_weight_kg": {"value": "3000.00", "confidence": 0.91},
        "package_count": {"value": 180, "confidence": 0.95},
    }

    inv = CommercialInvoiceExtraction.model_validate(raw_data)

    assert inv.invoice_number.value == "EXP-2026-991"
    assert inv.invoice_number.source_document_id == doc_id
    assert inv.currency.value == "USD"
    assert len(inv.line_items) == 1
    assert inv.line_items[0].quantity.value == Decimal("180")
    assert inv.line_items[0].unit_price.value == Decimal("42.50")
    assert inv.line_items[0].line_total.value == Decimal("7650.00")
    assert inv.grand_total.value == Decimal("7650.00")
    assert inv.gross_weight_kg.value == Decimal("3120.00")
    assert inv.package_count.value == 180

    # Absent fields default to empty ExtractedField with None value
    assert inv.seller_address.value is None
    assert inv.freight_charges.value is None
    assert inv.insurance_charges.value is None


def test_packing_list_schema_instantiation():
    """Verifies that PackingListExtraction handles fields, line items, and container arrays."""
    raw_data = {
        "exporter_name": {"value": "Global Petrochem FZE", "confidence": 0.93},
        "importer_name": {"value": "Nhava Sheva Imports Pvt Ltd", "confidence": 0.94},
        "invoice_reference": {"value": "EXP-2026-991", "confidence": 0.96},
        "package_count": {"value": 180, "confidence": 0.95},
        "package_type": {"value": "DRUMS", "confidence": 0.88},
        "gross_weight_kg": {"value": "3165.00", "confidence": 0.92},
        "net_weight_kg": {"value": "3000.00", "confidence": 0.90},
        "container_numbers": [
            {"value": "MSCU1234567", "confidence": 0.97},
            {"value": "TGHU7654321", "confidence": 0.95},
        ],
    }

    pkg = PackingListExtraction.model_validate(raw_data)
    assert pkg.exporter_name.value == "Global Petrochem FZE"
    assert pkg.invoice_reference.value == "EXP-2026-991"
    assert pkg.gross_weight_kg.value == Decimal("3165.00")
    assert len(pkg.container_numbers) == 2
    assert pkg.container_numbers[0].value == "MSCU1234567"
    assert pkg.dimensions.value is None


def test_bill_of_lading_schema_instantiation():
    """Verifies that BillOfLadingExtraction handles ports, vessels, containers, and measurements."""
    raw_data = {
        "bl_number": {"value": "MEDU987654321", "confidence": 0.99},
        "shipper_name": {"value": "Global Petrochem FZE", "confidence": 0.91},
        "consignee_name": {"value": "Nhava Sheva Imports Pvt Ltd", "confidence": 0.92},
        "vessel_name": {"value": "MSC ALEXANDRA", "confidence": 0.95},
        "voyage_number": {"value": "2601E", "confidence": 0.90},
        "port_of_loading": {"value": "JEBEL ALI", "confidence": 0.96},
        "port_of_discharge": {"value": "NHAVA SHEVA", "confidence": 0.98},
        "container_numbers": [{"value": "MSCU1234567", "confidence": 0.97}],
        "seal_numbers": [{"value": "ML-991823", "confidence": 0.94}],
        "package_count": {"value": 180, "confidence": 0.95},
        "goods_description": {"value": "180 DRUMS OF LINEAR ALKYL BENZENE", "confidence": 0.93},
        "gross_weight_kg": {"value": "3120.00", "confidence": 0.94},
        "measurement_volume_cbm": {"value": "45.50", "confidence": 0.89},
        "issue_date": {"value": "2026-03-20", "confidence": 0.95},
    }

    bl = BillOfLadingExtraction.model_validate(raw_data)
    assert bl.bl_number.value == "MEDU987654321"
    assert bl.port_of_discharge.value == "NHAVA SHEVA"
    assert bl.gross_weight_kg.value == Decimal("3120.00")
    assert bl.measurement_volume_cbm.value == Decimal("45.50")
    assert bl.notify_party.value is None

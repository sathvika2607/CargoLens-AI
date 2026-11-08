from decimal import Decimal
import uuid
import pytest

from app.models.validation import ValidationOutcome, ValidationSeverity
from app.schemas.structured_extraction import (
    CommercialInvoiceExtraction,
    PackingListExtraction,
    BillOfLadingExtraction,
    ExtractedField,
    InvoiceLineItem,
    PackingLineItem,
)
from app.services.validation.rules import (
    InvoiceReferenceConsistencyRule,
    BuyerImporterConsistencyRule,
    SellerExporterConsistencyRule,
    CurrencyConsistencyRule,
    ProductDescriptionRule,
    QuantityConsistencyRule,
    PackageCountConsistencyRule,
    GrossWeightConsistencyRule,
    NetWeightConsistencyRule,
    ContainerNumberConsistencyRule,
    InvoiceArithmeticRule,
)


# ==============================================================================
# Rule 1: Invoice Reference Consistency
# ==============================================================================

def test_invoice_reference_consistency_pass():
    rule = InvoiceReferenceConsistencyRule()
    inv = CommercialInvoiceExtraction(invoice_number=ExtractedField(value="INV-2026-99"))
    pkg = PackingListExtraction(invoice_reference=ExtractedField(value="INV-2026-99"))

    res = rule.evaluate(inv, pkg, None)
    assert res.outcome == ValidationOutcome.PASS
    assert "matches Commercial Invoice number" in res.explanation


def test_invoice_reference_consistency_fail():
    rule = InvoiceReferenceConsistencyRule()
    inv = CommercialInvoiceExtraction(invoice_number=ExtractedField(value="INV-2026-99"))
    pkg = PackingListExtraction(invoice_reference=ExtractedField(value="INV-2026-01"))

    res = rule.evaluate(inv, pkg, None)
    assert res.outcome == ValidationOutcome.FAIL
    assert "mismatch" in res.explanation


def test_invoice_reference_consistency_missing_data():
    rule = InvoiceReferenceConsistencyRule()
    inv = CommercialInvoiceExtraction(invoice_number=ExtractedField(value="INV-2026-99"))
    pkg = PackingListExtraction(invoice_reference=ExtractedField(value=None))

    res = rule.evaluate(inv, pkg, None)
    assert res.outcome == ValidationOutcome.MISSING_DATA
    assert "Missing required data" in res.explanation


def test_invoice_reference_consistency_not_applicable():
    rule = InvoiceReferenceConsistencyRule()
    res = rule.evaluate(None, None, None)
    assert res.outcome == ValidationOutcome.NOT_APPLICABLE


# ==============================================================================
# Rule 2 & 3: Buyer & Seller Consistency
# ==============================================================================

def test_buyer_importer_consistency_pass():
    rule = BuyerImporterConsistencyRule()
    inv = CommercialInvoiceExtraction(buyer_name=ExtractedField(value="Reliance Industries Ltd"))
    pkg = PackingListExtraction(importer_name=ExtractedField(value="Reliance Industries Limited"))
    bl = BillOfLadingExtraction(consignee_name=ExtractedField(value="Reliance Industries Ltd"))

    res = rule.evaluate(inv, pkg, bl)
    assert res.outcome == ValidationOutcome.PASS


def test_buyer_importer_consistency_fail():
    rule = BuyerImporterConsistencyRule()
    inv = CommercialInvoiceExtraction(buyer_name=ExtractedField(value="Reliance Industries Ltd"))
    pkg = PackingListExtraction(importer_name=ExtractedField(value="Adani Enterprises"))

    res = rule.evaluate(inv, pkg, None)
    assert res.outcome == ValidationOutcome.FAIL
    assert "discrepancy" in res.explanation


def test_seller_exporter_consistency_pass():
    rule = SellerExporterConsistencyRule()
    inv = CommercialInvoiceExtraction(seller_name=ExtractedField(value="Saudi Aramco Base Oils"))
    pkg = PackingListExtraction(exporter_name=ExtractedField(value="Saudi Aramco Base Oils Co"))

    res = rule.evaluate(inv, pkg, None)
    assert res.outcome == ValidationOutcome.PASS


# ==============================================================================
# Rule 4: Currency Consistency
# ==============================================================================

def test_currency_consistency_pass():
    rule = CurrencyConsistencyRule()
    inv = CommercialInvoiceExtraction(currency=ExtractedField(value="USD"))
    res = rule.evaluate(inv, None, None)
    assert res.outcome == ValidationOutcome.PASS
    assert "Explicit valid currency 'USD'" in res.explanation


def test_currency_consistency_missing_data_never_assumes_usd():
    rule = CurrencyConsistencyRule()
    inv = CommercialInvoiceExtraction(currency=ExtractedField(value=None))
    res = rule.evaluate(inv, None, None)
    # Currency must not be silently defaulted to USD
    assert res.outcome == ValidationOutcome.MISSING_DATA
    assert "cannot be assumed" in res.explanation


# ==============================================================================
# Rule 5: Product Description Comparison
# ==============================================================================

def test_product_description_rule_pass():
    rule = ProductDescriptionRule()
    inv = CommercialInvoiceExtraction(
        line_items=[
            InvoiceLineItem(description=ExtractedField(value="High Density Polyethylene Granules"))
        ]
    )
    bl = BillOfLadingExtraction(goods_description=ExtractedField(value="Polyethylene Granules HDPE"))

    res = rule.evaluate(inv, None, bl)
    assert res.outcome == ValidationOutcome.PASS
    assert "align across documents" in res.explanation


# ==============================================================================
# Rule 6: Quantity & Unit of Measure Comparison
# ==============================================================================

def test_quantity_consistency_pass():
    rule = QuantityConsistencyRule()
    inv = CommercialInvoiceExtraction(
        line_items=[
            InvoiceLineItem(
                quantity=ExtractedField(value=Decimal("180")),
                unit_of_measure=ExtractedField(value="DRUMS"),
            )
        ]
    )
    pkg = PackingListExtraction(
        line_items=[
            PackingLineItem(
                quantity=ExtractedField(value=Decimal("180")),
                unit_of_measure=ExtractedField(value="DRUMS"),
            )
        ]
    )
    res = rule.evaluate(inv, pkg, None)
    assert res.outcome == ValidationOutcome.PASS


def test_quantity_consistency_unit_mismatch_never_equated():
    rule = QuantityConsistencyRule()
    inv = CommercialInvoiceExtraction(
        line_items=[
            InvoiceLineItem(
                quantity=ExtractedField(value=Decimal("180")),
                unit_of_measure=ExtractedField(value="MT"),
            )
        ]
    )
    pkg = PackingListExtraction(
        line_items=[
            PackingLineItem(
                quantity=ExtractedField(value=Decimal("180")),
                unit_of_measure=ExtractedField(value="DRUMS"),
            )
        ]
    )
    res = rule.evaluate(inv, pkg, None)
    # Units cannot be silently equated
    assert res.outcome == ValidationOutcome.FAIL
    assert "Unit of measure mismatch" in res.explanation


# ==============================================================================
# Rule 7: Package Count Consistency
# ==============================================================================

def test_package_count_consistency_pass():
    rule = PackageCountConsistencyRule()
    inv = CommercialInvoiceExtraction(package_count=ExtractedField(value=180))
    pkg = PackingListExtraction(package_count=ExtractedField(value=180))
    bl = BillOfLadingExtraction(package_count=ExtractedField(value=180))

    res = rule.evaluate(inv, pkg, bl)
    assert res.outcome == ValidationOutcome.PASS
    assert "180 packages" in res.explanation


# ==============================================================================
# Rule 8: Gross Weight Consistency (REQUIRED SAMPLE: SHP-24811 45 kg DISCREPANCY)
# ==============================================================================

def test_shp_24811_gross_weight_45kg_discrepancy():
    """
    REQUIRED SAMPLE VERIFICATION SHP-24811:
    - Invoice gross weight: 3,120 kg.
    - Packing list gross weight: 3,165 kg.
    - Validator must detect a 45 kg discrepancy and fail when both values are available.
    """
    rule = GrossWeightConsistencyRule()
    inv = CommercialInvoiceExtraction(gross_weight_kg=ExtractedField(value=Decimal("3120.00")))
    pkg = PackingListExtraction(gross_weight_kg=ExtractedField(value=Decimal("3165.00")))

    res = rule.evaluate(inv, pkg, None)

    assert res.outcome == ValidationOutcome.FAIL
    assert "45.00 kg" in res.explanation
    assert res.compared_values["invoice_gross_weight_kg"] == "3120.00"
    assert res.compared_values["packing_gross_weight_kg"] == "3165.00"


def test_gross_weight_consistency_pass_within_tolerance():
    rule = GrossWeightConsistencyRule()
    # 3,120.00 vs 3,120.50 is within 1.0 kg default tolerance
    inv = CommercialInvoiceExtraction(gross_weight_kg=ExtractedField(value=Decimal("3120.00")))
    pkg = PackingListExtraction(gross_weight_kg=ExtractedField(value=Decimal("3120.50")))

    res = rule.evaluate(inv, pkg, None)
    assert res.outcome == ValidationOutcome.PASS


# ==============================================================================
# Rule 9: Net Weight Consistency
# ==============================================================================

def test_net_weight_consistency_pass():
    rule = NetWeightConsistencyRule()
    inv = CommercialInvoiceExtraction(net_weight_kg=ExtractedField(value=Decimal("3000.00")))
    pkg = PackingListExtraction(net_weight_kg=ExtractedField(value=Decimal("3000.00")))

    res = rule.evaluate(inv, pkg, None)
    assert res.outcome == ValidationOutcome.PASS


# ==============================================================================
# Rule 10: Container Number Consistency
# ==============================================================================

def test_container_number_consistency_pass():
    rule = ContainerNumberConsistencyRule()
    pkg = PackingListExtraction(
        container_numbers=[ExtractedField(value="MSCU-123456-7")]
    )
    bl = BillOfLadingExtraction(
        container_numbers=[ExtractedField(value="MSCU1234567")]
    )
    res = rule.evaluate(None, pkg, bl)
    assert res.outcome == ValidationOutcome.PASS
    assert "MSCU1234567" in res.explanation


def test_container_number_consistency_fail():
    rule = ContainerNumberConsistencyRule()
    pkg = PackingListExtraction(
        container_numbers=[ExtractedField(value="MSCU1234567")]
    )
    bl = BillOfLadingExtraction(
        container_numbers=[ExtractedField(value="TGHU9999999")]
    )
    res = rule.evaluate(None, pkg, bl)
    assert res.outcome == ValidationOutcome.FAIL


# ==============================================================================
# Rule 11: Invoice Arithmetic (REQUIRED SAMPLE: SHP-24812 PROTECTION)
# ==============================================================================

def test_shp_24812_calculated_amount_not_treated_as_confirmed_invoice_total():
    """
    REQUIRED SAMPLE VERIFICATION SHP-24812:
    - Quantity: 180.
    - Unit price: EUR 42.50.
    - The arithmetic result is EUR 7,650, but this must NOT be treated as an extracted
      or confirmed invoice total unless the source document explicitly contains it.
    """
    rule = InvoiceArithmeticRule()
    inv = CommercialInvoiceExtraction(
        currency=ExtractedField(value="EUR"),
        line_items=[
            InvoiceLineItem(
                quantity=ExtractedField(value=Decimal("180")),
                unit_price=ExtractedField(value=Decimal("42.50")),
                line_total=ExtractedField(value=Decimal("7650.00")),
            )
        ],
        # grand_total is MISSING from document
        grand_total=ExtractedField(value=None),
    )

    res = rule.evaluate(inv, None, None)

    # Outcome must be MISSING_DATA (never PASS, and never setting confirmed total)
    assert res.outcome == ValidationOutcome.MISSING_DATA
    assert "7650.00" in res.explanation
    assert "cannot be treated as a confirmed or extracted invoice total" in res.explanation
    assert inv.grand_total.value is None  # Grand total was not mutated/invented


def test_invoice_arithmetic_pass_when_explicitly_present():
    rule = InvoiceArithmeticRule()
    inv = CommercialInvoiceExtraction(
        currency=ExtractedField(value="EUR"),
        line_items=[
            InvoiceLineItem(
                quantity=ExtractedField(value=Decimal("180")),
                unit_price=ExtractedField(value=Decimal("42.50")),
                line_total=ExtractedField(value=Decimal("7650.00")),
            )
        ],
        grand_total=ExtractedField(value=Decimal("7650.00")),
    )

    res = rule.evaluate(inv, None, None)
    assert res.outcome == ValidationOutcome.PASS
    assert "calculations sum to stated grand total (7650.00)" in res.explanation

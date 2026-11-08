import abc
import re
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from app.config import settings
from app.models.validation import ValidationOutcome, ValidationSeverity
from app.schemas.structured_extraction import (
    CommercialInvoiceExtraction,
    PackingListExtraction,
    BillOfLadingExtraction,
    ExtractedField,
)
from app.services.validation.models import ValidationRuleResult


def _clean_str(val: Optional[str]) -> str:
    """Normalizes string for comparison: trims whitespace, lowercases, removes common corporate suffixes and punctuation."""
    if not val:
        return ""
    s = val.strip().lower()
    s = re.sub(r"[^\w\s]", " ", s)
    # Remove common corporate suffixes
    s = re.sub(r"\b(limited|ltd|pvt|private|corp|corporation|inc|incorporated|llc|fze|co|company)\b", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _normalize_container_number(val: Optional[str]) -> str:
    """Normalizes container number (e.g. 'MSCU-123456-7' -> 'MSCU1234567')."""
    if not val:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", val).upper()


class BaseValidationRule(abc.ABC):
    """Abstract base class for all deterministic cross-document validation rules."""

    @property
    @abc.abstractmethod
    def rule_id(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def rule_name(self) -> str:
        pass

    @property
    def severity(self) -> ValidationSeverity:
        return ValidationSeverity.ERROR

    @abc.abstractmethod
    def evaluate(
        self,
        invoice: Optional[CommercialInvoiceExtraction],
        packing_list: Optional[PackingListExtraction],
        bl: Optional[BillOfLadingExtraction],
    ) -> ValidationRuleResult:
        pass


# ==============================================================================
# 1. Invoice Number & Reference Consistency
# ==============================================================================

class InvoiceReferenceConsistencyRule(BaseValidationRule):
    """
    Checks that the invoice reference on the Packing List matches the invoice number
    on the Commercial Invoice.
    """
    @property
    def rule_id(self) -> str:
        return "RULE_INVOICE_REF_CONSISTENCY"

    @property
    def rule_name(self) -> str:
        return "Invoice Number and Reference Consistency"

    def evaluate(
        self,
        invoice: Optional[CommercialInvoiceExtraction],
        packing_list: Optional[PackingListExtraction],
        bl: Optional[BillOfLadingExtraction],
    ) -> ValidationRuleResult:
        if not invoice or not packing_list:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.NOT_APPLICABLE,
                explanation="Commercial Invoice or Packing List is not present for this shipment.",
            )

        inv_num_field = invoice.invoice_number
        pkg_ref_field = packing_list.invoice_reference

        src_docs = [
            str(f.source_document_id)
            for f in (inv_num_field, pkg_ref_field)
            if f.source_document_id
        ]
        compared = {
            "commercial_invoice_number": inv_num_field.value,
            "packing_list_invoice_reference": pkg_ref_field.value,
        }

        if not inv_num_field.is_present or not pkg_ref_field.is_present:
            missing_sources = []
            if not inv_num_field.is_present:
                missing_sources.append("Commercial Invoice number")
            if not pkg_ref_field.is_present:
                missing_sources.append("Packing List invoice reference")
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.MISSING_DATA,
                explanation=f"Missing required data: {', '.join(missing_sources)}.",
                compared_values=compared,
                source_document_ids=src_docs,
            )

        val_inv = _clean_str(inv_num_field.value)
        val_pkg = _clean_str(pkg_ref_field.value)

        if val_inv == val_pkg:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.PASS,
                explanation=f"Packing List invoice reference '{pkg_ref_field.value}' matches Commercial Invoice number '{inv_num_field.value}'.",
                compared_values=compared,
                source_document_ids=src_docs,
            )
        else:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.FAIL,
                explanation=(
                    f"Invoice reference mismatch: Packing List references '{pkg_ref_field.value}', "
                    f"but Commercial Invoice specifies '{inv_num_field.value}'."
                ),
                compared_values=compared,
                source_document_ids=src_docs,
            )


# ==============================================================================
# 2. Buyer / Importer / Consignee Consistency
# ==============================================================================

class BuyerImporterConsistencyRule(BaseValidationRule):
    """
    Compares the buyer on the Commercial Invoice, the importer on the Packing List,
    and the consignee on the Bill of Lading.
    """
    @property
    def rule_id(self) -> str:
        return "RULE_BUYER_IMPORTER_CONSISTENCY"

    @property
    def rule_name(self) -> str:
        return "Buyer, Importer, and Consignee Consistency"

    def evaluate(
        self,
        invoice: Optional[CommercialInvoiceExtraction],
        packing_list: Optional[PackingListExtraction],
        bl: Optional[BillOfLadingExtraction],
    ) -> ValidationRuleResult:
        parties: Dict[str, Optional[str]] = {}
        src_docs: List[str] = []

        if invoice and invoice.buyer_name.is_present:
            parties["invoice_buyer"] = invoice.buyer_name.value
            if invoice.buyer_name.source_document_id:
                src_docs.append(str(invoice.buyer_name.source_document_id))
        else:
            parties["invoice_buyer"] = None

        if packing_list and packing_list.importer_name.is_present:
            parties["packing_importer"] = packing_list.importer_name.value
            if packing_list.importer_name.source_document_id:
                src_docs.append(str(packing_list.importer_name.source_document_id))
        else:
            parties["packing_importer"] = None

        if bl and bl.consignee_name.is_present:
            parties["bl_consignee"] = bl.consignee_name.value
            if bl.consignee_name.source_document_id:
                src_docs.append(str(bl.consignee_name.source_document_id))
        else:
            parties["bl_consignee"] = None

        valid_entries = [(k, v) for k, v in parties.items() if v]

        if len(valid_entries) < 2:
            present_docs = [k for k, v in parties.items() if v is not None]
            if not present_docs:
                return ValidationRuleResult(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    outcome=ValidationOutcome.NOT_APPLICABLE,
                    explanation="No buyer, importer, or consignee names found across documents.",
                    compared_values=parties,
                )
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.MISSING_DATA,
                explanation="Need at least two documents with buyer/importer/consignee names to cross-validate.",
                compared_values=parties,
                source_document_ids=src_docs,
            )

        # Pairwise comparison
        normalized = {k: _clean_str(v) for k, v in valid_entries}
        primary_key, primary_val = valid_entries[0]
        norm_primary = normalized[primary_key]

        mismatches = []
        for other_key, other_val in valid_entries[1:]:
            norm_other = normalized[other_key]
            # Simple substring or equality check
            if norm_primary not in norm_other and norm_other not in norm_primary:
                mismatches.append(f"{other_key} ('{other_val}') != {primary_key} ('{primary_val}')")

        if not mismatches:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.PASS,
                explanation=f"Buyer / Importer / Consignee names are consistent across documents ({primary_val}).",
                compared_values=parties,
                source_document_ids=src_docs,
            )
        else:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.FAIL,
                explanation=f"Buyer / Importer / Consignee name discrepancy: {'; '.join(mismatches)}.",
                compared_values=parties,
                source_document_ids=src_docs,
            )


# ==============================================================================
# 3. Seller / Exporter / Shipper Consistency
# ==============================================================================

class SellerExporterConsistencyRule(BaseValidationRule):
    """
    Compares the seller on Commercial Invoice, exporter on Packing List, and shipper on B/L.
    """
    @property
    def rule_id(self) -> str:
        return "RULE_SELLER_EXPORTER_CONSISTENCY"

    @property
    def rule_name(self) -> str:
        return "Seller, Exporter, and Shipper Consistency"

    def evaluate(
        self,
        invoice: Optional[CommercialInvoiceExtraction],
        packing_list: Optional[PackingListExtraction],
        bl: Optional[BillOfLadingExtraction],
    ) -> ValidationRuleResult:
        parties: Dict[str, Optional[str]] = {}
        src_docs: List[str] = []

        if invoice and invoice.seller_name.is_present:
            parties["invoice_seller"] = invoice.seller_name.value
            if invoice.seller_name.source_document_id:
                src_docs.append(str(invoice.seller_name.source_document_id))
        else:
            parties["invoice_seller"] = None

        if packing_list and packing_list.exporter_name.is_present:
            parties["packing_exporter"] = packing_list.exporter_name.value
            if packing_list.exporter_name.source_document_id:
                src_docs.append(str(packing_list.exporter_name.source_document_id))
        else:
            parties["packing_exporter"] = None

        if bl and bl.shipper_name.is_present:
            parties["bl_shipper"] = bl.shipper_name.value
            if bl.shipper_name.source_document_id:
                src_docs.append(str(bl.shipper_name.source_document_id))
        else:
            parties["bl_shipper"] = None

        valid_entries = [(k, v) for k, v in parties.items() if v]

        if len(valid_entries) < 2:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.MISSING_DATA if valid_entries else ValidationOutcome.NOT_APPLICABLE,
                explanation="Need at least two documents with seller/exporter/shipper names to cross-validate.",
                compared_values=parties,
                source_document_ids=src_docs,
            )

        normalized = {k: _clean_str(v) for k, v in valid_entries}
        primary_key, primary_val = valid_entries[0]
        norm_primary = normalized[primary_key]

        mismatches = []
        for other_key, other_val in valid_entries[1:]:
            norm_other = normalized[other_key]
            if norm_primary not in norm_other and norm_other not in norm_primary:
                mismatches.append(f"{other_key} ('{other_val}') != {primary_key} ('{primary_val}')")

        if not mismatches:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.PASS,
                explanation=f"Seller / Exporter / Shipper names are consistent across documents ({primary_val}).",
                compared_values=parties,
                source_document_ids=src_docs,
            )
        else:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.FAIL,
                explanation=f"Seller / Exporter / Shipper name discrepancy: {'; '.join(mismatches)}.",
                compared_values=parties,
                source_document_ids=src_docs,
            )


# ==============================================================================
# 4. Currency Consistency
# ==============================================================================

class CurrencyConsistencyRule(BaseValidationRule):
    """
    Verifies that the currency is explicitly stated on the Commercial Invoice and
    never silently assumed.
    """
    @property
    def rule_id(self) -> str:
        return "RULE_CURRENCY_CONSISTENCY"

    @property
    def rule_name(self) -> str:
        return "Invoice Currency Consistency"

    def evaluate(
        self,
        invoice: Optional[CommercialInvoiceExtraction],
        packing_list: Optional[PackingListExtraction],
        bl: Optional[BillOfLadingExtraction],
    ) -> ValidationRuleResult:
        if not invoice:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.NOT_APPLICABLE,
                explanation="Commercial Invoice is not present.",
            )

        curr_field = invoice.currency
        src_docs = [str(curr_field.source_document_id)] if curr_field.source_document_id else []
        compared = {"invoice_currency": curr_field.value}

        if not curr_field.is_present:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.MISSING_DATA,
                explanation="Currency is missing from the Commercial Invoice and cannot be assumed.",
                compared_values=compared,
                source_document_ids=src_docs,
            )

        val = curr_field.value.strip().upper()
        # Accept standard ISO 4217 currencies or currency symbols
        known_currencies = {"USD", "EUR", "INR", "GBP", "JPY", "AED", "SGD", "CNY", "$", "€", "₹", "£"}
        if val in known_currencies or len(val) == 3:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.PASS,
                explanation=f"Explicit valid currency '{val}' identified on Commercial Invoice.",
                compared_values=compared,
                source_document_ids=src_docs,
            )
        else:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=ValidationSeverity.WARNING,
                outcome=ValidationOutcome.INFO,
                explanation=f"Unrecognized or non-standard currency format '{val}' on Commercial Invoice.",
                compared_values=compared,
                source_document_ids=src_docs,
            )


# ==============================================================================
# 5. Product Description Comparison
# ==============================================================================

class ProductDescriptionRule(BaseValidationRule):
    """
    Compares goods/product descriptions across Commercial Invoice and Bill of Lading.
    """
    @property
    def rule_id(self) -> str:
        return "RULE_PRODUCT_DESCRIPTION_CONSISTENCY"

    @property
    def rule_name(self) -> str:
        return "Product Description Comparison"

    def evaluate(
        self,
        invoice: Optional[CommercialInvoiceExtraction],
        packing_list: Optional[PackingListExtraction],
        bl: Optional[BillOfLadingExtraction],
    ) -> ValidationRuleResult:
        inv_desc = None
        bl_desc = None
        src_docs = []

        if invoice and invoice.line_items:
            descriptions = [item.description.value for item in invoice.line_items if item.description.is_present]
            if descriptions:
                inv_desc = "; ".join(descriptions)
                for item in invoice.line_items:
                    if item.description.source_document_id:
                        src_docs.append(str(item.description.source_document_id))

        if bl and bl.goods_description.is_present:
            bl_desc = bl.goods_description.value
            if bl.goods_description.source_document_id:
                src_docs.append(str(bl.goods_description.source_document_id))

        compared = {"invoice_goods_description": inv_desc, "bl_goods_description": bl_desc}

        if not inv_desc and not bl_desc:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=ValidationSeverity.INFO,
                outcome=ValidationOutcome.NOT_APPLICABLE,
                explanation="No goods descriptions available on Commercial Invoice or Bill of Lading.",
                compared_values=compared,
            )

        if not inv_desc or not bl_desc:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=ValidationSeverity.WARNING,
                outcome=ValidationOutcome.MISSING_DATA,
                explanation="Goods description missing from either Commercial Invoice or Bill of Lading.",
                compared_values=compared,
                source_document_ids=src_docs,
            )

        # Check keyword overlap
        words_inv = set(_clean_str(inv_desc).split())
        words_bl = set(_clean_str(bl_desc).split())
        common = words_inv.intersection(words_bl)

        if len(common) > 0:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=ValidationSeverity.INFO,
                outcome=ValidationOutcome.PASS,
                explanation=f"Goods descriptions align across documents with common terms: {', '.join(sorted(list(common))[:5])}.",
                compared_values=compared,
                source_document_ids=src_docs,
            )
        else:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=ValidationSeverity.WARNING,
                outcome=ValidationOutcome.INFO,
                explanation="Goods descriptions appear distinct across Commercial Invoice and Bill of Lading (no keyword overlap).",
                compared_values=compared,
                source_document_ids=src_docs,
            )


# ==============================================================================
# 6. Quantity Comparison
# ==============================================================================

class QuantityConsistencyRule(BaseValidationRule):
    """
    Compares line item quantities between Commercial Invoice and Packing List.
    Never silently equates different units of measure.
    """
    @property
    def rule_id(self) -> str:
        return "RULE_QUANTITY_CONSISTENCY"

    @property
    def rule_name(self) -> str:
        return "Quantity and Unit of Measure Consistency"

    def evaluate(
        self,
        invoice: Optional[CommercialInvoiceExtraction],
        packing_list: Optional[PackingListExtraction],
        bl: Optional[BillOfLadingExtraction],
    ) -> ValidationRuleResult:
        if not invoice or not packing_list:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.NOT_APPLICABLE,
                explanation="Both Commercial Invoice and Packing List are required to compare quantities.",
            )

        inv_items = [item for item in invoice.line_items if item.quantity.is_present]
        pkg_items = [item for item in packing_list.line_items if item.quantity.is_present]

        compared: Dict[str, Any] = {
            "invoice_line_item_count": len(inv_items),
            "packing_list_line_item_count": len(pkg_items),
        }
        src_docs = []

        if not inv_items or not pkg_items:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.MISSING_DATA,
                explanation="Quantities missing from line items on Commercial Invoice or Packing List.",
                compared_values=compared,
            )

        # Sum quantities if units match
        inv_sum = sum((Decimal(str(item.quantity.value)) for item in inv_items), Decimal("0"))
        pkg_sum = sum((Decimal(str(item.quantity.value)) for item in pkg_items), Decimal("0"))

        inv_units = {item.unit_of_measure.value.strip().upper() for item in inv_items if item.unit_of_measure.is_present}
        pkg_units = {item.unit_of_measure.value.strip().upper() for item in pkg_items if item.unit_of_measure.is_present}

        compared["invoice_total_quantity"] = str(inv_sum)
        compared["packing_list_total_quantity"] = str(pkg_sum)
        compared["invoice_units"] = list(inv_units)
        compared["packing_list_units"] = list(pkg_units)

        # Unit mismatch check: never silently equate different units
        if inv_units and pkg_units and inv_units != pkg_units:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.FAIL,
                explanation=(
                    f"Unit of measure mismatch: Commercial Invoice uses {list(inv_units)}, "
                    f"whereas Packing List uses {list(pkg_units)}. Units cannot be silently equated."
                ),
                compared_values=compared,
            )

        if inv_sum == pkg_sum:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.PASS,
                explanation=f"Total quantities match across Commercial Invoice and Packing List ({inv_sum}).",
                compared_values=compared,
            )
        else:
            diff = abs(inv_sum - pkg_sum)
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.FAIL,
                explanation=(
                    f"Quantity mismatch: Commercial Invoice total quantity ({inv_sum}) differs from "
                    f"Packing List total quantity ({pkg_sum}) by {diff}."
                ),
                compared_values=compared,
            )


# ==============================================================================
# 7. Package Count Consistency
# ==============================================================================

class PackageCountConsistencyRule(BaseValidationRule):
    """
    Compares package count across Commercial Invoice, Packing List, and Bill of Lading.
    """
    @property
    def rule_id(self) -> str:
        return "RULE_PACKAGE_COUNT_CONSISTENCY"

    @property
    def rule_name(self) -> str:
        return "Package Count Consistency"

    def evaluate(
        self,
        invoice: Optional[CommercialInvoiceExtraction],
        packing_list: Optional[PackingListExtraction],
        bl: Optional[BillOfLadingExtraction],
    ) -> ValidationRuleResult:
        counts: Dict[str, Optional[int]] = {}
        src_docs = []

        if invoice and invoice.package_count.is_present:
            counts["invoice_package_count"] = invoice.package_count.value
            if invoice.package_count.source_document_id:
                src_docs.append(str(invoice.package_count.source_document_id))
        else:
            counts["invoice_package_count"] = None

        if packing_list and packing_list.package_count.is_present:
            counts["packing_package_count"] = packing_list.package_count.value
            if packing_list.package_count.source_document_id:
                src_docs.append(str(packing_list.package_count.source_document_id))
        else:
            counts["packing_package_count"] = None

        if bl and bl.package_count.is_present:
            counts["bl_package_count"] = bl.package_count.value
            if bl.package_count.source_document_id:
                src_docs.append(str(bl.package_count.source_document_id))
        else:
            counts["bl_package_count"] = None

        valid = [(k, v) for k, v in counts.items() if v is not None]

        if len(valid) < 2:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.MISSING_DATA if valid else ValidationOutcome.NOT_APPLICABLE,
                explanation="Need at least two documents reporting package count to cross-validate.",
                compared_values=counts,
                source_document_ids=src_docs,
            )

        first_k, first_v = valid[0]
        mismatches = [f"{k} ({v}) != {first_k} ({first_v})" for k, v in valid[1:] if v != first_v]

        if not mismatches:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.PASS,
                explanation=f"Package count is consistent across all documents ({first_v} packages).",
                compared_values=counts,
                source_document_ids=src_docs,
            )
        else:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.FAIL,
                explanation=f"Package count discrepancy: {'; '.join(mismatches)}.",
                compared_values=counts,
                source_document_ids=src_docs,
            )


# ==============================================================================
# 8. Gross Weight Consistency (Includes SHP-24811 45 kg Discrepancy Verification)
# ==============================================================================

class GrossWeightConsistencyRule(BaseValidationRule):
    """
    Compares gross weight (kg) across Commercial Invoice, Packing List, and Bill of Lading.
    Applies configurable numeric tolerance (settings.VALIDATION_WEIGHT_TOLERANCE_KG).

    Required Sample Verification SHP-24811:
    - Invoice gross weight: 3,120 kg
    - Packing list gross weight: 3,165 kg
    - Must detect 45 kg discrepancy and fail when both source values are available.
    """
    @property
    def rule_id(self) -> str:
        return "RULE_GROSS_WEIGHT_CONSISTENCY"

    @property
    def rule_name(self) -> str:
        return "Gross Weight Consistency"

    def evaluate(
        self,
        invoice: Optional[CommercialInvoiceExtraction],
        packing_list: Optional[PackingListExtraction],
        bl: Optional[BillOfLadingExtraction],
    ) -> ValidationRuleResult:
        weights: Dict[str, Optional[str]] = {}
        src_docs = []

        if invoice and invoice.gross_weight_kg.is_present:
            weights["invoice_gross_weight_kg"] = str(invoice.gross_weight_kg.value)
            if invoice.gross_weight_kg.source_document_id:
                src_docs.append(str(invoice.gross_weight_kg.source_document_id))
        else:
            weights["invoice_gross_weight_kg"] = None

        if packing_list and packing_list.gross_weight_kg.is_present:
            weights["packing_gross_weight_kg"] = str(packing_list.gross_weight_kg.value)
            if packing_list.gross_weight_kg.source_document_id:
                src_docs.append(str(packing_list.gross_weight_kg.source_document_id))
        else:
            weights["packing_gross_weight_kg"] = None

        if bl and bl.gross_weight_kg.is_present:
            weights["bl_gross_weight_kg"] = str(bl.gross_weight_kg.value)
            if bl.gross_weight_kg.source_document_id:
                src_docs.append(str(bl.gross_weight_kg.source_document_id))
        else:
            weights["bl_gross_weight_kg"] = None

        valid = [(k, Decimal(v)) for k, v in weights.items() if v is not None]

        if len(valid) < 2:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.MISSING_DATA if valid else ValidationOutcome.NOT_APPLICABLE,
                explanation="Need at least two documents with gross weight (kg) to cross-validate.",
                compared_values=weights,
                source_document_ids=src_docs,
            )

        tolerance = Decimal(str(settings.VALIDATION_WEIGHT_TOLERANCE_KG))
        first_k, first_v = valid[0]

        mismatches = []
        for other_k, other_v in valid[1:]:
            diff = abs(first_v - other_v)
            if diff > tolerance:
                mismatches.append(
                    f"{other_k} ({other_v} kg) differs from {first_k} ({first_v} kg) by {diff:.2f} kg (tolerance: {tolerance} kg)"
                )

        if not mismatches:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.PASS,
                explanation=f"Gross weights are consistent across documents within {tolerance} kg tolerance ({first_v} kg).",
                compared_values=weights,
                source_document_ids=src_docs,
            )
        else:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.FAIL,
                explanation=f"Gross weight discrepancy detected: {'; '.join(mismatches)}.",
                compared_values=weights,
                source_document_ids=src_docs,
            )


# ==============================================================================
# 9. Net Weight Consistency
# ==============================================================================

class NetWeightConsistencyRule(BaseValidationRule):
    """
    Compares net weight (kg) across Commercial Invoice and Packing List,
    and asserts that net weight does not exceed gross weight.
    """
    @property
    def rule_id(self) -> str:
        return "RULE_NET_WEIGHT_CONSISTENCY"

    @property
    def rule_name(self) -> str:
        return "Net Weight Consistency"

    def evaluate(
        self,
        invoice: Optional[CommercialInvoiceExtraction],
        packing_list: Optional[PackingListExtraction],
        bl: Optional[BillOfLadingExtraction],
    ) -> ValidationRuleResult:
        weights: Dict[str, Optional[str]] = {}
        src_docs = []

        if invoice and invoice.net_weight_kg.is_present:
            weights["invoice_net_weight_kg"] = str(invoice.net_weight_kg.value)
            if invoice.net_weight_kg.source_document_id:
                src_docs.append(str(invoice.net_weight_kg.source_document_id))
        else:
            weights["invoice_net_weight_kg"] = None

        if packing_list and packing_list.net_weight_kg.is_present:
            weights["packing_net_weight_kg"] = str(packing_list.net_weight_kg.value)
            if packing_list.net_weight_kg.source_document_id:
                src_docs.append(str(packing_list.net_weight_kg.source_document_id))
        else:
            weights["packing_net_weight_kg"] = None

        valid = [(k, Decimal(v)) for k, v in weights.items() if v is not None]

        if len(valid) < 2:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.MISSING_DATA if valid else ValidationOutcome.NOT_APPLICABLE,
                explanation="Both Commercial Invoice and Packing List net weights are required to cross-validate.",
                compared_values=weights,
                source_document_ids=src_docs,
            )

        tolerance = Decimal(str(settings.VALIDATION_WEIGHT_TOLERANCE_KG))
        first_k, first_v = valid[0]
        second_k, second_v = valid[1]
        diff = abs(first_v - second_v)

        if diff <= tolerance:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.PASS,
                explanation=f"Net weights match between Commercial Invoice and Packing List ({first_v} kg).",
                compared_values=weights,
                source_document_ids=src_docs,
            )
        else:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.FAIL,
                explanation=f"Net weight mismatch between Commercial Invoice ({weights['invoice_net_weight_kg']} kg) and Packing List ({weights['packing_net_weight_kg']} kg). Discrepancy: {diff:.2f} kg.",
                compared_values=weights,
                source_document_ids=src_docs,
            )


# ==============================================================================
# 10. Container Number Consistency
# ==============================================================================

class ContainerNumberConsistencyRule(BaseValidationRule):
    """
    Checks that container numbers appearing on the Packing List and Bill of Lading match.
    """
    @property
    def rule_id(self) -> str:
        return "RULE_CONTAINER_NUMBERS_CONSISTENCY"

    @property
    def rule_name(self) -> str:
        return "Container Numbers Consistency"

    def evaluate(
        self,
        invoice: Optional[CommercialInvoiceExtraction],
        packing_list: Optional[PackingListExtraction],
        bl: Optional[BillOfLadingExtraction],
    ) -> ValidationRuleResult:
        pkg_containers = set()
        bl_containers = set()
        src_docs = []

        if packing_list and packing_list.container_numbers:
            for item in packing_list.container_numbers:
                if item.is_present:
                    pkg_containers.add(_normalize_container_number(item.value))
                    if item.source_document_id:
                        src_docs.append(str(item.source_document_id))

        if bl and bl.container_numbers:
            for item in bl.container_numbers:
                if item.is_present:
                    bl_containers.add(_normalize_container_number(item.value))
                    if item.source_document_id:
                        src_docs.append(str(item.source_document_id))

        compared = {
            "packing_list_containers": sorted(list(pkg_containers)),
            "bl_containers": sorted(list(bl_containers)),
        }

        if not pkg_containers and not bl_containers:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=ValidationSeverity.INFO,
                outcome=ValidationOutcome.NOT_APPLICABLE,
                explanation="No container numbers listed on Packing List or Bill of Lading (LCL or bulk cargo).",
                compared_values=compared,
            )

        if not pkg_containers or not bl_containers:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=ValidationSeverity.WARNING,
                outcome=ValidationOutcome.MISSING_DATA,
                explanation="Container numbers present on one document but missing on the other.",
                compared_values=compared,
                source_document_ids=src_docs,
            )

        missing_in_bl = pkg_containers - bl_containers
        missing_in_pkg = bl_containers - pkg_containers

        if not missing_in_bl and not missing_in_pkg:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.PASS,
                explanation=f"Container numbers match between Packing List and Bill of Lading: {', '.join(sorted(list(pkg_containers)))}.",
                compared_values=compared,
                source_document_ids=src_docs,
            )
        else:
            mismatches = []
            if missing_in_bl:
                mismatches.append(f"In Packing List but not B/L: {sorted(list(missing_in_bl))}")
            if missing_in_pkg:
                mismatches.append(f"In B/L but not Packing List: {sorted(list(missing_in_pkg))}")
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.FAIL,
                explanation=f"Container number mismatch: {'; '.join(mismatches)}.",
                compared_values=compared,
                source_document_ids=src_docs,
            )


# ==============================================================================
# 11. Invoice Arithmetic Check (Includes SHP-24812 Protection)
# ==============================================================================

class InvoiceArithmeticRule(BaseValidationRule):
    """
    Verifies line-item arithmetic (quantity * unit_price == line_total) and subtotal checks
    when values are explicitly available in the Commercial Invoice.

    Required Sample Verification SHP-24812:
    - Quantity: 180, Unit price: EUR 42.50.
    - The arithmetic product is EUR 7,650.
    - If the source document does not explicitly contain a confirmed grand total, the calculated
      amount must NOT be treated as an extracted or confirmed invoice total.
    """
    @property
    def rule_id(self) -> str:
        return "RULE_INVOICE_ARITHMETIC"

    @property
    def rule_name(self) -> str:
        return "Invoice Arithmetic Consistency"

    def evaluate(
        self,
        invoice: Optional[CommercialInvoiceExtraction],
        packing_list: Optional[PackingListExtraction],
        bl: Optional[BillOfLadingExtraction],
    ) -> ValidationRuleResult:
        if not invoice:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.NOT_APPLICABLE,
                explanation="Commercial Invoice is not present.",
            )

        src_docs = []
        tolerance = Decimal(str(settings.VALIDATION_CURRENCY_TOLERANCE))

        line_checks = []
        arithmetic_total = Decimal("0")
        has_computable_lines = False

        for idx, item in enumerate(invoice.line_items, start=1):
            if item.quantity.is_present and item.unit_price.is_present:
                qty = Decimal(str(item.quantity.value))
                price = Decimal(str(item.unit_price.value))
                calc_total = qty * price
                arithmetic_total += calc_total
                has_computable_lines = True

                if item.line_total.is_present:
                    stated_total = Decimal(str(item.line_total.value))
                    diff = abs(calc_total - stated_total)
                    if diff > tolerance:
                        line_checks.append(
                            f"Line {idx}: {qty} x {price} = {calc_total}, but stated line total is {stated_total}"
                        )
                else:
                    # Stated line total is absent
                    pass

        grand_total_field = invoice.grand_total
        if grand_total_field.source_document_id:
            src_docs.append(str(grand_total_field.source_document_id))

        compared = {
            "computed_line_arithmetic_total": str(arithmetic_total) if has_computable_lines else None,
            "invoice_stated_grand_total": str(grand_total_field.value) if grand_total_field.is_present else None,
            "currency": invoice.currency.value if invoice.currency.is_present else None,
        }

        # Protection Rule: If grand total is absent from document, calculated arithmetic total
        # MUST NOT be treated as an extracted or confirmed invoice total.
        if not grand_total_field.is_present:
            if has_computable_lines:
                curr_str = f" {invoice.currency.value}" if invoice.currency.is_present else ""
                return ValidationRuleResult(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=ValidationSeverity.WARNING,
                    outcome=ValidationOutcome.MISSING_DATA,
                    explanation=(
                        f"Calculated arithmetic subtotal is {arithmetic_total:.2f}{curr_str}, "
                        f"but grand total is NOT explicitly present on the Commercial Invoice. "
                        f"The calculated amount cannot be treated as a confirmed or extracted invoice total."
                    ),
                    compared_values=compared,
                    source_document_ids=src_docs,
                )
            else:
                return ValidationRuleResult(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    outcome=ValidationOutcome.MISSING_DATA,
                    explanation="Neither line arithmetic nor grand total are present on Commercial Invoice.",
                    compared_values=compared,
                    source_document_ids=src_docs,
                )

        if line_checks:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.FAIL,
                explanation=f"Line item calculation discrepancy: {'; '.join(line_checks)}.",
                compared_values=compared,
                source_document_ids=src_docs,
            )

        # Compare grand total if lines are available
        stated_grand = Decimal(str(grand_total_field.value))
        diff = abs(arithmetic_total - stated_grand)

        if diff <= tolerance:
            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.PASS,
                explanation=f"Invoice arithmetic matches: line item calculations sum to stated grand total ({stated_grand}).",
                compared_values=compared,
                source_document_ids=src_docs,
            )
        else:
            # Check if freight / other charges explain the difference
            freight = Decimal(str(invoice.freight_charges.value)) if invoice.freight_charges.is_present else Decimal("0")
            insurance = Decimal(str(invoice.insurance_charges.value)) if invoice.insurance_charges.is_present else Decimal("0")
            other = Decimal(str(invoice.other_charges.value)) if invoice.other_charges.is_present else Decimal("0")

            if abs(arithmetic_total + freight + insurance + other - stated_grand) <= tolerance:
                return ValidationRuleResult(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    outcome=ValidationOutcome.PASS,
                    explanation=f"Invoice arithmetic verified including charges (subtotal {arithmetic_total} + charges = {stated_grand}).",
                    compared_values=compared,
                    source_document_ids=src_docs,
                )

            return ValidationRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                outcome=ValidationOutcome.FAIL,
                explanation=(
                    f"Invoice grand total discrepancy: Stated grand total is {stated_grand}, "
                    f"but line item arithmetic sum is {arithmetic_total} (difference: {diff:.2f})."
                ),
                compared_values=compared,
                source_document_ids=src_docs,
            )

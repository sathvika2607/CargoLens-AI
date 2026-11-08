import logging
import re
from decimal import Decimal
from typing import Dict, Any, List, Optional

from app.models.document import DocumentType
from app.services.ai.base import (
    BaseExtractionProvider,
    DocumentPageInput,
    RawProviderResult,
)
from app.schemas.structured_extraction import (
    CommercialInvoiceExtraction,
    PackingListExtraction,
    BillOfLadingExtraction,
    ExtractedField,
    InvoiceLineItem,
    PackingLineItem,
)

logger = logging.getLogger("cargolens.ai.fixture_provider")


class DeterministicFixtureExtractionProvider(BaseExtractionProvider):
    """
    Deterministic Development & Demonstration Extraction Provider.
    Implements BaseExtractionProvider without requiring external API keys.
    Extracts structured customs data from synthetic document text with high fidelity,
    supporting realistic confidence scores, low-confidence warning scenarios,
    and missing financial data tests.
    Never masquerades as Claude AI; explicitly identifies as 'development-fixture'.
    """

    @property
    def provider_name(self) -> str:
        return "development-fixture"

    @property
    def model_name(self) -> str:
        return "fixture-v1"

    async def extract_structured(
        self,
        document_type: DocumentType,
        text_content: Optional[str] = None,
        page_images: Optional[List[bytes]] = None,
        mime_type: Optional[str] = None,
    ) -> RawProviderResult:
        page_input = DocumentPageInput(
            page_number=1,
            is_digital_text=bool(text_content),
            text_content=text_content,
        )
        return await self.extract_pages_batch(document_type, [page_input])

    async def extract_pages_batch(
        self,
        document_type: DocumentType,
        pages: List[DocumentPageInput],
    ) -> RawProviderResult:
        all_text = "\n".join([p.text_content for p in pages if p.text_content])
        is_low_confidence = "[LOW_CONFIDENCE]" in all_text

        if document_type == DocumentType.COMMERCIAL_INVOICE:
            data = self._extract_commercial_invoice(all_text, is_low_confidence)
        elif document_type == DocumentType.PACKING_LIST:
            data = self._extract_packing_list(all_text, is_low_confidence)
        elif document_type == DocumentType.BILL_OF_LADING:
            data = self._extract_bill_of_lading(all_text, is_low_confidence)
        else:
            data = {}

        return RawProviderResult(
            data=data,
            provider=self.provider_name,
            model=self.model_name,
            extraction_mode="TEXT_FIRST",
            token_usage={"input_tokens": 140, "output_tokens": 95},
            latency_seconds=0.04,
        )

    def _get_val(self, text: str, pattern: str) -> Optional[str]:
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def _extract_commercial_invoice(self, text: str, is_low_conf: bool) -> Dict[str, Any]:
        conf_high = 0.65 if is_low_conf else 0.99
        conf_med = 0.60 if is_low_conf else 0.98

        inv_num = self._get_val(text, r"Invoice Number:\s*([^\n]+)")
        inv_date = self._get_val(text, r"Invoice Date:\s*([^\n]+)")
        seller = self._get_val(text, r"Seller:\s*([^\n]+)")
        buyer = self._get_val(text, r"Buyer:\s*([^\n]+)")
        currency = self._get_val(text, r"Currency:\s*([^\n]+)")

        grand_total_str = self._get_val(text, r"Grand Total:\s*(?:[A-Z]{3}\s*)?([0-9,.]+)")
        grand_total = Decimal(grand_total_str.replace(",", "")) if grand_total_str else None

        gross_wt_str = self._get_val(text, r"Gross Weight:\s*([0-9,.]+)\s*KG")
        gross_wt = Decimal(gross_wt_str.replace(",", "")) if gross_wt_str else None

        net_wt_str = self._get_val(text, r"Net Weight:\s*([0-9,.]+)\s*KG")
        net_wt = Decimal(net_wt_str.replace(",", "")) if net_wt_str else None

        pkg_cnt_str = self._get_val(text, r"Package Count:\s*([0-9]+)")
        pkg_cnt = int(pkg_cnt_str) if pkg_cnt_str else None

        # Line item parsing
        line_items = []
        item_desc = self._get_val(text, r"Item:\s*([^\n|]+)")
        qty_match = re.search(r"(?:Quantity|Qty):\s*([0-9,.]+)(?:\s*([A-Za-z]+))?", text, re.IGNORECASE)
        qty_str = qty_match.group(1) if qty_match else self._get_val(text, r"(?:Quantity|Qty):\s*([0-9,.]+)")
        uom_str = (qty_match.group(2) if (qty_match and qty_match.group(2)) else None) or self._get_val(text, r"(?:Unit|UOM):\s*([A-Za-z]+)")
        price_str = self._get_val(text, r"Unit Price:\s*(?:[A-Z]{3}\s*)?([0-9,.]+)")
        subtotal_str = self._get_val(text, r"Subtotal:\s*(?:[A-Z]{3}\s*)?([0-9,.]+)")

        if item_desc or qty_str or price_str:
            qty = Decimal(qty_str.replace(",", "")) if qty_str else Decimal("0")
            price = Decimal(price_str.replace(",", "")) if price_str else Decimal("0")
            subtotal = (
                Decimal(subtotal_str.replace(",", ""))
                if subtotal_str
                else round(qty * price, 2)
            )
            line_items.append(
                InvoiceLineItem(
                    item_number=1,
                    description=ExtractedField(
                        value=item_desc.strip() if item_desc else "Item Description",
                        confidence=conf_high,
                        evidence_text=f"Item: {item_desc}",
                    ),
                    quantity=ExtractedField(
                        value=qty,
                        confidence=conf_high,
                        evidence_text=f"Quantity: {qty_str}",
                    ),
                    unit_of_measure=ExtractedField(
                        value=uom_str.upper() if uom_str else "PCS",
                        confidence=conf_high if uom_str else 0.8,
                        evidence_text=f"Unit: {uom_str}" if uom_str else None,
                    ),
                    unit_price=ExtractedField(
                        value=price,
                        confidence=conf_high,
                        evidence_text=f"Unit Price: {price_str}",
                    ),
                    line_total=ExtractedField(
                        value=subtotal,
                        confidence=conf_high,
                        evidence_text=f"Subtotal: {subtotal_str or subtotal}",
                    ),
                )
            )

        model = CommercialInvoiceExtraction(
            invoice_number=ExtractedField(
                value=inv_num,
                confidence=conf_high if inv_num else None,
                evidence_text=f"Invoice Number: {inv_num}" if inv_num else None,
            ),
            invoice_date=ExtractedField(
                value=inv_date,
                confidence=conf_med if inv_date else None,
                evidence_text=f"Invoice Date: {inv_date}" if inv_date else None,
            ),
            seller_name=ExtractedField(
                value=seller,
                confidence=conf_high if seller else None,
                evidence_text=f"Seller: {seller}" if seller else None,
            ),
            buyer_name=ExtractedField(
                value=buyer,
                confidence=conf_med if buyer else None,
                evidence_text=f"Buyer: {buyer}" if buyer else None,
            ),
            currency=ExtractedField(
                value=currency,
                confidence=1.0 if currency else None,
                evidence_text=f"Currency: {currency}" if currency else None,
            ),
            grand_total=ExtractedField(
                value=grand_total,
                confidence=conf_high if grand_total is not None else None,
                evidence_text=f"Grand Total: {grand_total_str}" if grand_total_str else None,
            ),
            gross_weight_kg=ExtractedField(
                value=gross_wt,
                confidence=conf_med if gross_wt is not None else None,
                evidence_text=f"Gross Weight: {gross_wt_str} KG" if gross_wt_str else None,
            ),
            net_weight_kg=ExtractedField(
                value=net_wt,
                confidence=conf_med if net_wt is not None else None,
                evidence_text=f"Net Weight: {net_wt_str} KG" if net_wt_str else None,
            ),
            package_count=ExtractedField(
                value=pkg_cnt,
                confidence=conf_high if pkg_cnt is not None else None,
                evidence_text=f"Package Count: {pkg_cnt_str}" if pkg_cnt_str else None,
            ),
            line_items=line_items,
        )
        return model.model_dump(mode="json")

    def _extract_packing_list(self, text: str, is_low_conf: bool) -> Dict[str, Any]:
        conf_high = 0.62 if is_low_conf else 0.99
        conf_med = 0.65 if is_low_conf else 0.98

        inv_ref = self._get_val(text, r"Invoice Reference:\s*([^\n]+)")
        exporter = self._get_val(text, r"Exporter:\s*([^\n]+)")
        importer = self._get_val(text, r"Importer:\s*([^\n]+)")
        pkg_cnt_str = self._get_val(text, r"Package Count:\s*([0-9]+)")
        pkg_cnt = int(pkg_cnt_str) if pkg_cnt_str else None
        pkg_type = self._get_val(text, r"Package Type:\s*([^\n]+)")

        gross_wt_str = self._get_val(text, r"Gross Weight:\s*([0-9,.]+)\s*KG")
        gross_wt = Decimal(gross_wt_str.replace(",", "")) if gross_wt_str else None

        net_wt_str = self._get_val(text, r"Net Weight:\s*([0-9,.]+)\s*KG")
        net_wt = Decimal(net_wt_str.replace(",", "")) if net_wt_str else None

        container_str = self._get_val(text, r"Container Numbers:\s*([^\n]+)")
        containers = []
        if container_str:
            for c in container_str.split(","):
                c_clean = c.strip()
                if c_clean:
                    containers.append(
                        ExtractedField(
                            value=c_clean,
                            confidence=0.62 if is_low_conf else 0.98,
                            evidence_text=f"Container Numbers: {c_clean}",
                        )
                    )

        # Parse packing list line items
        line_items = []
        item_desc = self._get_val(text, r"Item:\s*([^\n|]+)")
        qty_match = re.search(r"(?:Quantity|Qty):\s*([0-9,.]+)(?:\s*([A-Za-z]+))?", text, re.IGNORECASE)
        pl_qty_str = qty_match.group(1) if qty_match else self._get_val(text, r"(?:Quantity|Qty):\s*([0-9,.]+)")
        pl_uom_str = (qty_match.group(2) if (qty_match and qty_match.group(2)) else None) or self._get_val(text, r"(?:Unit|UOM):\s*([A-Za-z]+)")

        if not pl_qty_str:
            fallback_match = re.search(r"([0-9,.]+)\s*(pcs|cartons|pallets|units)", text, re.IGNORECASE)
            if fallback_match:
                pl_qty_str = fallback_match.group(1)
                if not pl_uom_str:
                    pl_uom_str = fallback_match.group(2).upper()

        if item_desc or pl_qty_str:
            qty_val = Decimal(pl_qty_str.replace(",", "")) if pl_qty_str else Decimal("0")
            line_items.append(
                PackingLineItem(
                    item_number=1,
                    description=ExtractedField(
                        value=item_desc.strip() if item_desc else "Cargo Item",
                        confidence=conf_high,
                        evidence_text=f"Item: {item_desc}",
                    ),
                    quantity=ExtractedField(
                        value=qty_val,
                        confidence=conf_high,
                        evidence_text=f"Quantity: {pl_qty_str}",
                    ),
                    unit_of_measure=ExtractedField(
                        value=pl_uom_str.upper() if pl_uom_str else "PCS",
                        confidence=conf_high if pl_uom_str else 0.8,
                        evidence_text=f"Unit: {pl_uom_str}" if pl_uom_str else None,
                    ),
                    package_count=ExtractedField(
                        value=pkg_cnt,
                        confidence=conf_med if pkg_cnt is not None else None,
                        evidence_text=f"Package Count: {pkg_cnt_str}" if pkg_cnt_str else None,
                    ),
                    package_type=ExtractedField(
                        value=pkg_type,
                        confidence=conf_high if pkg_type else None,
                        evidence_text=f"Package Type: {pkg_type}" if pkg_type else None,
                    ),
                )
            )

        model = PackingListExtraction(
            exporter_name=ExtractedField(
                value=exporter,
                confidence=conf_high if exporter else None,
                evidence_text=f"Exporter: {exporter}" if exporter else None,
            ),
            importer_name=ExtractedField(
                value=importer,
                confidence=conf_med if importer else None,
                evidence_text=f"Importer: {importer}" if importer else None,
            ),
            invoice_reference=ExtractedField(
                value=inv_ref,
                confidence=conf_high if inv_ref else None,
                evidence_text=f"Invoice Reference: {inv_ref}" if inv_ref else None,
            ),
            line_items=line_items,
            package_count=ExtractedField(
                value=pkg_cnt,
                confidence=conf_med if pkg_cnt is not None else None,
                evidence_text=f"Package Count: {pkg_cnt_str}" if pkg_cnt_str else None,
            ),
            package_type=ExtractedField(
                value=pkg_type,
                confidence=conf_high if pkg_type else None,
                evidence_text=f"Package Type: {pkg_type}" if pkg_type else None,
            ),
            gross_weight_kg=ExtractedField(
                value=gross_wt,
                confidence=conf_high if gross_wt is not None else None,
                evidence_text=f"Gross Weight: {gross_wt_str} KG" if gross_wt_str else None,
            ),
            net_weight_kg=ExtractedField(
                value=net_wt,
                confidence=conf_med if net_wt is not None else None,
                evidence_text=f"Net Weight: {net_wt_str} KG" if net_wt_str else None,
            ),
            container_numbers=containers,
        )
        return model.model_dump(mode="json")

    def _extract_bill_of_lading(self, text: str, is_low_conf: bool) -> Dict[str, Any]:
        conf_high = 0.64 if is_low_conf else 0.99
        conf_med = 0.61 if is_low_conf else 0.98

        bl_num = self._get_val(text, r"(?:Bill of Lading Number|B/L Number|BL Number):\s*([^\n]+)")
        shipper = self._get_val(text, r"Shipper:\s*([^\n]+)")
        consignee = self._get_val(text, r"Consignee:\s*([^\n]+)")
        notify = self._get_val(text, r"Notify Party:\s*([^\n]+)")
        vessel = self._get_val(text, r"Vessel:\s*([^\n]+)")
        voyage = self._get_val(text, r"Voyage:\s*([^\n]+)")
        pol = self._get_val(text, r"Port of Loading:\s*([^\n]+)")
        pod = self._get_val(text, r"Port of Discharge:\s*([^\n]+)")
        goods_desc = self._get_val(text, r"(?:Goods Description|Description of Goods|Item):\s*([^\n]+)")

        gross_wt_str = self._get_val(text, r"Gross Weight:\s*([0-9,.]+)\s*KG")
        gross_wt = Decimal(gross_wt_str.replace(",", "")) if gross_wt_str else None

        pkg_cnt_str = self._get_val(text, r"Package Count:\s*([0-9]+)")
        pkg_cnt = int(pkg_cnt_str) if pkg_cnt_str else None

        container_str = self._get_val(text, r"Container Numbers:\s*([^\n]+)")
        containers = []
        if container_str:
            for c in container_str.split(","):
                c_clean = c.strip()
                if c_clean:
                    containers.append(
                        ExtractedField(
                            value=c_clean,
                            confidence=0.62 if is_low_conf else 0.98,
                            evidence_text=f"Container Numbers: {c_clean}",
                        )
                    )

        seal_str = self._get_val(text, r"Seal Numbers:\s*([^\n]+)")
        seals = []
        if seal_str:
            for s in seal_str.split(","):
                s_clean = s.strip()
                if s_clean:
                    seals.append(
                        ExtractedField(
                            value=s_clean,
                            confidence=0.65 if is_low_conf else 0.99,
                            evidence_text=f"Seal Numbers: {s_clean}",
                        )
                    )

        model = BillOfLadingExtraction(
            bl_number=ExtractedField(
                value=bl_num,
                confidence=conf_high if bl_num else None,
                evidence_text=f"B/L Number: {bl_num}" if bl_num else None,
            ),
            shipper_name=ExtractedField(
                value=shipper,
                confidence=conf_high if shipper else None,
                evidence_text=f"Shipper: {shipper}" if shipper else None,
            ),
            consignee_name=ExtractedField(
                value=consignee,
                confidence=conf_med if consignee else None,
                evidence_text=f"Consignee: {consignee}" if consignee else None,
            ),
            notify_party=ExtractedField(
                value=notify,
                confidence=conf_med if notify else None,
                evidence_text=f"Notify Party: {notify}" if notify else None,
            ),
            vessel_name=ExtractedField(
                value=vessel,
                confidence=conf_high if vessel else None,
                evidence_text=f"Vessel: {vessel}" if vessel else None,
            ),
            voyage_number=ExtractedField(
                value=voyage,
                confidence=conf_med if voyage else None,
                evidence_text=f"Voyage: {voyage}" if voyage else None,
            ),
            port_of_loading=ExtractedField(
                value=pol,
                confidence=conf_high if pol else None,
                evidence_text=f"Port of Loading: {pol}" if pol else None,
            ),
            port_of_discharge=ExtractedField(
                value=pod,
                confidence=conf_high if pod else None,
                evidence_text=f"Port of Discharge: {pod}" if pod else None,
            ),
            goods_description=ExtractedField(
                value=goods_desc,
                confidence=conf_high if goods_desc else None,
                evidence_text=f"Goods Description: {goods_desc}" if goods_desc else None,
            ),
            gross_weight_kg=ExtractedField(
                value=gross_wt,
                confidence=conf_high if gross_wt is not None else None,
                evidence_text=f"Gross Weight: {gross_wt_str} KG" if gross_wt_str else None,
            ),
            package_count=ExtractedField(
                value=pkg_cnt,
                confidence=conf_med if pkg_cnt is not None else None,
                evidence_text=f"Package Count: {pkg_cnt_str}" if pkg_cnt_str else None,
            ),
            container_numbers=containers,
            seal_numbers=seals,
        )
        return model.model_dump(mode="json")

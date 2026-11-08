import io
import re
from typing import List, Optional, Dict, Any, Tuple
import pymupdf

from app.models.document import DocumentType


class TradePdfGenerator:
    """
    Renders enterprise-quality, authentic international trade documents (Commercial Invoice,
    Packing List, Bill of Lading) with crisp typography, structured corporate borders, vector
    emblems, tabular line items, packaging summaries, official customs declarations,
    authenticated corporate stamps, security barcodes, and demo watermarks.
    """

    # Corporate Executive Palette (Navy, Slate, Crisp Whites and Greys)
    NAVY_DARK = (0.05, 0.11, 0.22)       # #0D1C38 - Deep Primary Navy
    NAVY_MID = (0.10, 0.22, 0.42)        # #1A386B - Executive Secondary Navy
    NAVY_LIGHT = (0.93, 0.95, 0.98)      # #EDF3FA - Card & Header Fill
    SLATE_DARK = (0.14, 0.17, 0.22)      # #242B38 - Primary Text
    SLATE_MUTED = (0.42, 0.46, 0.54)     # #6B758A - Secondary Text & Labels
    BORDER_COLOR = (0.74, 0.79, 0.86)    # #BDC9DC - Table & Card Dividers
    BORDER_DARK = (0.35, 0.42, 0.52)     # #596B85 - Major Outer Rules
    ACCENT_AMBER = (0.85, 0.42, 0.08)    # #D96B14 - Warning & Unstated Highlights
    ACCENT_EMERALD = (0.08, 0.52, 0.32)  # #148552 - Verified Status
    BG_ZEBRA = (0.975, 0.985, 0.995)     # #F8FAFE - Alternating Table Row Fill
    BG_WHITE = (1.0, 1.0, 1.0)

    @classmethod
    def _parse_lines(cls, lines: List[str]) -> Tuple[Dict[str, str], List[str]]:
        parsed = {}
        other = []
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
            if "|" in line_clean and ":" in line_clean:
                segments = line_clean.split("|")
                for seg in segments:
                    seg = seg.strip()
                    if ":" in seg:
                        sk, sv = seg.split(":", 1)
                        sk_clean = sk.strip().lower()
                        if sk_clean.startswith("line "):
                            parsed["item"] = sv.strip()
                        elif sk_clean == "price":
                            parsed["unit price"] = sv.strip()
                        elif sk_clean == "total":
                            parsed["subtotal"] = sv.strip()
                        parsed[sk_clean] = sv.strip()
                    else:
                        other.append(seg)
            elif ":" in line_clean:
                parts = line_clean.split(":", 1)
                k = parts[0].strip().lower()
                v = parts[1].strip()
                if k.startswith("line "):
                    parsed["item"] = v
                parsed[k] = v
            else:
                other.append(line_clean)
        return parsed, other

    @classmethod
    def _get(cls, parsed: Dict[str, str], *keys: str, default: str = "") -> str:
        for k in keys:
            if k.lower() in parsed:
                return parsed[k.lower()]
        return default

    @classmethod
    def _clean_prefix(cls, text: str, prefix_pattern: str) -> str:
        return re.sub(prefix_pattern, "", text, flags=re.IGNORECASE).strip()

    @classmethod
    def _draw_emblem(cls, page: pymupdf.Page, x: float, y: float, emblem_type: str):
        """Draws a vector corporate insignia or carrier emblem."""
        # Rounded background badge
        page.draw_rect(pymupdf.Rect(x, y, x + 34, y + 34), fill=cls.NAVY_MID, color=cls.NAVY_DARK, width=0.8)
        # Inner accent border
        page.draw_rect(pymupdf.Rect(x + 2, y + 2, x + 32, y + 32), color=(0.28, 0.44, 0.68), width=0.5)

        if emblem_type == "invoice":
            # Corporate Shield & Document Icon
            page.draw_line(pymupdf.Point(x + 8, y + 9), pymupdf.Point(x + 26, y + 9), color=(1, 1, 1), width=1.2)
            page.draw_line(pymupdf.Point(x + 8, y + 14), pymupdf.Point(x + 22, y + 14), color=(1, 1, 1), width=1.0)
            page.draw_line(pymupdf.Point(x + 8, y + 19), pymupdf.Point(x + 26, y + 19), color=(1, 1, 1), width=1.0)
            page.draw_line(pymupdf.Point(x + 8, y + 24), pymupdf.Point(x + 19, y + 24), color=(0.85, 0.70, 0.30), width=1.2)
        elif emblem_type == "packing":
            # Cargo Pallet & Container Icon
            page.draw_rect(pymupdf.Rect(x + 7, y + 8, x + 27, y + 20), color=(1, 1, 1), width=1.0)
            page.draw_line(pymupdf.Point(x + 17, y + 8), pymupdf.Point(x + 17, y + 20), color=(1, 1, 1), width=0.8)
            page.draw_line(pymupdf.Point(x + 5, y + 24), pymupdf.Point(x + 29, y + 24), color=(0.85, 0.70, 0.30), width=1.5)
            page.draw_line(pymupdf.Point(x + 8, y + 24), pymupdf.Point(x + 8, y + 27), color=(0.85, 0.70, 0.30), width=1.5)
            page.draw_line(pymupdf.Point(x + 26, y + 24), pymupdf.Point(x + 26, y + 27), color=(0.85, 0.70, 0.30), width=1.5)
        else:
            # Maritime Ocean Carrier / Anchor Icon
            page.draw_line(pymupdf.Point(x + 17, y + 7), pymupdf.Point(x + 17, y + 25), color=(1, 1, 1), width=1.4)
            page.draw_circle(pymupdf.Point(x + 17, y + 9), 3, color=(1, 1, 1), width=0.8)
            page.draw_line(pymupdf.Point(x + 10, y + 15), pymupdf.Point(x + 24, y + 15), color=(1, 1, 1), width=1.2)
            # Anchor curved base
            page.draw_line(pymupdf.Point(x + 8, y + 21), pymupdf.Point(x + 17, y + 26), color=(0.85, 0.70, 0.30), width=1.5)
            page.draw_line(pymupdf.Point(x + 17, y + 26), pymupdf.Point(x + 26, y + 21), color=(0.85, 0.70, 0.30), width=1.5)

    @classmethod
    def _draw_stamp(cls, page: pymupdf.Page, cx: float, cy: float, title_text: str, dept_text: str, date_str: str):
        """Draws a decorative simulated vector corporate seal stamp for demonstration data."""
        # Outer Ring
        page.draw_circle(pymupdf.Point(cx, cy), 32, color=cls.NAVY_MID, width=1.2)
        # Inner Ring
        page.draw_circle(pymupdf.Point(cx, cy), 28, color=(0.35, 0.48, 0.68), width=0.6)
        # Radial Stars
        page.insert_text((cx - 26, cy - 2), "*", fontname="hebo", fontsize=10, color=cls.ACCENT_AMBER)
        page.insert_text((cx + 20, cy - 2), "*", fontname="hebo", fontsize=10, color=cls.ACCENT_AMBER)
        # Stamp Text Hierarchy
        page.insert_text((cx - 24, cy - 12), title_text[:16].upper(), fontname="hebo", fontsize=6, color=cls.NAVY_DARK)
        page.insert_text((cx - 23, cy), dept_text[:18].upper(), fontname="hebo", fontsize=5.5, color=cls.NAVY_MID)
        page.insert_text((cx - 20, cy + 10), f"DATE: {date_str[:10]}", fontname="hebo", fontsize=5.5, color=cls.SLATE_DARK)
        page.insert_text((cx - 20, cy + 19), "DEMO ONLY", fontname="hebi", fontsize=5.5, color=cls.ACCENT_AMBER)

    @classmethod
    def _draw_barcode(cls, page: pymupdf.Page, x: float, y: float, w: float, h: float, code_str: str):
        """Renders a simulated demonstration barcode strip representing internal document tracking identifiers."""
        page.draw_rect(pymupdf.Rect(x, y, x + w, y + h), fill=cls.BG_ZEBRA, color=cls.BORDER_COLOR, width=0.5)
        # Barcode vertical stripes
        bx = x + 10
        pattern = [1.2, 0.6, 2.0, 0.8, 1.5, 2.2, 0.7, 1.8, 0.9, 1.2, 2.4, 0.6, 1.6, 2.0, 0.8, 1.4, 2.2, 0.6, 1.8, 1.0]
        idx = 0
        while bx < x + 140:
            bw = pattern[idx % len(pattern)]
            page.draw_rect(pymupdf.Rect(bx, y + 4, bx + bw, y + h - 12), fill=cls.NAVY_DARK, color=cls.NAVY_DARK, width=0)
            bx += bw + 1.2
            idx += 1
        page.insert_text((x + 12, y + h - 3), f"* DEMO-ID: {code_str} *", fontname="helv", fontsize=5.8, color=cls.SLATE_MUTED)
        # Internal demo identification text right (clearly disclaiming official customs filing or authentication)
        page.insert_text((x + 160, y + 10), "INTERNAL DOCUMENT TRACKING — DEMONSTRATION RECORD", fontname="hebo", fontsize=6.5, color=cls.NAVY_DARK)
        page.insert_text((x + 160, y + 20), "SIMULATED EDI FORMAT • CARGOLENS AUTOMATED EXTRACTION TEST RECORD", fontname="helv", fontsize=6, color=cls.SLATE_MUTED)
        page.insert_text((x + 160, y + 29), "SYSTEM DEMO IDENTIFIER • NOT AN OFFICIAL CUSTOMS FILING OR LEGAL SUBMISSION", fontname="hebo", fontsize=5.8, color=cls.ACCENT_AMBER)

    @classmethod
    def generate(
        cls,
        title: str,
        lines: List[str],
        is_low_confidence: bool = False,
        document_type: Optional[DocumentType] = None,
    ) -> bytes:
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)  # Standard A4 portrait

        title_norm = title.strip().lower()
        parsed, other = cls._parse_lines(lines)

        is_pl = (
            document_type == DocumentType.PACKING_LIST
            or "packing" in title_norm
        )
        is_bl = (
            document_type == DocumentType.BILL_OF_LADING
            or "lading" in title_norm
            or "b/l" in title_norm
            or "bl" in title_norm
        )

        if is_pl:
            cls._draw_packing_list(page, title, parsed, other, is_low_confidence)
        elif is_bl:
            cls._draw_bill_of_lading(page, title, parsed, other, is_low_confidence)
        else:
            cls._draw_commercial_invoice(page, title, parsed, other, is_low_confidence)

        # Standard bottom demo watermark & pagination
        page.draw_line(pymupdf.Point(28, 804), pymupdf.Point(567, 804), color=cls.BORDER_DARK, width=0.6)
        watermark = "SYNTHETIC DEMONSTRATION DATA — FOR TESTING & DEMO ONLY — NOT AN OFFICIAL CUSTOMS FILING"
        if is_low_confidence:
            watermark = "[LOW_CONFIDENCE] " + watermark
        page.insert_text((35, 816), watermark, fontname="hebo", fontsize=6.5, color=(0.48, 0.52, 0.60))
        page.insert_text((385, 816), "PORT OF NHAVA SHEVA (INNSA1) SPECIMEN", fontname="helv", fontsize=6.2, color=(0.55, 0.58, 0.65))
        page.insert_text((530, 816), "Page 1 of 1", fontname="hebo", fontsize=7.2, color=cls.NAVY_MID)

        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # =========================================================================
    # 1. COMMERCIAL INVOICE — PREMIUM ENTERPRISE LAYOUT
    # =========================================================================
    @classmethod
    def _draw_commercial_invoice(
        cls,
        page: pymupdf.Page,
        title: str,
        parsed: Dict[str, str],
        other: List[str],
        is_low_conf: bool,
    ):
        # Double Corporate Frame
        page.draw_rect(pymupdf.Rect(28, 28, 567, 800), color=cls.BORDER_DARK, width=1.0)
        page.draw_rect(pymupdf.Rect(30, 30, 565, 798), color=cls.BORDER_COLOR, width=0.5)

        # 1. Header Banner
        page.draw_rect(pymupdf.Rect(30, 30, 565, 108), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.8)
        cls._draw_emblem(page, 42, 42, "invoice")

        doc_heading = title.upper() if title else "COMMERCIAL INVOICE"
        page.insert_text((86, 52), doc_heading, fontname="hebo", fontsize=15, color=cls.NAVY_DARK)
        page.insert_text(
            (86, 68),
            "CUSTOMS CLEARANCE INVOICE — PORT OF NHAVA SHEVA (JNPT), INDIA",
            fontname="hebo",
            fontsize=7.2,
            color=cls.NAVY_MID,
        )
        page.insert_text(
            (86, 79),
            "IN ACCORDANCE WITH SECTION 14 OF THE INDIAN CUSTOMS ACT, 1962",
            fontname="helv",
            fontsize=6.5,
            color=cls.SLATE_MUTED,
        )

        badge = "SYNTHETIC DEMONSTRATION DATA"
        if is_low_conf:
            badge += " [LOW_CONFIDENCE]"
        page.insert_text((86, 95), badge, fontname="hebo", fontsize=7.0, color=cls.ACCENT_AMBER)

        # Header Right Metadata Card
        inv_num = cls._clean_prefix(cls._get(parsed, "invoice number", "inv no", "invoice no", default="[Not provided in source declaration]"), r"^invoice\s*(?:number|no)?:\s*")
        inv_date = cls._clean_prefix(cls._get(parsed, "invoice date", "date", default="2026-10-18"), r"^invoice\s*date:\s*")
        currency = cls._get(parsed, "currency", default="USD")
        terms = cls._get(parsed, "terms", "incoterms", default="CIF Nhava Sheva (INCOTERMS 2020)")

        page.draw_rect(pymupdf.Rect(355, 36, 558, 102), fill=cls.BG_WHITE, color=cls.BORDER_COLOR, width=0.6)
        page.insert_text((362, 50), f"Invoice Number: {inv_num}", fontname="hebo", fontsize=8.0, color=cls.NAVY_DARK)
        page.insert_text((362, 63), f"Invoice Date: {inv_date}", fontname="helv", fontsize=7.8, color=cls.SLATE_DARK)
        page.insert_text((362, 76), f"Currency: {currency}", fontname="hebo", fontsize=7.8, color=cls.NAVY_MID)
        page.insert_text((362, 88), f"Incoterms: {terms[:32]}", fontname="helv", fontsize=7.2, color=cls.SLATE_MUTED)

        # 2. Trading Parties Panels (2 Balanced Columns)
        # Seller Box (Left)
        page.draw_rect(pymupdf.Rect(30, 108, 297, 195), color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(30, 108, 297, 124), fill=cls.NAVY_MID, color=cls.NAVY_MID, width=0)
        page.insert_text((38, 119), "1. EXPORTER / SELLER (CONSIGNOR):", fontname="hebo", fontsize=7.2, color=(1, 1, 1))

        seller = cls._clean_prefix(cls._get(parsed, "seller", "exporter", "shipper", default="[Not provided in source declaration]"), r"^(?:seller|exporter|shipper):\s*")
        page.insert_text((38, 137), f"Seller: {seller}", fontname="hebo", fontsize=8.0, color=cls.NAVY_DARK if "[Not provided" not in seller else cls.SLATE_MUTED)
        if "[Not provided" not in seller:
            page.insert_text((38, 151), "Industrial Export Processing Zone", fontname="helv", fontsize=7.5, color=cls.SLATE_MUTED)
            page.insert_text((38, 163), "Customs Registered Manufacturer & Overseas Shipper", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
            page.insert_text((38, 175), "Tax ID: EX-IND-8849201 | Country of Origin: Declaration", fontname="helv", fontsize=6.8, color=cls.SLATE_MUTED)
        else:
            page.insert_text((38, 153), "Identity unstated on physical documentation declaration", fontname="hebi", fontsize=7.2, color=cls.ACCENT_AMBER)

        # Buyer Box (Right)
        page.draw_rect(pymupdf.Rect(297, 108, 565, 195), color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(297, 108, 565, 124), fill=cls.NAVY_MID, color=cls.NAVY_MID, width=0)
        page.insert_text((305, 119), "2. IMPORTER / BUYER (CONSIGNEE):", fontname="hebo", fontsize=7.2, color=(1, 1, 1))

        buyer = cls._clean_prefix(cls._get(parsed, "buyer", "consignee", "importer", default="[Not provided in source declaration]"), r"^(?:buyer|consignee|importer):\s*")
        page.insert_text((305, 137), f"Buyer: {buyer}", fontname="hebo", fontsize=8.0, color=cls.NAVY_DARK if "[Not provided" not in buyer else cls.SLATE_MUTED)
        if "[Not provided" not in buyer:
            page.insert_text((305, 151), "Navi Mumbai Commercial Logistics Park, Maharashtra, India", fontname="helv", fontsize=7.5, color=cls.SLATE_MUTED)
            page.insert_text((305, 163), "IEC / GSTIN Registered Consignee — Indian Customs Port Hub", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
            page.insert_text((305, 175), "GSTIN: 27AABCL8921M1ZX | Port Node: Nhava Sheva (INNSA)", fontname="helv", fontsize=6.8, color=cls.SLATE_MUTED)
        else:
            page.insert_text((305, 153), "Identity unstated on physical documentation declaration", fontname="hebi", fontsize=7.2, color=cls.ACCENT_AMBER)

        # 3. Transport & Logistics Ribbon
        page.draw_rect(pymupdf.Rect(30, 195, 565, 238), fill=cls.BG_ZEBRA, color=cls.BORDER_COLOR, width=0.8)
        pol = cls._clean_prefix(cls._get(parsed, "port of loading", default="Port of Loading"), r"^port\s*of\s*loading:\s*")
        pod = cls._clean_prefix(cls._get(parsed, "port of discharge", default="Nhava Sheva (INNSA), India"), r"^port\s*of\s*discharge:\s*")
        vessel = cls._get(parsed, "vessel", "vessel / voyage", default="Commercial Ocean Carrier")

        # Vertical Column Divider inside ribbon
        page.draw_line(pymupdf.Point(297, 195), pymupdf.Point(297, 238), color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((38, 210), f"Port of Loading: {pol}", fontname="helv", fontsize=7.5, color=cls.SLATE_DARK)
        page.insert_text((38, 224), f"Vessel / Voyage: {vessel}", fontname="helv", fontsize=7.5, color=cls.SLATE_DARK)
        page.insert_text((305, 210), f"Port of Discharge: {pod}", fontname="hebo", fontsize=7.8, color=cls.NAVY_DARK)
        page.insert_text((305, 224), "Destination: Nhava Sheva Customs (INNSA1) CFS Terminal", fontname="helv", fontsize=7.2, color=cls.SLATE_MUTED)

        # 4. Product Table Header
        page.draw_rect(pymupdf.Rect(30, 244, 565, 265), fill=cls.NAVY_MID, color=cls.NAVY_MID, width=0)
        page.insert_text((36, 258), "Item", fontname="hebo", fontsize=7.2, color=(1, 1, 1))
        page.insert_text((65, 258), "Description of Goods & Specifications", fontname="hebo", fontsize=7.2, color=(1, 1, 1))
        page.insert_text((275, 258), "Quantity", fontname="hebo", fontsize=7.2, color=(1, 1, 1))
        page.insert_text((345, 258), "Unit", fontname="hebo", fontsize=7.2, color=(1, 1, 1))
        page.insert_text((395, 258), "Unit Price", fontname="hebo", fontsize=7.2, color=(1, 1, 1))
        page.insert_text((475, 258), "Line Total", fontname="hebo", fontsize=7.2, color=(1, 1, 1))

        # 4. Product Table Row 1
        item_desc = cls._clean_prefix(cls._get(parsed, "item", "description", "goods description", default="Commercial Merchandise"), r"^(?:item|goods description|description):\s*")
        qty = cls._clean_prefix(cls._get(parsed, "quantity", "qty", default=""), r"^(?:quantity|qty):\s*")
        uom = cls._clean_prefix(cls._get(parsed, "unit", "uom", default="PCS"), r"^(?:unit|uom):\s*")
        unit_price = cls._clean_prefix(cls._get(parsed, "unit price", default=""), r"^unit\s*price:\s*")
        subtotal = cls._clean_prefix(cls._get(parsed, "subtotal", "line total", default=""), r"^(?:subtotal|line total):\s*")

        page.draw_rect(pymupdf.Rect(30, 265, 565, 345), fill=cls.BG_WHITE, color=cls.BORDER_COLOR, width=0.8)
        # Vertical column separators inside table
        for col_x in [58, 270, 340, 390, 470]:
            page.draw_line(pymupdf.Point(col_x, 265), pymupdf.Point(col_x, 345), color=cls.BORDER_COLOR, width=0.4)

        page.insert_text((40, 278), "1", fontname="hebo", fontsize=8.0, color=cls.SLATE_DARK)
        # Line 1 (y=278): Item description
        page.insert_text((65, 278), f"Item: {item_desc}", fontname="hebo", fontsize=7.8, color=cls.NAVY_DARK)

        # Line 2 (y=292): Specification and Quantity
        page.insert_text((65, 292), "Specification: Commercial Grade Verified Standard", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
        if qty:
            page.insert_text((275, 292), f"Quantity: {qty}", fontname="hebo", fontsize=7.8, color=cls.NAVY_DARK)
        else:
            page.insert_text((275, 292), "Quantity: [Unstated]", fontname="helv", fontsize=7.5, color=cls.SLATE_MUTED)

        # Line 3 (y=306): HS Classification and Unit Price
        page.insert_text((65, 306), "HS Classification: Subject to Customs Tariff Assessment", fontname="hebi", fontsize=6.8, color=(0.50, 0.55, 0.62))
        if unit_price:
            page.insert_text((395, 306), f"Unit Price: {unit_price}", fontname="hebo", fontsize=7.8, color=cls.NAVY_DARK)

        # Line 4 (y=320): Unit and Subtotal
        page.insert_text((345, 320), f"Unit: {uom}", fontname="helv", fontsize=7.8, color=cls.SLATE_DARK)
        if subtotal:
            page.insert_text((475, 320), f"Subtotal: {subtotal}", fontname="hebo", fontsize=8.2, color=cls.NAVY_MID)

        # 5. Packaging & Weight Specification (Left Box)
        page.draw_rect(pymupdf.Rect(30, 352, 310, 452), fill=cls.BG_WHITE, color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(30, 352, 310, 368), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((38, 363), "WEIGHT & PACKAGING SPECIFICATION:", fontname="hebo", fontsize=7.0, color=cls.NAVY_MID)

        pkg_cnt = cls._clean_prefix(cls._get(parsed, "package count", "packages", default=""), r"^package\s*count:\s*")
        gross_wt = cls._clean_prefix(cls._get(parsed, "gross weight", default=""), r"^gross\s*weight:\s*")
        net_wt = cls._clean_prefix(cls._get(parsed, "net weight", default=""), r"^net\s*weight:\s*")
        container = cls._clean_prefix(cls._get(parsed, "container numbers", "container", default=""), r"^container(?:\s*numbers)?:\s*")

        y_w = 382
        if pkg_cnt:
            page.insert_text((38, y_w), f"Package Count: {pkg_cnt}", fontname="helv", fontsize=7.8, color=cls.SLATE_DARK)
            y_w += 14
        if gross_wt:
            page.insert_text((38, y_w), f"Gross Weight: {gross_wt}", fontname="hebo", fontsize=8.2, color=cls.NAVY_DARK)
            y_w += 14
        if net_wt:
            page.insert_text((38, y_w), f"Net Weight: {net_wt}", fontname="helv", fontsize=7.8, color=cls.SLATE_DARK)
            y_w += 14
        if container:
            page.insert_text((38, y_w), f"Container Numbers: {container}", fontname="helv", fontsize=7.5, color=cls.SLATE_MUTED)
        else:
            page.insert_text((38, y_w), "Container Allocation: CFS LCL / Direct Consignment", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)

        # 5. Financial Summary Card (Right Box)
        page.draw_rect(pymupdf.Rect(318, 352, 565, 452), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(318, 352, 565, 368), fill=cls.NAVY_MID, color=cls.NAVY_MID, width=0)
        page.insert_text((326, 363), "FINANCIAL SETTLEMENT SUMMARY:", fontname="hebo", fontsize=7.0, color=(1, 1, 1))

        if subtotal:
            page.insert_text((326, 383), f"Calculated Line Subtotal: {subtotal}", fontname="hebo", fontsize=8.2, color=cls.NAVY_DARK)
        page.insert_text((326, 398), f"Freight & Insurance: Included in {terms[:18]}", fontname="helv", fontsize=7.2, color=cls.SLATE_MUTED)

        # Grand Total Handling: strictly preserve distinction between confirmed vs unstated
        grand_total = cls._get(parsed, "grand total", default="")
        page.draw_line(pymupdf.Point(326, 408), pymupdf.Point(555, 408), color=cls.BORDER_COLOR, width=0.5)

        if grand_total:
            grand_total_clean = cls._clean_prefix(grand_total, r"^grand\s*total:\s*")
            page.insert_text((326, 428), f"Grand Total: {grand_total_clean}", fontname="hebo", fontsize=11.5, color=cls.NAVY_DARK)
            page.insert_text((326, 442), "Confirmed Source Declared Amount", fontname="helv", fontsize=6.8, color=cls.ACCENT_EMERALD)
        else:
            # Unstated grand total: do not print "Grand Total:"
            page.insert_text((326, 426), "Total Invoice Value: [Unstated in source declaration]", fontname="hebi", fontsize=7.8, color=cls.ACCENT_AMBER)
            page.insert_text((326, 440), "Pure line-item arithmetic reference; invoice total unconfirmed.", fontname="helv", fontsize=6.5, color=cls.SLATE_MUTED)

        # 6. Customs Legal Declaration Box
        page.draw_rect(pymupdf.Rect(30, 460, 565, 524), fill=cls.BG_WHITE, color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(30, 460, 565, 474), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((38, 470), "CUSTOMS STATUTORY DECLARATION SPECIMEN (INDIAN CUSTOMS ACT, 1962 FORMAT):", fontname="hebo", fontsize=6.8, color=cls.NAVY_MID)
        decl_text = (
            "We declare that this simulated commercial invoice reflects the itemized merchandise particulars described herein "
            "for testing and demonstration under Section 14 of the Indian Customs Act, 1962. [Simulated business document for "
            "CargoLens AI platform demonstration and testing; not an official customs filing or legal submission]."
        )
        page.insert_textbox(pymupdf.Rect(38, 478, 555, 520), decl_text, fontname="helv", fontsize=6.8, color=cls.SLATE_MUTED)

        # 7. Authentication & Signatory Block
        page.draw_rect(pymupdf.Rect(30, 532, 320, 638), color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(30, 532, 320, 546), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((38, 542), "ADDITIONAL DECLARATIONS & SPECIAL MARKS:", fontname="hebo", fontsize=6.8, color=cls.NAVY_MID)
        if other:
            other_text = "\n".join(other[:4])
            page.insert_textbox(pymupdf.Rect(38, 550, 312, 630), other_text, fontname="helv", fontsize=7.2, color=cls.SLATE_DARK)
        else:
            page.insert_text((38, 562), "• Consignment cleared for Nhava Sheva CFS container depot.", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
            page.insert_text((38, 576), "• Origin packaging meets international ISPM-15 phytosanitary rules.", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
            page.insert_text((38, 590), "• Single-window clearance format mapped for demonstration testing.", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
            page.insert_text((38, 604), "• Country of origin verified by Chamber of Commerce certification.", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)

        # Right Signatory & Vector Stamp Box
        page.draw_rect(pymupdf.Rect(328, 532, 565, 638), fill=cls.BG_WHITE, color=cls.BORDER_COLOR, width=0.8)
        sign_label = seller[:32] if "[Not provided" not in seller else "Exporter / Shipper"
        page.insert_text((336, 546), f"For and on behalf of {sign_label}:", fontname="hebo", fontsize=7.2, color=cls.NAVY_DARK)

        # Vector Stamp
        cls._draw_stamp(page, 446, 588, "EXPORTER SEAL", "DEMO SPECIMEN", inv_date)

        page.insert_text((336, 626), "[SIMULATED CORPORATE FACSIMILE STAMP — DEMO ONLY]", fontname="hebi", fontsize=6.5, color=cls.NAVY_MID)
        page.insert_text((336, 634), "Demonstration Consignor Endorsement (Simulated Signature)", fontname="helv", fontsize=6.2, color=cls.SLATE_MUTED)

        # 8. Digital Security Barcode Strip
        cls._draw_barcode(page, 30, 646, 535, 42, f"INV-{inv_num[:12] if '[Not provided' not in inv_num else 'DEMO-2026'}")

        # 9. Customs Note Box
        page.draw_rect(pymupdf.Rect(30, 696, 565, 788), fill=cls.BG_ZEBRA, color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((38, 708), "CUSTOMS ADVISORY & RECONCILIATION AUDIT TRAIL:", fontname="hebo", fontsize=6.8, color=cls.NAVY_MID)
        notes = (
            "1. Valuation is subject to verification by the Proper Officer of Customs under Section 14 of the Customs Act, 1962.\n"
            "2. Supporting trade documents (Packing List, Bill of Lading) validated via CargoLens automated engine.\n"
            "3. Any quantitative or monetary discrepancy detected during cross-document validation mandates human review before clearance.\n"
            "4. Generated by CargoLens AI Enterprise Demonstration & Automated Verification System."
        )
        page.insert_textbox(pymupdf.Rect(38, 714, 555, 782), notes, fontname="helv", fontsize=6.5, color=cls.SLATE_MUTED)

    # =========================================================================
    # 2. PACKING LIST — LOGISTICS-ORIENTED LAYOUT
    # =========================================================================
    @classmethod
    def _draw_packing_list(
        cls,
        page: pymupdf.Page,
        title: str,
        parsed: Dict[str, str],
        other: List[str],
        is_low_conf: bool,
    ):
        # Double Corporate Frame
        page.draw_rect(pymupdf.Rect(28, 28, 567, 800), color=cls.BORDER_DARK, width=1.0)
        page.draw_rect(pymupdf.Rect(30, 30, 565, 798), color=cls.BORDER_COLOR, width=0.5)

        # 1. Header Banner
        page.draw_rect(pymupdf.Rect(30, 30, 565, 108), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.8)
        cls._draw_emblem(page, 42, 42, "packing")

        doc_heading = title.upper() if title else "PACKING LIST"
        page.insert_text((86, 52), doc_heading, fontname="hebo", fontsize=15, color=cls.NAVY_DARK)
        page.insert_text(
            (86, 68),
            "CARGO PACKING MANIFEST & WEIGHT SPECIFICATION — PORT OF NHAVA SHEVA (JNPT)",
            fontname="hebo",
            fontsize=7.2,
            color=cls.NAVY_MID,
        )
        page.insert_text(
            (86, 79),
            "DISPATCH RECONCILIATION REPORT • CERTIFIED FOR CONTAINER DISPATCH",
            fontname="helv",
            fontsize=6.5,
            color=cls.SLATE_MUTED,
        )

        badge = "SYNTHETIC DEMONSTRATION DATA"
        if is_low_conf:
            badge += " [LOW_CONFIDENCE]"
        page.insert_text((86, 95), badge, fontname="hebo", fontsize=7.0, color=cls.ACCENT_AMBER)

        # Header Right Metadata Block
        inv_ref = cls._clean_prefix(cls._get(parsed, "invoice reference", "inv ref", "invoice ref", default="[Not provided in source declaration]"), r"^invoice\s*reference:\s*")
        date = cls._clean_prefix(cls._get(parsed, "date", default="2026-10-18"), r"^date:\s*")
        pkg_cnt = cls._clean_prefix(cls._get(parsed, "package count", "packages", default=""), r"^package\s*count:\s*")
        pkg_type = cls._clean_prefix(cls._get(parsed, "package type", default="CARTONS"), r"^package\s*type:\s*")

        page.draw_rect(pymupdf.Rect(355, 36, 558, 102), fill=cls.BG_WHITE, color=cls.BORDER_COLOR, width=0.6)
        page.insert_text((362, 50), f"Invoice Reference: {inv_ref}", fontname="hebo", fontsize=8.0, color=cls.NAVY_DARK)
        page.insert_text((362, 63), f"Manifest Date: {date}", fontname="helv", fontsize=7.8, color=cls.SLATE_DARK)
        if pkg_cnt:
            page.insert_text((362, 76), f"Package Count: {pkg_cnt}", fontname="hebo", fontsize=7.8, color=cls.NAVY_MID)
        page.insert_text((362, 88), f"Package Type: {pkg_type}", fontname="helv", fontsize=7.2, color=cls.SLATE_MUTED)

        # 2. Exporter & Importer Panels
        # Exporter (Left)
        page.draw_rect(pymupdf.Rect(30, 108, 297, 195), color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(30, 108, 297, 124), fill=cls.NAVY_MID, color=cls.NAVY_MID, width=0)
        page.insert_text((38, 119), "1. EXPORTER / CONSIGNOR (ORIGIN):", fontname="hebo", fontsize=7.2, color=(1, 1, 1))

        exporter = cls._clean_prefix(cls._get(parsed, "exporter", "shipper", "seller", default="[Not provided in source declaration]"), r"^(?:exporter|shipper|seller):\s*")
        page.insert_text((38, 137), f"Exporter: {exporter}", fontname="hebo", fontsize=8.0, color=cls.NAVY_DARK if "[Not provided" not in exporter else cls.SLATE_MUTED)
        page.insert_text((38, 151), "Warehouse Logistics & Packaging Facility", fontname="helv", fontsize=7.5, color=cls.SLATE_MUTED)
        page.insert_text((38, 163), "Export Packaging & Quality Control Unit — Seaworthy Palletizing", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
        page.insert_text((38, 175), "Depot Verification Node: Origin Dispatch Hub", fontname="helv", fontsize=6.8, color=cls.SLATE_MUTED)

        # Importer (Right)
        page.draw_rect(pymupdf.Rect(297, 108, 565, 195), color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(297, 108, 565, 124), fill=cls.NAVY_MID, color=cls.NAVY_MID, width=0)
        page.insert_text((305, 119), "2. IMPORTER / CONSIGNEE (DESTINATION):", fontname="hebo", fontsize=7.2, color=(1, 1, 1))

        importer = cls._clean_prefix(cls._get(parsed, "importer", "consignee", "buyer", default="[Not provided in source declaration]"), r"^(?:importer|consignee|buyer):\s*")
        page.insert_text((305, 137), f"Importer: {importer}", fontname="hebo", fontsize=8.0, color=cls.NAVY_DARK if "[Not provided" not in importer else cls.SLATE_MUTED)
        page.insert_text((305, 151), "Nhava Sheva Freight CFS Container Depot Hub", fontname="helv", fontsize=7.5, color=cls.SLATE_MUTED)
        page.insert_text((305, 163), "Customs Cleared Cargo Destination — Port of Nhava Sheva", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
        page.insert_text((305, 175), "Jawaharlal Nehru Port Trust Logistics Node (INNSA)", fontname="helv", fontsize=6.8, color=cls.SLATE_MUTED)

        # 3. Transport & Container Ribbon
        page.draw_rect(pymupdf.Rect(30, 195, 565, 238), fill=cls.BG_ZEBRA, color=cls.BORDER_COLOR, width=0.8)
        containers = cls._clean_prefix(cls._get(parsed, "container numbers", "container", default="MSCU1029384"), r"^container(?:\s*numbers)?:\s*")
        seals = cls._clean_prefix(cls._get(parsed, "seal numbers", "seal", default="MSC8392102"), r"^seal(?:\s*numbers)?:\s*")

        page.draw_line(pymupdf.Point(297, 195), pymupdf.Point(297, 238), color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((38, 210), f"Container Numbers: {containers}", fontname="hebo", fontsize=7.8, color=cls.NAVY_DARK)
        page.insert_text((38, 224), f"Seal Numbers: {seals}", fontname="helv", fontsize=7.5, color=cls.SLATE_DARK)
        page.insert_text((305, 210), "Port of Discharge: Nhava Sheva (INNSA)", fontname="hebo", fontsize=7.8, color=cls.NAVY_MID)
        page.insert_text((305, 224), "CFS: Jawaharlal Nehru Port Logistics Park (INNSA1)", fontname="helv", fontsize=7.2, color=cls.SLATE_MUTED)

        # 4. Packing Table Header
        page.draw_rect(pymupdf.Rect(30, 244, 565, 265), fill=cls.NAVY_MID, color=cls.NAVY_MID, width=0)
        page.insert_text((36, 258), "Pkg #", fontname="hebo", fontsize=7.2, color=(1, 1, 1))
        page.insert_text((70, 258), "Package Description & Cargo Specifications", fontname="hebo", fontsize=7.2, color=(1, 1, 1))
        page.insert_text((275, 258), "Quantity", fontname="hebo", fontsize=7.2, color=(1, 1, 1))
        page.insert_text((355, 258), "Net Wt (KG)", fontname="hebo", fontsize=7.2, color=(1, 1, 1))
        page.insert_text((455, 258), "Gross Weight (KG)", fontname="hebo", fontsize=7.2, color=(1, 1, 1))

        # 4. Packing Table Row
        item_desc = cls._clean_prefix(cls._get(parsed, "item", "description", default="Packaged Commercial Goods"), r"^(?:item|goods description|description):\s*")
        qty = cls._clean_prefix(cls._get(parsed, "quantity", "qty", default=""), r"^(?:quantity|qty):\s*")
        net_wt = cls._clean_prefix(cls._get(parsed, "net weight", default=""), r"^net\s*weight:\s*")
        gross_wt = cls._clean_prefix(cls._get(parsed, "gross weight", default=""), r"^gross\s*weight:\s*")

        page.draw_rect(pymupdf.Rect(30, 265, 565, 345), fill=cls.BG_WHITE, color=cls.BORDER_COLOR, width=0.8)
        for col_x in [64, 270, 350, 450]:
            page.draw_line(pymupdf.Point(col_x, 265), pymupdf.Point(col_x, 345), color=cls.BORDER_COLOR, width=0.4)

        page.insert_text((40, 290), "1-N", fontname="hebo", fontsize=8.0, color=cls.SLATE_DARK)
        # Dedicated Line for Item ensures regex matches clean line
        page.insert_text((70, 286), f"Item: {item_desc}", fontname="hebo", fontsize=7.8, color=cls.NAVY_DARK)
        page.insert_text((70, 302), "Packaging: Heavy-Duty Export Cartons with Plastic Strapping", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
        page.insert_text((70, 316), "Markings: JNPT / NHAVA SHEVA / INDIA | FRAGILE MERCHANDISE", fontname="hebi", fontsize=6.8, color=(0.50, 0.55, 0.62))

        if qty:
            page.insert_text((275, 290), f"Quantity: {qty}", fontname="hebo", fontsize=7.8, color=cls.NAVY_DARK)
        if net_wt:
            page.insert_text((355, 290), f"Net Weight: {net_wt}", fontname="helv", fontsize=7.8, color=cls.SLATE_DARK)
        if gross_wt:
            page.insert_text((455, 290), f"Gross Weight: {gross_wt}", fontname="hebo", fontsize=8.5, color=cls.NAVY_DARK)

        # 5. Manifest Recapitulation (Left Box)
        page.draw_rect(pymupdf.Rect(30, 352, 310, 452), fill=cls.BG_WHITE, color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(30, 352, 310, 368), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((38, 363), "MANIFEST RECAPITULATION & PACKAGING:", fontname="hebo", fontsize=7.0, color=cls.NAVY_MID)

        y_p = 382
        if pkg_cnt:
            page.insert_text((38, y_p), f"Package Count: {pkg_cnt}", fontname="hebo", fontsize=8.0, color=cls.SLATE_DARK)
            y_p += 14
        page.insert_text((38, y_p), f"Package Type: {pkg_type}", fontname="helv", fontsize=7.8, color=cls.SLATE_DARK)
        y_p += 14
        if net_wt:
            page.insert_text((38, y_p), f"Net Weight: {net_wt}", fontname="helv", fontsize=7.8, color=cls.SLATE_MUTED)
            y_p += 14
        if containers:
            page.insert_text((38, y_p), f"Container Numbers: {containers}", fontname="helv", fontsize=7.5, color=cls.SLATE_MUTED)

        # 5. Prominent Certified Weight Card (Right Box) - Critical for Cross-Document Validation!
        page.draw_rect(pymupdf.Rect(318, 352, 565, 452), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(318, 352, 565, 368), fill=cls.NAVY_MID, color=cls.NAVY_MID, width=0)
        page.insert_text((326, 363), "CERTIFIED DISPATCH WEIGHTS (CROSS-DOCUMENT CRITICAL):", fontname="hebo", fontsize=6.8, color=(1, 1, 1))

        if net_wt:
            page.insert_text((326, 383), f"Total Net Weight: {net_wt}", fontname="helv", fontsize=8.0, color=cls.SLATE_DARK)
        if gross_wt:
            page.draw_line(pymupdf.Point(326, 396), pymupdf.Point(555, 396), color=cls.BORDER_COLOR, width=0.5)
            # Prominent Gross Weight Box
            page.draw_rect(pymupdf.Rect(326, 404, 555, 442), fill=cls.BG_WHITE, color=cls.NAVY_MID, width=1.0)
            page.insert_text((334, 420), f"Gross Weight: {gross_wt}", fontname="hebo", fontsize=11.5, color=cls.NAVY_DARK)
            page.insert_text((334, 434), "Calibrated Weighbridge Reading • Origin Dispatch Station", fontname="helv", fontsize=6.5, color=cls.NAVY_MID)

        # 6. Cargo Handling Instructions & Marks
        page.draw_rect(pymupdf.Rect(30, 460, 565, 524), fill=cls.BG_WHITE, color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(30, 460, 565, 474), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((38, 470), "CARGO HANDLING INSTRUCTIONS & STOWAGE DIRECTIVES:", fontname="hebo", fontsize=6.8, color=cls.NAVY_MID)
        handling_text = (
            "Marks & Numbers: JNPT / NHAVA SHEVA / INDIA | DO NOT DROP | KEEP DRY | FRAGILE MERCHANDISE.\n"
            "All packages verified at origin packing facility. Tare weights confirmed on calibrated weighbridge. "
            "Seaworthy export packaging conforming to international freight handling and JNPT port unloading norms."
        )
        page.insert_textbox(pymupdf.Rect(38, 478, 555, 520), handling_text, fontname="helv", fontsize=6.8, color=cls.SLATE_MUTED)

        # 7. Packing Notes & Signatory Block
        page.draw_rect(pymupdf.Rect(30, 532, 320, 638), color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(30, 532, 320, 546), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((38, 542), "PACKING NOTES & CONSIGNMENT BREAKDOWN:", fontname="hebo", fontsize=6.8, color=cls.NAVY_MID)
        if other:
            other_text = "\n".join(other[:4])
            page.insert_textbox(pymupdf.Rect(38, 550, 312, 630), other_text, fontname="helv", fontsize=7.2, color=cls.SLATE_DARK)
        else:
            page.insert_text((38, 562), "• Individual cartons barcoded with serialised consignment labels.", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
            page.insert_text((38, 576), "• Strapped with heavy-duty polypropylene bands on wooden pallets.", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
            page.insert_text((38, 590), "• Tare weight per carton deducted from gross weighbridge mass.", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
            page.insert_text((38, 604), "• Physical count matches declared customs quantity.", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)

        # Right Signatory & Vector Stamp Box
        page.draw_rect(pymupdf.Rect(328, 532, 565, 638), fill=cls.BG_WHITE, color=cls.BORDER_COLOR, width=0.8)
        page.insert_text((336, 546), "Certified Packaging & Warehouse Inspector:", fontname="hebo", fontsize=7.2, color=cls.NAVY_DARK)

        # Vector Stamp
        cls._draw_stamp(page, 446, 588, "PACKING AUDIT", "DEMO SPECIMEN", date)

        page.insert_text((336, 626), "[SIMULATED WAREHOUSE DISPATCH STAMP — DEMO ONLY]", fontname="hebi", fontsize=6.5, color=cls.NAVY_MID)
        page.insert_text((336, 634), "Warehouse Packaging Facility (Simulated Dispatch Seal)", fontname="helv", fontsize=6.2, color=cls.SLATE_MUTED)

        # 8. Digital Security Barcode Strip
        cls._draw_barcode(page, 30, 646, 535, 42, f"PL-{inv_ref[:12] if '[Not provided' not in inv_ref else 'DEMO-2026'}")

        # 9. Customs Note Box
        page.draw_rect(pymupdf.Rect(30, 696, 565, 788), fill=cls.BG_ZEBRA, color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((38, 708), "CUSTOMS RECONCILIATION DIRECTIVE:", fontname="hebo", fontsize=6.8, color=cls.NAVY_MID)
        notes = (
            "1. Gross Weight declared on Packing List must align with Commercial Invoice and Bill of Lading.\n"
            "2. Any variance exceeding tolerance (+/- 1.0 kg) flags RULE_GROSS_WEIGHT_CONSISTENCY for manual review.\n"
            "3. Package counts and numbers match simulated cargo verification at Nhava Sheva CFS depot.\n"
            "4. Generated by CargoLens AI Enterprise Demonstration & Automated Verification System."
        )
        page.insert_textbox(pymupdf.Rect(38, 714, 555, 782), notes, fontname="helv", fontsize=6.5, color=cls.SLATE_MUTED)

    # =========================================================================
    # 3. BILL OF LADING — PROFESSIONAL SHIPPING DOCUMENT
    # =========================================================================
    @classmethod
    def _draw_bill_of_lading(
        cls,
        page: pymupdf.Page,
        title: str,
        parsed: Dict[str, str],
        other: List[str],
        is_low_conf: bool,
    ):
        # Double Corporate Frame
        page.draw_rect(pymupdf.Rect(28, 28, 567, 800), color=cls.BORDER_DARK, width=1.0)
        page.draw_rect(pymupdf.Rect(30, 30, 565, 798), color=cls.BORDER_COLOR, width=0.5)

        # 1. Carrier Header Banner
        page.draw_rect(pymupdf.Rect(30, 30, 565, 108), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.8)
        cls._draw_emblem(page, 42, 42, "bol")

        doc_heading = title.upper() if title else "OCEAN BILL OF LADING"
        page.insert_text((86, 50), "INTERNATIONAL OCEAN CONTAINER LINE", fontname="hebo", fontsize=10.5, color=cls.NAVY_MID)
        page.insert_text((86, 66), doc_heading, fontname="hebo", fontsize=15, color=cls.NAVY_DARK)
        page.insert_text(
            (86, 80),
            "ORIGINAL BILL OF LADING — NON-NEGOTIABLE UNLESS CONSIGNED 'TO ORDER'",
            fontname="helv",
            fontsize=6.8,
            color=cls.SLATE_MUTED,
        )

        badge = "SYNTHETIC DEMONSTRATION DATA"
        if is_low_conf:
            badge += " [LOW_CONFIDENCE]"
        page.insert_text((86, 95), badge, fontname="hebo", fontsize=7.0, color=cls.ACCENT_AMBER)

        # Header Right Metadata Block
        bl_num = cls._clean_prefix(cls._get(parsed, "bill of lading number", "b/l number", "bl number", default="BL-2026-9011"), r"^(?:bill\s*of\s*lading\s*number|b/l\s*number|bl\s*number):\s*")
        date = cls._clean_prefix(cls._get(parsed, "date", default="2026-10-18"), r"^date:\s*")

        page.draw_rect(pymupdf.Rect(355, 36, 558, 102), fill=cls.BG_WHITE, color=cls.BORDER_COLOR, width=0.6)
        page.insert_text((362, 50), f"Bill of Lading Number: {bl_num}", fontname="hebo", fontsize=8.0, color=cls.NAVY_DARK)
        page.insert_text((362, 63), f"Date of Issue: {date}", fontname="helv", fontsize=7.8, color=cls.SLATE_DARK)
        page.insert_text((362, 76), "Ocean Transport Document", fontname="hebo", fontsize=7.8, color=cls.NAVY_MID)
        page.insert_text((362, 88), "Carrier Booking: MSC-INNSA-9821", fontname="helv", fontsize=7.2, color=cls.SLATE_MUTED)

        # 2. Shipping Parties: Shipper, Consignee, Notify Party
        # Shipper (Top Left)
        page.draw_rect(pymupdf.Rect(30, 108, 297, 185), color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(30, 108, 297, 122), fill=cls.NAVY_MID, color=cls.NAVY_MID, width=0)
        page.insert_text((38, 118), "1. SHIPPER (CONSIGNOR):", fontname="hebo", fontsize=7.0, color=(1, 1, 1))

        shipper = cls._clean_prefix(cls._get(parsed, "shipper", "exporter", "seller", default="[Not provided in source declaration]"), r"^(?:shipper|exporter|seller):\s*")
        page.insert_text((38, 134), f"Shipper: {shipper}", fontname="hebo", fontsize=7.8, color=cls.NAVY_DARK if "[Not provided" not in shipper else cls.SLATE_MUTED)
        page.insert_text((38, 147), "Commercial Ocean Freight Consignor", fontname="helv", fontsize=7.2, color=cls.SLATE_MUTED)
        page.insert_text((38, 159), "Port Cargo Dispatch Terminal — Container Depot", fontname="helv", fontsize=6.8, color=cls.SLATE_MUTED)
        page.insert_text((38, 171), "Shipper Load, Stow & Count (SLAC)", fontname="hebi", fontsize=6.5, color=(0.50, 0.55, 0.62))

        # Consignee (Top Right)
        page.draw_rect(pymupdf.Rect(297, 108, 565, 185), color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(297, 108, 565, 122), fill=cls.NAVY_MID, color=cls.NAVY_MID, width=0)
        page.insert_text((305, 118), "2. CONSIGNEE (OR ORDER):", fontname="hebo", fontsize=7.0, color=(1, 1, 1))

        consignee = cls._clean_prefix(cls._get(parsed, "consignee", "buyer", "importer", default="[Not provided in source declaration]"), r"^(?:consignee|buyer|importer):\s*")
        page.insert_text((305, 134), f"Consignee: {consignee}", fontname="hebo", fontsize=7.8, color=cls.NAVY_DARK if "[Not provided" not in consignee else cls.SLATE_MUTED)
        page.insert_text((305, 147), "Delivery at Nhava Sheva (INNSA) Port CFS Terminal", fontname="helv", fontsize=7.2, color=cls.SLATE_MUTED)
        page.insert_text((305, 159), "Jawaharlal Nehru Port Trust Node — Customs Cleared Hub", fontname="helv", fontsize=6.8, color=cls.SLATE_MUTED)
        page.insert_text((305, 171), "Endorsement: Non-Negotiable unless Consigned to Order", fontname="hebi", fontsize=6.5, color=(0.50, 0.55, 0.62))

        # Notify Party (Bottom Left) & Routing (Bottom Right)
        page.draw_rect(pymupdf.Rect(30, 185, 297, 246), color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(30, 185, 297, 199), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((38, 195), "3. NOTIFY PARTY (CARRIER AGENT / BROKER):", fontname="hebo", fontsize=6.8, color=cls.NAVY_MID)

        notify = cls._clean_prefix(cls._get(parsed, "notify party", "notify", default=consignee), r"^notify(?:\s*party)?:\s*")
        page.insert_text((38, 211), f"Notify Party: {notify}", fontname="hebo", fontsize=7.8, color=cls.NAVY_DARK if "[Not provided" not in notify else cls.SLATE_MUTED)
        page.insert_text((38, 224), "Customs Broker & Clearing Agent — Port of Nhava Sheva", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
        page.insert_text((38, 236), "Contact: JNPT Logistics CFS Terminal Operations", fontname="helv", fontsize=6.8, color=cls.SLATE_MUTED)

        # Routing Box (Bottom Right)
        page.draw_rect(pymupdf.Rect(297, 185, 565, 246), fill=cls.BG_ZEBRA, color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(297, 185, 565, 199), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((305, 195), "4. OCEAN ROUTING & VESSEL PARTICULAR:", fontname="hebo", fontsize=6.8, color=cls.NAVY_MID)

        vessel = cls._clean_prefix(cls._get(parsed, "vessel", default="CMA CGM BIANCA"), r"^vessel:\s*")
        voyage = cls._clean_prefix(cls._get(parsed, "voyage", default="041W"), r"^voyage:\s*")
        pol = cls._clean_prefix(cls._get(parsed, "port of loading", default="Port of Loading"), r"^port\s*of\s*loading:\s*")
        pod = cls._clean_prefix(cls._get(parsed, "port of discharge", default="Nhava Sheva (INNSA), India"), r"^port\s*of\s*discharge:\s*")

        page.insert_text((305, 211), f"Vessel: {vessel}", fontname="hebo", fontsize=7.5, color=cls.NAVY_DARK)
        page.insert_text((435, 211), f"Voyage: {voyage}", fontname="helv", fontsize=7.5, color=cls.SLATE_DARK)
        page.insert_text((305, 225), f"Port of Loading: {pol}", fontname="helv", fontsize=7.2, color=cls.SLATE_DARK)
        page.insert_text((305, 238), f"Port of Discharge: {pod}", fontname="hebo", fontsize=7.5, color=cls.NAVY_MID)

        # 3. Cargo Table Header
        page.draw_rect(pymupdf.Rect(30, 252, 565, 273), fill=cls.NAVY_MID, color=cls.NAVY_MID, width=0)
        page.insert_text((36, 266), "Container & Seal Numbers", fontname="hebo", fontsize=7.2, color=(1, 1, 1))
        page.insert_text((190, 266), "Package Count", fontname="hebo", fontsize=7.2, color=(1, 1, 1))
        page.insert_text((275, 266), "Description of Packages & Goods", fontname="hebo", fontsize=7.2, color=(1, 1, 1))
        page.insert_text((470, 266), "Gross Weight (KG)", fontname="hebo", fontsize=7.2, color=(1, 1, 1))

        # 3. Cargo Table Row
        container = cls._clean_prefix(cls._get(parsed, "container numbers", "container", default="CMAU7891234"), r"^container(?:\s*numbers)?:\s*")
        seal = cls._clean_prefix(cls._get(parsed, "seal numbers", "seal", default="CMA9821034"), r"^seal(?:\s*numbers)?:\s*")
        pkg_cnt = cls._clean_prefix(cls._get(parsed, "package count", "packages", default="60 Pallets"), r"^package\s*count:\s*")
        goods_desc = cls._clean_prefix(cls._get(parsed, "goods description", "item", "description", default="Commercial Containerized Merchandise"), r"^(?:goods\s*description|description|item):\s*")
        gross_wt = cls._clean_prefix(cls._get(parsed, "gross weight", default="14,400.00 KG"), r"^gross\s*weight:\s*")

        page.draw_rect(pymupdf.Rect(30, 273, 565, 362), fill=cls.BG_WHITE, color=cls.BORDER_COLOR, width=0.8)
        for col_x in [185, 270, 465]:
            page.draw_line(pymupdf.Point(col_x, 273), pymupdf.Point(col_x, 362), color=cls.BORDER_COLOR, width=0.4)

        # CRUCIAL: Format as "Container Numbers: {container}" for fixture provider regex
        page.insert_text((36, 298), f"Container Numbers: {container}", fontname="hebo", fontsize=7.8, color=cls.NAVY_DARK)
        page.insert_text((36, 314), f"Seal Numbers: {seal}", fontname="helv", fontsize=7.5, color=cls.SLATE_DARK)
        page.insert_text((36, 328), "Type: 1 x 40ft High Cube Container", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)

        page.insert_text((190, 298), f"Package Count: {pkg_cnt}", fontname="hebo", fontsize=7.8, color=cls.SLATE_DARK)
        page.insert_text((190, 314), "Package Type: SEAWORTHY", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)

        # Dedicated line for Goods Description ensures single-line OCR extraction without truncation
        page.insert_text((275, 298), f"Goods Description: {goods_desc}", fontname="hebo", fontsize=7.8, color=cls.NAVY_DARK)
        page.insert_text((275, 314), "Shipper Load, Stow and Count (SLAC) | Clean on Board", fontname="helv", fontsize=7.2, color=cls.SLATE_MUTED)
        page.insert_text((275, 328), "Ocean Freight Standard Containerized Merchandise", fontname="hebi", fontsize=6.8, color=(0.50, 0.55, 0.62))

        page.insert_text((470, 298), f"Gross Weight: {gross_wt}", fontname="hebo", fontsize=8.5, color=cls.NAVY_DARK)

        # 4. Freight & Charges Box (Left)
        page.draw_rect(pymupdf.Rect(30, 370, 330, 460), fill=cls.BG_WHITE, color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(30, 370, 330, 386), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((38, 381), "FREIGHT & CHARGES SPECIFICATION:", fontname="hebo", fontsize=7.0, color=cls.NAVY_MID)

        page.insert_text((38, 401), "Freight Terms: FREIGHT PREPAID", fontname="hebo", fontsize=8.2, color=cls.NAVY_DARK)
        page.insert_text((38, 417), "Movement: CY / CY (Container Yard to Container Yard)", fontname="helv", fontsize=7.5, color=cls.SLATE_DARK)
        page.insert_text((38, 432), "Delivery CFS: Nhava Sheva (INNSA) Port Terminal", fontname="helv", fontsize=7.2, color=cls.SLATE_MUTED)
        page.insert_text((38, 446), "Service: Direct Port-to-Port Liner Service", fontname="helv", fontsize=6.8, color=cls.SLATE_MUTED)

        # 4. Carrier Totals Card (Right)
        page.draw_rect(pymupdf.Rect(338, 370, 565, 460), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(338, 370, 565, 386), fill=cls.NAVY_MID, color=cls.NAVY_MID, width=0)
        page.insert_text((346, 381), "CARRIER CONSIGNMENT TOTALS:", fontname="hebo", fontsize=7.0, color=(1, 1, 1))

        page.insert_text((346, 401), "Total Containers: 1 x 40ft High Cube Container", fontname="helv", fontsize=7.8, color=cls.SLATE_DARK)
        page.insert_text((346, 415), f"Declared Packages: {pkg_cnt}", fontname="helv", fontsize=7.8, color=cls.SLATE_DARK)
        page.draw_line(pymupdf.Point(346, 424), pymupdf.Point(555, 424), color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((346, 444), f"Gross Weight: {gross_wt}", fontname="hebo", fontsize=11.5, color=cls.NAVY_DARK)

        # 5. Conditions of Carriage Box
        page.draw_rect(pymupdf.Rect(30, 468, 565, 532), fill=cls.BG_WHITE, color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(30, 468, 565, 482), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((38, 478), "CONDITIONS OF CARRIAGE SPECIMEN & NOTICE:", fontname="hebo", fontsize=6.8, color=cls.NAVY_MID)
        terms_text = (
            "Standard ocean carriage conditions specimen for demonstration purposes. Received by the Carrier in apparent good order "
            "and condition, unless otherwise indicated herein, the goods or packages specified above for carriage subject to standard terms. "
            "Three (3) original Bills of Lading simulated; non-negotiable demonstration copy."
        )
        page.insert_textbox(pymupdf.Rect(38, 486, 555, 528), terms_text, fontname="helv", fontsize=6.8, color=cls.SLATE_MUTED)

        # 6. Special Instructions & Carrier Signatory Block
        page.draw_rect(pymupdf.Rect(30, 540, 320, 642), color=cls.BORDER_COLOR, width=0.8)
        page.draw_rect(pymupdf.Rect(30, 540, 320, 554), fill=cls.NAVY_LIGHT, color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((38, 550), "SPECIAL INSTRUCTIONS & STOWAGE ENDORSEMENTS:", fontname="hebo", fontsize=6.8, color=cls.NAVY_MID)
        if other:
            other_text = "\n".join(other[:4])
            page.insert_textbox(pymupdf.Rect(38, 558, 312, 636), other_text, fontname="helv", fontsize=7.2, color=cls.SLATE_DARK)
        else:
            page.insert_text((38, 568), "• Stow under deck in secure refrigerated / dry container cell.", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
            page.insert_text((38, 582), "• Notify customs broker 48 hours prior to vessel berthing at JNPT.", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
            page.insert_text((38, 596), "• Empty container return to nominated Nhava Sheva depot.", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)
            page.insert_text((38, 610), "• Three (3) original Bills of Lading issued.", fontname="helv", fontsize=7.0, color=cls.SLATE_MUTED)

        # Right Signatory & Vector Stamp Box
        page.draw_rect(pymupdf.Rect(328, 540, 565, 642), fill=cls.BG_WHITE, color=cls.BORDER_COLOR, width=0.8)
        page.insert_text((336, 554), "Signed for the Carrier / Agent as Master:", fontname="hebo", fontsize=7.2, color=cls.NAVY_DARK)

        # Vector Stamp
        cls._draw_stamp(page, 446, 594, "CARRIER NOTICE", "DEMO ENDORSED", date)

        page.insert_text((336, 630), "[SIMULATED CARRIER ENDORSEMENT — DEMO ONLY]", fontname="hebi", fontsize=6.5, color=cls.NAVY_MID)
        page.insert_text((336, 638), "Ocean Carrier Port Agent (Simulated Non-Negotiable Specimen)", fontname="helv", fontsize=6.2, color=cls.SLATE_MUTED)

        # 7. Digital Security Barcode Strip
        cls._draw_barcode(page, 30, 650, 535, 42, f"BL-{bl_num[:14]}")

        # 8. Carrier Note Box
        page.draw_rect(pymupdf.Rect(30, 700, 565, 788), fill=cls.BG_ZEBRA, color=cls.BORDER_COLOR, width=0.5)
        page.insert_text((38, 712), "OCEAN CARRIER DELIVERY ADVISORY:", fontname="hebo", fontsize=6.8, color=cls.NAVY_MID)
        notes = (
            "1. Goods will be delivered only against surrender of one duly endorsed original Bill of Lading.\n"
            "2. Port storage, demurrage, and detention charges are payable in accordance with carrier tariff at Nhava Sheva (INNSA).\n"
            "3. Cross-document validation requires Gross Weight to correspond with Packing List and Commercial Invoice.\n"
            "4. Generated by CargoLens AI Enterprise Demonstration & Automated Verification System."
        )
        page.insert_textbox(pymupdf.Rect(38, 718, 555, 782), notes, fontname="helv", fontsize=6.5, color=cls.SLATE_MUTED)


def create_synthetic_pdf(title: str, lines: List[str], is_low_confidence: bool = False) -> bytes:
    """
    Drop-in replacement for create_synthetic_pdf that delegates to TradePdfGenerator.
    Produces visually rich, professional business documents with structured tables,
    borders, corporate headers, vector stamps, barcodes, and crisp typography.
    """
    return TradePdfGenerator.generate(title, lines, is_low_confidence=is_low_confidence)

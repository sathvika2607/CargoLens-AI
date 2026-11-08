from typing import Dict, Any
from app.models.document import DocumentType

SYSTEM_INSTRUCTION = """You are an expert customs documentation intelligence engine specializing in international shipping documents for customs clearance at Nhava Sheva (JNPT), India.

Your objective is to extract structured information with high fidelity and exact evidence from shipping documents.

CRITICAL RULES:
1. EXACT EXTRACTION: Extract only what is explicitly written in the document.
2. NO INVENTING OR INFERRING: Never guess, hallucinate, or infer missing values. If a field is not present or illegible, return null.
3. PRESERVE ORIGINAL VALUES: Do not convert currencies or units. If weight is in LBS or KG, keep it as reported.
4. CONFIDENCE: Provide a realistic confidence score between 0.0 and 1.0 reflecting OCR clarity and legibility. If absent, confidence must be null.
5. NO TAX/DUTY CALCULATIONS: Do not calculate customs duties or taxes.
6. NO ASSUMED DEFAULTS: Never assume USD or any currency if not explicitly stated.
7. EVIDENCE: Include the exact text snippet from the document where the value appears, and the 1-based page number.
8. RETURN RAW JSON ONLY: Do not wrap in markdown quotes or preamble. Return only the JSON object.
"""

COMMERCIAL_INVOICE_PROMPT = """Extract the Commercial Invoice into a valid JSON object matching this structure:
{
  "invoice_number": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "invoice_date": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "seller_name": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "seller_address": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "buyer_name": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "buyer_address": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "currency": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "incoterm": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "line_items": [
    {
      "item_number": int or null,
      "description": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
      "hsn_code": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
      "quantity": {"value": number/string or null, "normalized_value": number/string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
      "unit_of_measure": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
      "unit_price": {"value": number/string or null, "normalized_value": number/string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
      "line_total": {"value": number/string or null, "normalized_value": number/string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null}
    }
  ],
  "subtotal": {"value": number/string or null, "normalized_value": number/string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "freight_charges": {"value": number/string or null, "normalized_value": number/string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "insurance_charges": {"value": number/string or null, "normalized_value": number/string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "other_charges": {"value": number/string or null, "normalized_value": number/string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "grand_total": {"value": number/string or null, "normalized_value": number/string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "gross_weight_kg": {"value": number/string or null, "normalized_value": number/string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "net_weight_kg": {"value": number/string or null, "normalized_value": number/string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "package_count": {"value": int or null, "normalized_value": int or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null}
}
"""

PACKING_LIST_PROMPT = """Extract the Packing List into a valid JSON object matching this structure:
{
  "exporter_name": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "importer_name": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "invoice_reference": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "line_items": [
    {
      "item_number": int or null,
      "description": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
      "quantity": {"value": number/string or null, "normalized_value": number/string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
      "unit_of_measure": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
      "package_count": {"value": int or null, "normalized_value": int or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
      "package_type": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null}
    }
  ],
  "package_count": {"value": int or null, "normalized_value": int or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "package_type": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "gross_weight_kg": {"value": number/string or null, "normalized_value": number/string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "net_weight_kg": {"value": number/string or null, "normalized_value": number/string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "dimensions": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "container_numbers": [
    {"value": string, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null}
  ],
  "marks_and_numbers": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null}
}
"""

BILL_OF_LADING_PROMPT = """Extract the Bill of Lading into a valid JSON object matching this structure:
{
  "bl_number": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "shipper_name": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "consignee_name": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "notify_party": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "vessel_name": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "voyage_number": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "port_of_loading": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "port_of_discharge": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "place_of_receipt": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "place_of_delivery": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "container_numbers": [
    {"value": string, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null}
  ],
  "seal_numbers": [
    {"value": string, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null}
  ],
  "package_count": {"value": int or null, "normalized_value": int or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "goods_description": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "gross_weight_kg": {"value": number/string or null, "normalized_value": number/string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "measurement_volume_cbm": {"value": number/string or null, "normalized_value": number/string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null},
  "issue_date": {"value": string or null, "normalized_value": string or null, "confidence": float or null, "source_page_number": int or null, "evidence_text": string or null}
}
"""

PROMPTS_BY_TYPE = {
    DocumentType.COMMERCIAL_INVOICE: COMMERCIAL_INVOICE_PROMPT,
    DocumentType.PACKING_LIST: PACKING_LIST_PROMPT,
    DocumentType.BILL_OF_LADING: BILL_OF_LADING_PROMPT,
}

import base64
import json
import logging
import time
from typing import Dict, Any, List, Optional
import anthropic

from app.config import settings
from app.models.document import DocumentType
from app.services.ai.base import (
    BaseExtractionProvider,
    DocumentPageInput,
    RawProviderResult,
    ExtractionProviderError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderAPIError,
    ProviderOutputError,
)
from app.services.ai.prompts import SYSTEM_INSTRUCTION, PROMPTS_BY_TYPE

logger = logging.getLogger("cargolens.ai.claude")


class ClaudeVisionExtractionProvider(BaseExtractionProvider):
    """
    Structured document extraction provider using Anthropic Claude Vision and Text.
    Supports:
    - Configurable models via environment variable (default: claude-sonnet-5-5).
    - Page-level mixed digital/scanned PDF handling (HYBRID modality).
    - Bounded image payloads and batch processing.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        client: Optional[anthropic.AsyncAnthropic] = None,
    ):
        self._api_key = api_key or settings.ANTHROPIC_API_KEY
        self._model = model or settings.ANTHROPIC_MODEL
        self._timeout_seconds = timeout_seconds or settings.ANTHROPIC_TIMEOUT_SECONDS
        self._max_retries = max_retries or settings.ANTHROPIC_MAX_RETRIES
        self._custom_client = client

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._model

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._custom_client:
            return self._custom_client

        if not self._api_key or not self._api_key.strip():
            raise ProviderConfigurationError(
                "Anthropic API key is not configured. Please set ANTHROPIC_API_KEY in environment or .env."
            )

        return anthropic.AsyncAnthropic(
            api_key=self._api_key.strip(),
            timeout=self._timeout_seconds,
            max_retries=self._max_retries,
        )

    @staticmethod
    def _clean_json_response(raw_text: str) -> Dict[str, Any]:
        """Strips markdown fences and parses JSON safely."""
        text = raw_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ProviderOutputError(
                f"Failed to parse Claude output as valid JSON: {str(e)}. Response snippet: {raw_text[:200]!r}"
            ) from e

    async def extract_pages_batch(
        self,
        document_type: DocumentType,
        pages: List[DocumentPageInput],
    ) -> RawProviderResult:
        """
        Executes structured document extraction on a batch of individual pages,
        supporting mixed digital-text and scanned page modalities simultaneously.
        """
        if not pages:
            raise ExtractionProviderError("No pages provided for batch extraction.")

        type_prompt = PROMPTS_BY_TYPE.get(document_type)
        if not type_prompt:
            raise ExtractionProviderError(f"Unsupported document type for extraction: {document_type}")

        client = self._get_client()

        has_digital = any(p.is_digital_text for p in pages)
        has_scanned = any(not p.is_digital_text for p in pages)

        if has_digital and has_scanned:
            extraction_mode = "HYBRID"
        elif has_digital:
            extraction_mode = "TEXT_FIRST"
        else:
            extraction_mode = "VISION"

        page_range_str = f"pages {pages[0].page_number} to {pages[-1].page_number}"
        batch_header = (
            f"{type_prompt}\n\n"
            f"You are extracting from {page_range_str} of the document.\n"
            f"Some pages are presented as digital text excerpts, and others as scanned page images.\n"
            f"Always record the accurate 'source_page_number' for every extracted field."
        )

        messages_content: List[Dict[str, Any]] = [
            {"type": "text", "text": batch_header}
        ]

        # Process each individual page in its native modality (bounding images to max payload)
        image_count = 0
        for page in pages:
            if page.is_digital_text and page.text_content and page.text_content.strip():
                messages_content.append({
                    "type": "text",
                    "text": (
                        f"--- PAGE {page.page_number} (DIGITAL TEXT) ---\n"
                        f"{page.text_content.strip()}\n"
                        f"--- END PAGE {page.page_number} ---"
                    )
                })
            elif page.image_bytes:
                if image_count >= settings.STRUCTURED_EXTRACTION_MAX_IMAGE_PAGES:
                    continue
                image_count += 1
                img_mime = page.mime_type or "image/jpeg"
                if "png" in img_mime.lower():
                    img_mime = "image/png"
                else:
                    img_mime = "image/jpeg"

                b64_data = base64.b64encode(page.image_bytes).decode("utf-8")
                messages_content.append({
                    "type": "text",
                    "text": f"--- PAGE {page.page_number} (SCANNED IMAGE) ---",
                })
                messages_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img_mime,
                        "data": b64_data,
                    }
                })
            else:
                # Page without text or image
                messages_content.append({
                    "type": "text",
                    "text": f"--- PAGE {page.page_number} (EMPTY / UNREADABLE) ---",
                })

        start_time = time.monotonic()

        try:
            response = await client.messages.create(
                model=self._model,
                max_tokens=4096,
                temperature=0.0,
                system=SYSTEM_INSTRUCTION,
                messages=[{"role": "user", "content": messages_content}],
            )
        except anthropic.RateLimitError as e:
            logger.warning(f"Anthropic rate limit encountered: {e}")
            raise ProviderRateLimitError(f"Anthropic rate limit exceeded: {str(e)}") from e
        except anthropic.APITimeoutError as e:
            logger.warning(f"Anthropic API timeout encountered: {e}")
            raise ProviderTimeoutError(f"Anthropic request timed out: {str(e)}") from e
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise ProviderAPIError(f"Anthropic API error: {str(e)}") from e
        except Exception as e:
            if isinstance(e, (ProviderConfigurationError, ExtractionProviderError)):
                raise
            logger.error(f"Unexpected error communicating with Anthropic API: {e}")
            raise ExtractionProviderError(f"AI provider communication failure: {str(e)}") from e

        latency = round(time.monotonic() - start_time, 3)

        response_text = ""
        for block in response.content:
            if getattr(block, "type", None) == "text":
                response_text += getattr(block, "text", "")

        parsed_data = self._clean_json_response(response_text)

        token_usage = {
            "input_tokens": getattr(response.usage, "input_tokens", 0),
            "output_tokens": getattr(response.usage, "output_tokens", 0),
        }

        return RawProviderResult(
            data=parsed_data,
            provider=self.provider_name,
            model=self.model_name,
            extraction_mode=extraction_mode,
            token_usage=token_usage,
            latency_seconds=latency,
        )

    async def extract_structured(
        self,
        document_type: DocumentType,
        text_content: Optional[str] = None,
        page_images: Optional[List[bytes]] = None,
        mime_type: Optional[str] = None,
    ) -> RawProviderResult:
        """
        Backward-compatible helper converting flat text/images into DocumentPageInput.
        """
        pages: List[DocumentPageInput] = []

        if text_content and text_content.strip():
            pages.append(
                DocumentPageInput(
                    page_number=1,
                    is_digital_text=True,
                    text_content=text_content.strip(),
                )
            )
        elif page_images:
            bounded_images = page_images[: settings.STRUCTURED_EXTRACTION_MAX_IMAGE_PAGES]
            for idx, img_bytes in enumerate(bounded_images, start=1):
                pages.append(
                    DocumentPageInput(
                        page_number=idx,
                        is_digital_text=False,
                        image_bytes=img_bytes,
                        mime_type=mime_type or "image/jpeg",
                    )
                )
        else:
            raise ExtractionProviderError(
                "Neither text content nor page images were provided for document extraction."
            )

        return await self.extract_pages_batch(document_type=document_type, pages=pages)

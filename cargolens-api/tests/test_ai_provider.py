import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import anthropic

from app.models.document import DocumentType
from app.services.ai.base import (
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderAPIError,
    ProviderOutputError,
)
from app.services.ai.claude_provider import ClaudeVisionExtractionProvider


@pytest.mark.asyncio
async def test_missing_api_key_raises_configuration_error():
    """Verifies that attempting extraction without an API key raises ProviderConfigurationError."""
    provider = ClaudeVisionExtractionProvider(api_key="")
    with pytest.raises(ProviderConfigurationError) as exc_info:
        await provider.extract_structured(
            document_type=DocumentType.COMMERCIAL_INVOICE,
            text_content="Sample extracted text",
        )
    assert "Anthropic API key is not configured" in str(exc_info.value)


@pytest.mark.asyncio
async def test_text_first_mode_selection_and_parsing():
    """Verifies that digital text selects TEXT_FIRST mode and parses JSON correctly."""
    mock_client = AsyncMock()
    mock_response = MagicMock()

    # Mock JSON response from Claude
    sample_payload = {
        "invoice_number": {"value": "INV-2026-001", "confidence": 0.98},
        "currency": {"value": "USD", "confidence": 0.99},
        "grand_total": {"value": "15000.00", "confidence": 0.97},
    }

    # Mock text block inside message content
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = f"```json\n{json.dumps(sample_payload)}\n```"
    mock_response.content = [mock_block]
    mock_response.usage.input_tokens = 500
    mock_response.usage.output_tokens = 150

    mock_client.messages.create.return_value = mock_response

    provider = ClaudeVisionExtractionProvider(api_key="mock-key", client=mock_client)
    result = await provider.extract_structured(
        document_type=DocumentType.COMMERCIAL_INVOICE,
        text_content="Commercial Invoice document with plenty of digital text content extracted from PDF.",
    )

    assert result.extraction_mode == "TEXT_FIRST"
    assert result.provider == "anthropic"
    assert result.data["invoice_number"]["value"] == "INV-2026-001"
    assert result.data["currency"]["value"] == "USD"
    assert result.token_usage["input_tokens"] == 500


@pytest.mark.asyncio
async def test_vision_mode_selection_with_bounded_images():
    """Verifies that lack of digital text triggers VISION mode with bounded images."""
    mock_client = AsyncMock()
    mock_response = MagicMock()

    sample_payload = {
        "exporter_name": {"value": "Export Corp", "confidence": 0.90},
        "gross_weight_kg": {"value": "3165.00", "confidence": 0.92},
    }
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = json.dumps(sample_payload)
    mock_response.content = [mock_block]
    mock_response.usage.input_tokens = 1200
    mock_response.usage.output_tokens = 200
    mock_client.messages.create.return_value = mock_response

    provider = ClaudeVisionExtractionProvider(api_key="mock-key", client=mock_client)

    # Provide 7 page images: provider should bound to at most 5
    fake_images = [b"fake_jpeg_page_bytes" for _ in range(7)]
    result = await provider.extract_structured(
        document_type=DocumentType.PACKING_LIST,
        text_content=None,
        page_images=fake_images,
        mime_type="application/pdf",
    )

    assert result.extraction_mode == "VISION"
    assert result.data["gross_weight_kg"]["value"] == "3165.00"

    # Verify that messages.create was called with at most 5 images
    call_args = mock_client.messages.create.call_args[1]
    messages = call_args["messages"]
    content_blocks = messages[0]["content"]
    image_blocks = [b for b in content_blocks if b.get("type") == "image"]
    assert len(image_blocks) == 5  # Bounded to max configured (5)


@pytest.mark.asyncio
async def test_rate_limit_error_handling():
    """Verifies that Anthropic RateLimitError is translated to ProviderRateLimitError."""
    mock_client = AsyncMock()
    mock_client.messages.create.side_effect = anthropic.RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429),
        body={"error": {"message": "Rate limit exceeded"}},
    )

    provider = ClaudeVisionExtractionProvider(api_key="mock-key", client=mock_client)
    with pytest.raises(ProviderRateLimitError) as exc_info:
        await provider.extract_structured(
            document_type=DocumentType.COMMERCIAL_INVOICE,
            text_content="Sample digital text for testing rate limit handling.",
        )
    assert "Rate limit" in str(exc_info.value)


@pytest.mark.asyncio
async def test_timeout_error_handling():
    """Verifies that Anthropic APITimeoutError is translated to ProviderTimeoutError."""
    mock_client = AsyncMock()
    mock_client.messages.create.side_effect = anthropic.APITimeoutError(
        request=MagicMock()
    )

    provider = ClaudeVisionExtractionProvider(api_key="mock-key", client=mock_client)
    with pytest.raises(ProviderTimeoutError) as exc_info:
        await provider.extract_structured(
            document_type=DocumentType.COMMERCIAL_INVOICE,
            text_content="Sample digital text for testing timeout handling.",
        )
    assert "timed out" in str(exc_info.value)


@pytest.mark.asyncio
async def test_malformed_json_response_handling():
    """Verifies that malformed JSON from upstream AI raises ProviderOutputError."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "This is not valid JSON at all: {invoice_number: }"
    mock_response.content = [mock_block]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_client.messages.create.return_value = mock_response

    provider = ClaudeVisionExtractionProvider(api_key="mock-key", client=mock_client)
    with pytest.raises(ProviderOutputError) as exc_info:
        await provider.extract_structured(
            document_type=DocumentType.COMMERCIAL_INVOICE,
            text_content="Sample digital text for testing malformed JSON handling.",
        )
    assert "Failed to parse Claude output as valid JSON" in str(exc_info.value)


@pytest.mark.asyncio
async def test_claude_model_configuration_respected():
    """Verifies that the configured Claude model ID is forwarded to the Anthropic SDK."""
    from app.config import settings

    # Default model should be claude-sonnet-5-5
    default_provider = ClaudeVisionExtractionProvider(api_key="mock-key")
    assert default_provider.model_name == settings.ANTHROPIC_MODEL
    assert default_provider.model_name == "claude-sonnet-5-5"

    # Custom model passed explicitly
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = json.dumps({"invoice_number": {"value": "INV-123", "confidence": 0.95}})
    mock_response.content = [mock_block]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_client.messages.create.return_value = mock_response

    custom_provider = ClaudeVisionExtractionProvider(
        api_key="mock-key",
        model="claude-sonnet-5-5-custom-id",
        client=mock_client,
    )
    assert custom_provider.model_name == "claude-sonnet-5-5-custom-id"

    result = await custom_provider.extract_structured(
        document_type=DocumentType.COMMERCIAL_INVOICE,
        text_content="Sample digital text content",
    )
    assert result.model == "claude-sonnet-5-5-custom-id"

    # Verify messages.create received the exact configured model string
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-sonnet-5-5-custom-id"


@pytest.mark.asyncio
async def test_mixed_digital_and_scanned_pdf_pages_batch_handling():
    """
    Verifies that a mixed digital/scanned document:
    1. Selects HYBRID mode.
    2. Sends digital text for digital pages.
    3. Sends image blocks for scanned pages.
    4. Never skips scanned pages.
    """
    from app.services.ai.base import DocumentPageInput

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = json.dumps({
        "invoice_number": {"value": "INV-HYBRID-99", "confidence": 0.97, "source_page_number": 1},
        "gross_weight_kg": {"value": "4500.00", "confidence": 0.91, "source_page_number": 2},
    })
    mock_response.content = [mock_block]
    mock_response.usage.input_tokens = 800
    mock_response.usage.output_tokens = 120
    mock_client.messages.create.return_value = mock_response

    provider = ClaudeVisionExtractionProvider(api_key="mock-key", client=mock_client)

    # Page 1: digital text
    p1 = DocumentPageInput(
        page_number=1,
        is_digital_text=True,
        text_content="Page 1: Digital invoice text with details",
    )
    # Page 2: scanned image
    p2 = DocumentPageInput(
        page_number=2,
        is_digital_text=False,
        image_bytes=b"dummy_scanned_jpeg_page_bytes",
        mime_type="image/jpeg",
    )

    result = await provider.extract_pages_batch(
        document_type=DocumentType.COMMERCIAL_INVOICE,
        pages=[p1, p2],
    )

    assert result.extraction_mode == "HYBRID"
    assert result.data["invoice_number"]["value"] == "INV-HYBRID-99"

    # Inspect the payload sent to the Anthropic SDK
    call_kwargs = mock_client.messages.create.call_args[1]
    messages = call_kwargs["messages"]
    content_blocks = messages[0]["content"]

    # Block 0: Header prompt
    assert "pages 1 to 2" in content_blocks[0]["text"]

    # Verify Page 1 digital text block is present
    page1_blocks = [b for b in content_blocks if b.get("type") == "text" and "PAGE 1 (DIGITAL TEXT)" in b.get("text", "")]
    assert len(page1_blocks) == 1
    assert "Digital invoice text with details" in page1_blocks[0]["text"]

    # Verify Page 2 scanned image block is present and NOT skipped
    page2_header_blocks = [b for b in content_blocks if b.get("type") == "text" and "PAGE 2 (SCANNED IMAGE)" in b.get("text", "")]
    assert len(page2_header_blocks) == 1

    page2_img_blocks = [b for b in content_blocks if b.get("type") == "image"]
    assert len(page2_img_blocks) == 1
    assert page2_img_blocks[0]["source"]["type"] == "base64"
    assert page2_img_blocks[0]["source"]["media_type"] == "image/jpeg"

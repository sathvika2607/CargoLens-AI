import abc
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from app.models.document import DocumentType


class ExtractionProviderError(Exception):
    """Base exception for all AI provider extraction errors."""
    pass


class ProviderConfigurationError(ExtractionProviderError):
    """Raised when provider configuration or API key is missing or invalid."""
    pass


class ProviderRateLimitError(ExtractionProviderError):
    """Raised when the AI provider throttles or rate limits requests (retryable)."""
    pass


class ProviderTimeoutError(ExtractionProviderError):
    """Raised when an AI provider call times out (retryable)."""
    pass


class ProviderAPIError(ExtractionProviderError):
    """Raised on general API errors from upstream AI providers."""
    pass


class ProviderOutputError(ExtractionProviderError):
    """Raised when the AI provider returns malformed, unparseable, or schema-violating output."""
    pass


@dataclass
class DocumentPageInput:
    """Represents an individual document page with its classified extraction modality."""
    page_number: int  # 1-based page number
    is_digital_text: bool  # True if page contains digital text; False if scanned/image
    text_content: Optional[str] = None
    image_bytes: Optional[bytes] = None
    mime_type: Optional[str] = None


@dataclass
class RawProviderResult:
    """Standard container for output returned by any AI extraction provider."""
    data: Dict[str, Any]
    provider: str
    model: str
    extraction_mode: str  # "TEXT_FIRST", "VISION", or "HYBRID"
    token_usage: Dict[str, int] = field(default_factory=dict)
    latency_seconds: float = 0.0


class BaseExtractionProvider(abc.ABC):
    """
    Provider-neutral interface for structured document extraction.
    Allows swappable backends (Anthropic Claude, local models, etc.).
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g., 'anthropic')."""
        pass

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Model identifier (e.g., 'claude-sonnet-5-5')."""
        pass

    @abc.abstractmethod
    async def extract_structured(
        self,
        document_type: DocumentType,
        text_content: Optional[str] = None,
        page_images: Optional[List[bytes]] = None,
        mime_type: Optional[str] = None,
    ) -> RawProviderResult:
        """
        Executes structured document extraction using available text and/or page images.
        """
        pass

    @abc.abstractmethod
    async def extract_pages_batch(
        self,
        document_type: DocumentType,
        pages: List[DocumentPageInput],
    ) -> RawProviderResult:
        """
        Executes structured document extraction on a bounded batch of individual pages,
        supporting mixed digital-text and scanned page modalities simultaneously.
        """
        pass

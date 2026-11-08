import io
import hashlib
from typing import Tuple
from fastapi import HTTPException, status, UploadFile
from PIL import Image
from pypdf import PdfReader

from app.config import settings
from app.models.document import DocumentType

MAGIC_SIGNATURES = {
    "pdf": [b"%PDF-", b"%PDF"],
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n", b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"],
}

ALLOWED_EXTENSIONS_MAP = {
    ".pdf": "pdf",
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
}

ALLOWED_MIME_MAP = {
    "application/pdf": "pdf",
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/png": "png",
}


def sanitize_filename(filename: str) -> str:
    """
    Strips directory separators and null bytes from user-supplied filename.
    Never used for filesystem paths, only for metadata and safe download naming.
    """
    if not filename:
        return "unnamed_document"
    # Replace path separators
    clean = filename.replace("\\", "/").split("/")[-1]
    clean = "".join(c for c in clean if c.isalnum() or c in ("-", "_", ".", " "))
    return clean.strip() or "unnamed_document"


def validate_document_type(doc_type_raw: str) -> DocumentType:
    try:
        normalized = doc_type_raw.strip().upper()
        return DocumentType(normalized)
    except Exception:
        valid_types = [t.value for t in DocumentType]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document_type '{doc_type_raw}'. Supported types: {', '.join(valid_types)}",
        )


async def process_and_validate_upload_stream(
    upload_file: UploadFile,
) -> Tuple[bytes, str, str, str, int, str]:
    """
    Reads upload stream enforcing size limit, calculates SHA-256,
    validates magic bytes against declared extension and MIME type,
    and checks reasonable limits on PDF page count and image dimensions.

    Returns:
        (file_bytes, clean_filename, extension, detected_mime, file_size, sha256_hash)
    """
    filename = upload_file.filename or ""
    clean_name = sanitize_filename(filename)

    # 1. Validate extension
    ext = "." + clean_name.split(".")[-1].lower() if "." in clean_name else ""
    if ext not in ALLOWED_EXTENSIONS_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed extensions: .pdf, .jpg, .jpeg, .png",
        )
    expected_type = ALLOWED_EXTENSIONS_MAP[ext]

    # 2. Validate declared MIME type
    declared_mime = (upload_file.content_type or "").lower().split(";")[0].strip()
    if declared_mime not in ALLOWED_MIME_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported MIME type '{declared_mime}'. Allowed: application/pdf, image/jpeg, image/png",
        )
    if ALLOWED_MIME_MAP[declared_mime] != expected_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MIME type '{declared_mime}' does not match file extension '{ext}'.",
        )

    # 3. Stream chunks, enforce 25 MB max size, compute SHA-256
    hasher = hashlib.sha256()
    chunks = []
    total_size = 0
    max_size = settings.MAX_UPLOAD_SIZE_BYTES
    chunk_size = 64 * 1024

    while True:
        chunk = await upload_file.read(chunk_size)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum upload limit of 25 MB ({max_size} bytes).",
            )
        hasher.update(chunk)
        chunks.append(chunk)

    if total_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    file_bytes = b"".join(chunks)
    sha256_checksum = hasher.hexdigest()

    # 4. Validate Magic Bytes / File Signatures
    header = file_bytes[:16]
    valid_signatures = MAGIC_SIGNATURES.get(expected_type, [])
    has_valid_signature = any(header.startswith(sig) for sig in valid_signatures)

    if not has_valid_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File content signature does not match declared format '{expected_type}'. Magic bytes verification failed.",
        )

    # 5. Check reasonable structural limits (PDF pages / Image dimensions)
    if expected_type == "pdf":
        try:
            pdf_reader = PdfReader(io.BytesIO(file_bytes))
            num_pages = len(pdf_reader.pages)
            if num_pages > settings.MAX_PDF_PAGES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"PDF exceeds page limit ({num_pages} pages; max allowed is {settings.MAX_PDF_PAGES}).",
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Malformed or corrupted PDF file: {str(e)}",
            )
    elif expected_type in ("jpeg", "png"):
        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                img.verify()  # Verifies image integrity without full decoding
                width, height = img.size
                if width > settings.MAX_IMAGE_DIMENSION or height > settings.MAX_IMAGE_DIMENSION:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Image dimensions ({width}x{height}) exceed maximum allowed dimension of {settings.MAX_IMAGE_DIMENSION}px.",
                    )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Malformed or corrupted image file: {str(e)}",
            )

    canonical_mime = "application/pdf" if expected_type == "pdf" else f"image/{expected_type}"

    return (file_bytes, clean_name, ext, canonical_mime, total_size, sha256_checksum)

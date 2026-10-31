import hashlib
import os
import re

from backend.app.core.config import settings
from backend.app.core.exceptions import ValidationException

# Mapping of standard file extensions to valid MIME types
ALLOWED_EXTENSIONS_MAP = {
    "pdf": ["application/pdf", "application/x-pdf"],
    "png": ["image/png"],
    "jpg": ["image/jpeg", "image/jpg", "image/pjpeg"],
    "jpeg": ["image/jpeg", "image/jpg", "image/pjpeg"],
    "tiff": ["image/tiff", "image/x-tiff"],
    "tif": ["image/tiff", "image/x-tiff"],
}

# Magic byte signatures
MAGIC_NUMBERS = {
    "pdf": [b"%PDF"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "tiff": [b"II*\x00", b"MM\x00*"],
    "tif": [b"II*\x00", b"MM\x00*"],
}


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and null byte injections."""
    if not filename:
        raise ValidationException("File must have a filename.")

    # Check for null bytes
    if "\x00" in filename:
        raise ValidationException("Filename contains invalid null bytes.")

    # Remove path directory separators (both Windows and POSIX)
    cleaned = filename.replace("\\", "/").split("/")[-1].strip()

    # Remove any leading/trailing dots or spaces
    cleaned = re.sub(r"^\.+", "", cleaned)

    # If filename is empty after sanitization
    if not cleaned:
        raise ValidationException("Invalid filename format.")

    return cleaned


def calculate_sha256(file_bytes: bytes) -> str:
    """Calculate SHA256 checksum of raw bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def validate_magic_bytes(file_bytes: bytes, extension: str) -> bool:
    """Verify that file content magic bytes match the specified file extension."""
    if extension not in MAGIC_NUMBERS:
        return False

    signatures = MAGIC_NUMBERS[extension]
    return any(file_bytes.startswith(sig) for sig in signatures)


def validate_file_metadata(
    filename: str,
    file_size: int,
    file_bytes: bytes | None = None,
    content_type: str | None = None,
    allow_any_format: bool = False,
) -> str:
    """Validate filename, file size, extension, MIME type, and magic bytes.

    When allow_any_format=True, extension/MIME/magic-byte checks are skipped
    so a file of ANY format is accepted (used by the flexible upload
    endpoint). Filename sanitization and the size limit are still enforced.
    """
    sanitized = sanitize_filename(filename)

    # Extension check
    _, ext = os.path.splitext(sanitized)
    clean_ext = ext.lstrip(".").lower() or "bin"

    # Size check (always enforced, even in "any format" mode)
    if file_size == 0:
        raise ValidationException("File is empty (0 bytes).")

    if file_size > settings.max_file_size_bytes:
        raise ValidationException(
            f"File size ({file_size / (1024 * 1024):.2f} MB) exceeds maximum allowed size ({settings.MAX_FILE_SIZE_MB} MB)."
        )

    if allow_any_format:
        # Skip extension / MIME / magic-byte restrictions entirely.
        return clean_ext

    if clean_ext not in settings.ALLOWED_EXTENSIONS:
        raise ValidationException(
            f"File extension '.{clean_ext}' is not supported. Allowed extensions: {settings.ALLOWED_EXTENSIONS}"
        )

    # MIME check (if provided and not generic octet-stream)
    if content_type and content_type != "application/octet-stream":
        allowed_mimes = ALLOWED_EXTENSIONS_MAP.get(clean_ext, [])
        if content_type.lower() not in allowed_mimes:
            raise ValidationException(
                f"MIME type '{content_type}' does not match extension '.{clean_ext}'."
            )

    # Magic byte check
    if file_bytes is not None:
        if not validate_magic_bytes(file_bytes, clean_ext):
            raise ValidationException(
                f"File content does not match expected signature for '.{clean_ext}'."
            )

    return clean_ext

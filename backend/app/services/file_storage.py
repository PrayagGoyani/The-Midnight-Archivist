"""Local filesystem storage for uploaded documents."""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from ..config import settings

# Allowed extensions and corresponding content types
ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}


def validate_extension(filename: str) -> tuple[str, str]:
    """Validate file extension and return (extension, content_type).

    Raises ValueError for unsupported extensions.
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS.keys()))
        raise ValueError(
            f"Unsupported file type '{ext}'. Allowed types: {allowed}"
        )
    return ext, ALLOWED_EXTENSIONS[ext]


def sanitize_filename(filename: str) -> str:
    """Remove path components and unsafe characters from a filename."""
    # Strip any directory components
    name = Path(filename).name
    # Remove anything that isn't alphanumeric, dot, hyphen, or underscore
    name = re.sub(r"[^\w.\-]", "_", name)
    # Prevent hidden files
    name = name.lstrip(".")
    return name if name else "unnamed"


def generate_stored_filename(original_filename: str, extension: str) -> str:
    """Generate a unique storage filename to avoid collisions."""
    safe_base = sanitize_filename(Path(original_filename).stem)[:50]
    unique = uuid.uuid4().hex[:12]
    return f"{safe_base}_{unique}{extension}"


def save_upload(content: bytes, stored_filename: str) -> Path:
    """Write uploaded content to the uploads directory.

    Returns the resolved path to the stored file.
    Raises OSError on write failure.
    """
    upload_dir = settings.resolve_upload_dir()
    file_path = upload_dir / stored_filename

    # Prevent path traversal
    resolved = file_path.resolve()
    if not str(resolved).startswith(str(upload_dir.resolve())):
        raise ValueError("Invalid storage path detected")

    try:
        file_path.write_bytes(content)
    except Exception:
        # Clean up partial file
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        raise

    return resolved


def delete_file(stored_filename: str) -> bool:
    """Delete a stored file. Returns True if deleted, False if not found."""
    upload_dir = settings.resolve_upload_dir()
    file_path = upload_dir / stored_filename
    resolved = file_path.resolve()

    # Prevent path traversal
    if not str(resolved).startswith(str(upload_dir.resolve())):
        raise ValueError("Invalid storage path detected")

    if resolved.exists():
        resolved.unlink()
        return True
    return False

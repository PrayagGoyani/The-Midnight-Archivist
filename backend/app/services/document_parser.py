"""Document text extraction for PDF, Markdown and plain text."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExtractedPassage:
    """A contiguous block of extracted text with source metadata."""

    text: str
    page_number: int | None = None
    section: str | None = None


class ExtractionError(Exception):
    """Raised when document extraction fails unrecoverably."""
    pass


# ── PDF ──────────────────────────────────────────────────────────────


def extract_pdf(file_path: Path) -> list[ExtractedPassage]:
    """Extract text from a PDF page-by-page using pypdf.

    Raises ExtractionError for encrypted or unreadable PDFs.
    Returns an empty list if no extractable text is found (scanned PDF).
    """
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError:
        raise ExtractionError("pypdf is required for PDF extraction but is not installed.")

    try:
        reader = PdfReader(str(file_path))
    except PdfReadError as e:
        raise ExtractionError(f"Failed to read PDF: {e}")
    except Exception as e:
        raise ExtractionError(f"Failed to open PDF: {e}")

    if reader.is_encrypted:
        try:
            # Attempt empty-password decryption (some PDFs)
            if not reader.decrypt(""):
                raise ExtractionError(
                    "This PDF is password-protected. Encrypted PDFs are not supported."
                )
        except Exception:
            raise ExtractionError(
                "This PDF is password-protected. Encrypted PDFs are not supported."
            )

    passages: list[ExtractedPassage] = []
    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = text.strip()
        if text:
            passages.append(ExtractedPassage(text=text, page_number=page_idx))

    return passages


def get_pdf_page_count(file_path: Path) -> int:
    """Return total page count of a PDF, or 0 if unreadable."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        return len(reader.pages)
    except Exception:
        return 0


# ── Markdown ─────────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_MD_FORMATTING_RE = re.compile(
    r"(?:"
    r"\*\*(.+?)\*\*"      # bold
    r"|__(.+?)__"          # bold alt
    r"|\*(.+?)\*"          # italic
    r"|_(.+?)_"            # italic alt
    r"|~~(.+?)~~"          # strikethrough
    r"|`(.+?)`"            # inline code
    r"|\[([^\]]+)\]\([^)]+\)"  # links — keep text
    r"|!\[[^\]]*\]\([^)]+\)"   # images — remove entirely
    r")"
)


def _clean_md_formatting(text: str) -> str:
    """Strip Markdown formatting, preserving meaningful text."""
    # Remove images first
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    # Replace links with their text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove bold/italic/strikethrough/code markers
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def extract_markdown(file_path: Path) -> list[ExtractedPassage]:
    """Extract text from a Markdown file, splitting by headings."""
    raw = file_path.read_text(encoding="utf-8-sig")  # handles BOM
    if not raw.strip():
        return []

    passages: list[ExtractedPassage] = []
    current_section: str | None = None
    current_lines: list[str] = []

    def _flush() -> None:
        block = "\n".join(current_lines).strip()
        cleaned = _clean_md_formatting(block)
        if cleaned:
            passages.append(ExtractedPassage(text=cleaned, section=current_section))

    for line in raw.splitlines():
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            _flush()
            current_lines = []
            current_section = heading_match.group(2).strip()
        else:
            current_lines.append(line)

    _flush()
    return passages


# ── Plain text ───────────────────────────────────────────────────────


def extract_text(file_path: Path) -> list[ExtractedPassage]:
    """Extract text from a plain text file, splitting by paragraphs."""
    raw = file_path.read_text(encoding="utf-8-sig")  # handles BOM
    if not raw.strip():
        return []

    # Split on blank lines to preserve paragraph boundaries
    paragraphs = re.split(r"\n\s*\n", raw)
    passages: list[ExtractedPassage] = []
    for para in paragraphs:
        cleaned = para.strip()
        if cleaned:
            passages.append(ExtractedPassage(text=cleaned))

    return passages


# ── Dispatcher ───────────────────────────────────────────────────────

_EXTRACTORS = {
    ".pdf": extract_pdf,
    ".md": extract_markdown,
    ".markdown": extract_markdown,
    ".txt": extract_text,
}


def extract_document(file_path: Path) -> list[ExtractedPassage]:
    """Extract text passages from a supported document.

    Dispatches to the correct extractor based on file extension.
    Raises ExtractionError if the format is unsupported or extraction fails.
    """
    ext = file_path.suffix.lower()
    extractor = _EXTRACTORS.get(ext)
    if extractor is None:
        raise ExtractionError(f"Unsupported file format: {ext}")

    if not file_path.exists():
        raise ExtractionError(f"File not found: {file_path}")

    return extractor(file_path)

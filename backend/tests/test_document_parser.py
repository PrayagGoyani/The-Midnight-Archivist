"""Tests for document text extraction (PDF, Markdown, Plain text)."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.services.document_parser import (
    ExtractedPassage,
    ExtractionError,
    extract_document,
    extract_markdown,
    extract_pdf,
    extract_text,
    get_pdf_page_count,
)


def _create_sample_pdf(pages_text: list[str], password: str | None = None) -> bytes:
    """Helper to create an in-memory PDF with valid extractable text per page."""
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    for text in pages_text:
        page = writer.add_blank_page(width=400, height=600)

        # Standard Type1 Helvetica font
        font_dict = DictionaryObject()
        font_dict[NameObject("/Type")] = NameObject("/Font")
        font_dict[NameObject("/Subtype")] = NameObject("/Type1")
        font_dict[NameObject("/BaseFont")] = NameObject("/Helvetica")

        fonts = DictionaryObject()
        fonts[NameObject("/F1")] = font_dict

        resources = DictionaryObject()
        resources[NameObject("/Font")] = fonts
        page[NameObject("/Resources")] = resources

        # Escape special PDF string characters
        escaped = (
            text.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        stream_content = f"BT /F1 12 Tf 50 500 Td ({escaped}) Tj ET"
        stream = DecodedStreamObject()
        stream.set_data(stream_content.encode("latin-1"))
        page[NameObject("/Contents")] = stream

    if password:
        writer.encrypt(password)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ── Plain text ────────────────────────────────────────────────────────


def test_extract_plain_text(tmp_path: Path):
    txt_file = tmp_path / "sample.txt"
    txt_file.write_text(
        "First paragraph about ancient libraries.\n\nSecond paragraph describing old manuscripts.",
        encoding="utf-8",
    )

    passages = extract_text(txt_file)
    assert len(passages) == 2
    assert "ancient libraries" in passages[0].text
    assert "old manuscripts" in passages[1].text
    assert passages[0].page_number is None
    assert passages[0].section is None


def test_extract_plain_text_utf8_bom(tmp_path: Path):
    txt_file = tmp_path / "bom.txt"
    txt_file.write_bytes(b"\xef\xbb\xbfText with UTF-8 BOM indicator.")

    passages = extract_text(txt_file)
    assert len(passages) == 1
    assert passages[0].text == "Text with UTF-8 BOM indicator."


def test_extract_plain_text_empty(tmp_path: Path):
    txt_file = tmp_path / "empty.txt"
    txt_file.write_text("   \n\n  \t  ", encoding="utf-8")

    passages = extract_text(txt_file)
    assert passages == []


# ── Markdown ──────────────────────────────────────────────────────────


def test_extract_markdown_sections(tmp_path: Path):
    md_file = tmp_path / "notes.md"
    content = (
        "# Introduction to Archive\n\n"
        "This is the opening lore.\n\n"
        "## The Silent Bell\n\n"
        "It tolled at midnight with **profound** resonance.\n\n"
        "### Forgotten Depths\n\n"
        "Water gathered below the stone floor."
    )
    md_file.write_text(content, encoding="utf-8")

    passages = extract_markdown(md_file)
    assert len(passages) == 3

    assert passages[0].section == "Introduction to Archive"
    assert "opening lore" in passages[0].text

    assert passages[1].section == "The Silent Bell"
    assert "profound resonance" in passages[1].text
    assert "**" not in passages[1].text  # markdown bold stripped

    assert passages[2].section == "Forgotten Depths"
    assert "stone floor" in passages[2].text


def test_extract_markdown_strips_formatting(tmp_path: Path):
    md_file = tmp_path / "formats.md"
    content = (
        "Here is *italic* and `code` and [link text](http://example.com) "
        "and ![image alt](http://example.com/pic.png) and ~~strikethrough~~."
    )
    md_file.write_text(content, encoding="utf-8")

    passages = extract_markdown(md_file)
    assert len(passages) == 1
    text = passages[0].text
    assert "italic" in text
    assert "code" in text
    assert "link text" in text
    assert "strikethrough" in text
    assert "http://example.com" not in text
    assert "*" not in text
    assert "`" not in text
    assert "~~" not in text


def test_extract_markdown_empty(tmp_path: Path):
    md_file = tmp_path / "empty.md"
    md_file.write_text("   \n\n", encoding="utf-8")
    assert extract_markdown(md_file) == []


# ── PDF ───────────────────────────────────────────────────────────────


def test_extract_pdf_pages(tmp_path: Path):
    pdf_bytes = _create_sample_pdf([
        "Page one: The nocturnal records of St. Jude.",
        "Page two: Catalog of brass astrolabes and star maps.",
    ])
    pdf_file = tmp_path / "catalog.pdf"
    pdf_file.write_bytes(pdf_bytes)

    passages = extract_pdf(pdf_file)
    assert len(passages) == 2
    assert passages[0].page_number == 1
    assert "nocturnal records" in passages[0].text
    assert passages[1].page_number == 2
    assert "astrolabes" in passages[1].text


def test_get_pdf_page_count(tmp_path: Path):
    pdf_bytes = _create_sample_pdf(["First", "Second", "Third"])
    pdf_file = tmp_path / "three_pages.pdf"
    pdf_file.write_bytes(pdf_bytes)

    assert get_pdf_page_count(pdf_file) == 3


def test_extract_pdf_encrypted(tmp_path: Path):
    pdf_bytes = _create_sample_pdf(["Secret text"], password="secretpassword")
    pdf_file = tmp_path / "encrypted.pdf"
    pdf_file.write_bytes(pdf_bytes)

    with pytest.raises(ExtractionError, match="password-protected"):
        extract_pdf(pdf_file)


def test_extract_pdf_corrupted(tmp_path: Path):
    pdf_file = tmp_path / "corrupt.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 not a real valid pdf stream...")

    with pytest.raises(ExtractionError):
        extract_pdf(pdf_file)


def test_extract_pdf_blank_pages(tmp_path: Path):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    pdf_file = tmp_path / "blank.pdf"
    with open(pdf_file, "wb") as f:
        writer.write(f)

    passages = extract_pdf(pdf_file)
    assert passages == []


# ── Dispatcher ────────────────────────────────────────────────────────


def test_extract_document_unsupported_format(tmp_path: Path):
    doc_file = tmp_path / "archive.docx"
    doc_file.write_text("not supported")

    with pytest.raises(ExtractionError, match="Unsupported file format"):
        extract_document(doc_file)


def test_extract_document_file_not_found(tmp_path: Path):
    missing_file = tmp_path / "does_not_exist.txt"
    with pytest.raises(ExtractionError, match="File not found"):
        extract_document(missing_file)

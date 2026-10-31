"""Paragraph-aware text chunking with metadata preservation."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .document_parser import ExtractedPassage


@dataclass
class TextChunk:
    """A chunk of text ready for embedding, with source metadata."""

    text: str
    chunk_index: int
    page_number: int | None = None
    section: str | None = None


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences at common sentence boundaries."""
    # Split on sentence-ending punctuation followed by whitespace
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p for p in parts if p.strip()]


def chunk_passages(
    passages: list[ExtractedPassage],
    chunk_size: int = 1200,
    chunk_overlap: int = 180,
) -> list[TextChunk]:
    """Split extracted passages into overlapping chunks.

    Respects paragraph and sentence boundaries where possible.
    Preserves page_number and section metadata from source passages.

    Args:
        passages: Extracted text passages with metadata.
        chunk_size: Target maximum character count per chunk.
        chunk_overlap: Approximate overlap in characters between consecutive chunks.

    Returns:
        Ordered list of TextChunk with stable chunk_index values.
    """
    if not passages:
        return []

    if chunk_size < 50:
        chunk_size = 50
    if chunk_overlap < 0:
        chunk_overlap = 0
    if chunk_overlap >= chunk_size:
        chunk_overlap = chunk_size // 4

    chunks: list[TextChunk] = []
    chunk_index = 0

    for passage in passages:
        text = passage.text.strip()
        if not text:
            continue

        # If the passage fits in one chunk, emit it directly
        if len(text) <= chunk_size:
            chunks.append(
                TextChunk(
                    text=text,
                    chunk_index=chunk_index,
                    page_number=passage.page_number,
                    section=passage.section,
                )
            )
            chunk_index += 1
            continue

        # Split passage into sentences for smarter chunking
        sentences = _split_into_sentences(text)
        if not sentences:
            continue

        current_parts: list[str] = []
        current_len = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            # If a single sentence exceeds chunk_size, split by characters
            if sentence_len > chunk_size:
                # Flush current buffer first
                if current_parts:
                    chunk_text = " ".join(current_parts).strip()
                    if chunk_text:
                        chunks.append(
                            TextChunk(
                                text=chunk_text,
                                chunk_index=chunk_index,
                                page_number=passage.page_number,
                                section=passage.section,
                            )
                        )
                        chunk_index += 1
                    current_parts = []
                    current_len = 0

                # Hard-split the long sentence
                for i in range(0, sentence_len, chunk_size - chunk_overlap):
                    segment = sentence[i : i + chunk_size].strip()
                    if segment:
                        chunks.append(
                            TextChunk(
                                text=segment,
                                chunk_index=chunk_index,
                                page_number=passage.page_number,
                                section=passage.section,
                            )
                        )
                        chunk_index += 1
                continue

            # Would adding this sentence exceed the limit?
            join_len = current_len + (1 if current_parts else 0) + sentence_len
            if join_len > chunk_size and current_parts:
                # Emit current chunk
                chunk_text = " ".join(current_parts).strip()
                if chunk_text:
                    chunks.append(
                        TextChunk(
                            text=chunk_text,
                            chunk_index=chunk_index,
                            page_number=passage.page_number,
                            section=passage.section,
                        )
                    )
                    chunk_index += 1

                # Carry overlap: take trailing sentences that fit within overlap
                overlap_parts: list[str] = []
                overlap_len = 0
                for prev in reversed(current_parts):
                    if overlap_len + len(prev) + 1 > chunk_overlap:
                        break
                    overlap_parts.insert(0, prev)
                    overlap_len += len(prev) + 1

                current_parts = overlap_parts
                current_len = sum(len(p) for p in current_parts) + max(0, len(current_parts) - 1)

            current_parts.append(sentence)
            current_len += (1 if len(current_parts) > 1 else 0) + sentence_len

        # Flush remaining
        if current_parts:
            chunk_text = " ".join(current_parts).strip()
            if chunk_text:
                chunks.append(
                    TextChunk(
                        text=chunk_text,
                        chunk_index=chunk_index,
                        page_number=passage.page_number,
                        section=passage.section,
                    )
                )
                chunk_index += 1

    return chunks

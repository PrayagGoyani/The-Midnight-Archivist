"""Document indexing pipeline: extraction, chunking, embedding, and persistence."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Chunk, Document
from .chunker import chunk_passages
from .document_parser import (
    ExtractionError,
    extract_document,
    get_pdf_page_count,
)
from .ollama_client import (
    OllamaConnectionError,
    OllamaEmbeddingError,
    OllamaModelError,
    embed_texts,
)


class DocumentNotFoundError(Exception):
    """Raised when the specified document does not exist."""
    pass


class DocumentFileNotFoundError(Exception):
    """Raised when the document's physical file is missing from disk."""
    pass


@dataclass
class ProcessingResult:
    """Summary of successful document processing."""

    document_id: str
    title: str
    status: str
    chunk_count: int
    embedding_model: str
    dimensions: int
    indexed_at: datetime


def process_document(document_id: str, db: Session) -> ProcessingResult:
    """Run the complete ingestion pipeline for a document.

    Lifecycle semantics:
    A. First-time indexing (doc.status in ('uploaded', 'failed')):
       - Transitions: uploaded -> processing -> ready (or failed on error).
       - If failed, status='failed', error_message recorded.
    B. Re-indexing an already-ready document (doc.status == 'ready'):
       - doc.status remains 'ready' during processing to preserve searchability.
       - Existing chunks remain active and searchable during extraction/embedding.
       - If re-indexing fails, old chunks and indexing metadata remain intact and searchable;
         the error is recorded in doc.reindex_error.
       - If re-indexing succeeds, previous chunks are atomically replaced with the new index.

    Raises:
        DocumentNotFoundError: Document record not found.
        DocumentFileNotFoundError: Physical file missing from disk.
        ExtractionError: Text extraction failed or yielded no text.
        OllamaConnectionError: Ollama server unreachable.
        OllamaModelError: Embedding model not pulled.
        OllamaEmbeddingError: Embedding generation failed.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise DocumentNotFoundError(f"Document '{document_id}' not found.")

    file_path = settings.resolve_upload_dir() / doc.stored_filename
    if not file_path.exists():
        err = f"Stored file '{doc.stored_filename}' not found on disk."
        if doc.status == "ready":
            doc.reindex_error = err
        else:
            doc.status = "failed"
            doc.error_message = err
        db.commit()
        raise DocumentFileNotFoundError(err)

    is_reindex = (doc.status == "ready")

    if not is_reindex:
        doc.status = "processing"
        doc.error_message = None
        doc.reindex_error = None
        db.commit()
    else:
        # Re-indexing: keep status='ready', clear any previous reindex_error
        doc.reindex_error = None
        db.commit()

    def _record_failure(err_msg: str) -> None:
        """Helper to record failure while respecting re-indexing semantics."""
        if is_reindex:
            # Keep doc.status == 'ready', keep old chunks, keep previous metadata
            doc.reindex_error = err_msg
        else:
            doc.status = "failed"
            doc.error_message = err_msg
        db.commit()

    # Step 1: Extraction
    try:
        if doc.file_extension.lower() == ".pdf":
            page_count = get_pdf_page_count(file_path)
            if page_count > 0:
                doc.page_count = page_count

        passages = extract_document(file_path)
    except ExtractionError as e:
        _record_failure(str(e))
        raise
    except Exception as e:
        err = f"Unexpected extraction error: {e}"
        _record_failure(err)
        raise ExtractionError(err) from e

    if not passages:
        err = (
            "No extractable text found in document. "
            "The file may be empty or contains scanned images without OCR text."
        )
        _record_failure(err)
        raise ExtractionError(err)

    # Step 2: Chunking
    chunks = chunk_passages(
        passages,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    if not chunks:
        err = "Document produced no usable text chunks."
        _record_failure(err)
        raise ExtractionError(err)

    # Step 3: Embeddings via Ollama
    chunk_texts = [c.text for c in chunks]
    try:
        embedding_result = embed_texts(
            chunk_texts,
            model=settings.embedding_model,
            base_url=settings.ollama_base_url,
            batch_size=settings.embedding_batch_size,
            timeout=settings.ollama_timeout,
        )
    except (OllamaConnectionError, OllamaModelError, OllamaEmbeddingError) as e:
        _record_failure(str(e))
        raise
    except Exception as e:
        err = f"Unexpected embedding error: {e}"
        _record_failure(err)
        raise OllamaEmbeddingError(err) from e

    # Step 4: Atomic database persistence
    now = datetime.now(timezone.utc)
    try:
        # Atomic replacement: old chunks are deleted and new chunks added in the same transaction
        db.query(Chunk).filter(Chunk.document_id == doc.id).delete()

        for c, emb in zip(chunks, embedding_result.embeddings):
            chunk_record = Chunk(
                document_id=doc.id,
                chunk_index=c.chunk_index,
                text=c.text,
                page_number=c.page_number,
                section=c.section,
                embedding=json.dumps(emb),
                embedding_model=settings.embedding_model,
            )
            db.add(chunk_record)

        doc.status = "ready"
        doc.error_message = None
        doc.reindex_error = None
        doc.indexed_at = now
        doc.embedding_model_used = settings.embedding_model
        doc.chunk_count = len(chunks)

        db.commit()
        db.refresh(doc)
    except Exception as e:
        db.rollback()
        err = f"Failed to persist indexed chunks: {e}"
        _record_failure(err)
        raise

    return ProcessingResult(
        document_id=doc.id,
        title=doc.title,
        status=doc.status,
        chunk_count=len(chunks),
        embedding_model=settings.embedding_model,
        dimensions=embedding_result.dimensions,
        indexed_at=now,
    )

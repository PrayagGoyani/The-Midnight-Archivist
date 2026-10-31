"""Tests for document indexing pipeline."""
from __future__ import annotations

import httpx
import pytest
from pathlib import Path
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Document
from app.services.document_parser import ExtractionError
from app.services.indexing import (
    DocumentFileNotFoundError,
    DocumentNotFoundError,
    process_document,
)
from app.services.ollama_client import OllamaConnectionError
from app.services.retrieval import search_chunks


def _setup_mock_ollama(monkeypatch):
    """Mock Ollama embed_texts to return static vectors."""
    def mock_post(self, url, json=None, **kwargs):
        count = len(json["input"])
        return httpx.Response(
            status_code=200,
            json={"embeddings": [[0.1, 0.2, 0.3, 0.4]] * count},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", mock_post)


def test_process_missing_document(db_session: Session):
    with pytest.raises(DocumentNotFoundError):
        process_document("nonexistent_id", db_session)


def test_process_missing_file_on_disk(db_session: Session, tmp_data_dir: Path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_data_dir))
    monkeypatch.setattr("app.config.Settings.resolve_upload_dir", lambda self: tmp_data_dir / "uploads")

    doc = Document(
        id="missing_file_doc",
        title="Ghost File",
        original_filename="ghost.txt",
        stored_filename="ghost_stored.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=10,
        status="uploaded",
    )
    db_session.add(doc)
    db_session.commit()

    with pytest.raises(DocumentFileNotFoundError):
        process_document(doc.id, db_session)

    db_session.refresh(doc)
    assert doc.status == "failed"
    assert "not found on disk" in doc.error_message


def test_process_empty_document(db_session: Session, tmp_data_dir: Path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_data_dir))
    monkeypatch.setattr("app.config.Settings.resolve_upload_dir", lambda self: tmp_data_dir / "uploads")

    file_path = tmp_data_dir / "uploads" / "empty_doc.txt"
    file_path.write_text("   \n\n\t  ", encoding="utf-8")

    doc = Document(
        id="empty_doc",
        title="Empty Lore",
        original_filename="empty.txt",
        stored_filename="empty_doc.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=file_path.stat().st_size,
        status="uploaded",
    )
    db_session.add(doc)
    db_session.commit()

    with pytest.raises(ExtractionError, match="No extractable text"):
        process_document(doc.id, db_session)

    db_session.refresh(doc)
    assert doc.status == "failed"
    assert "No extractable text" in doc.error_message


def test_process_document_success(db_session: Session, tmp_data_dir: Path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_data_dir))
    monkeypatch.setattr("app.config.Settings.resolve_upload_dir", lambda self: tmp_data_dir / "uploads")
    _setup_mock_ollama(monkeypatch)

    file_path = tmp_data_dir / "uploads" / "archivist_notes.md"
    file_path.write_text(
        "# Volume I: The Iron Scriptorium\n\n"
        "The ink used here was brewed from burnt bone and elderberry juice.\n\n"
        "## Section II: The Vaults\n\n"
        "Below the second archway lies the index of lost cartographies.",
        encoding="utf-8",
    )

    doc = Document(
        id="notes_doc",
        title="Volume I",
        original_filename="notes.md",
        stored_filename="archivist_notes.md",
        file_extension=".md",
        content_type="text/markdown",
        file_size=file_path.stat().st_size,
        status="uploaded",
    )
    db_session.add(doc)
    db_session.commit()

    result = process_document(doc.id, db_session)

    assert result.status == "ready"
    assert result.chunk_count >= 2
    assert result.embedding_model == settings.embedding_model
    assert result.dimensions == 4

    db_session.refresh(doc)
    assert doc.status == "ready"
    assert doc.error_message is None
    assert doc.reindex_error is None
    assert doc.indexed_at is not None
    assert doc.chunk_count == result.chunk_count

    # Verify chunks stored in database
    chunks = db_session.query(Chunk).filter(Chunk.document_id == doc.id).order_by(Chunk.chunk_index).all()
    assert len(chunks) == result.chunk_count
    for c in chunks:
        assert c.embedding is not None
        assert c.embedding_model == settings.embedding_model


def test_reindexing_atomic_replacement(db_session: Session, tmp_data_dir: Path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_data_dir))
    monkeypatch.setattr("app.config.Settings.resolve_upload_dir", lambda self: tmp_data_dir / "uploads")
    _setup_mock_ollama(monkeypatch)

    file_path = tmp_data_dir / "uploads" / "reindex.txt"
    file_path.write_text("First edition paragraph text.", encoding="utf-8")

    doc = Document(
        id="reindex_doc",
        title="Reindex Test",
        original_filename="reindex.txt",
        stored_filename="reindex.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=file_path.stat().st_size,
        status="uploaded",
    )
    db_session.add(doc)
    db_session.commit()

    # Initial indexing
    result1 = process_document(doc.id, db_session)
    assert result1.chunk_count == 1

    # Modify file with longer content
    file_path.write_text(
        "Second edition text with first paragraph.\n\n"
        "And a second distinct paragraph for the archive.",
        encoding="utf-8",
    )

    # Re-index
    result2 = process_document(doc.id, db_session)
    assert result2.chunk_count == 2

    # Chunks in DB should NOT have accumulated (1 + 2 = 3); must be exactly 2
    chunks = db_session.query(Chunk).filter(Chunk.document_id == doc.id).all()
    assert len(chunks) == 2


def test_process_document_ollama_failure_first_time(db_session: Session, tmp_data_dir: Path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_data_dir))
    monkeypatch.setattr("app.config.Settings.resolve_upload_dir", lambda self: tmp_data_dir / "uploads")

    def mock_fail(self, url, **kwargs):
        raise httpx.ConnectError("Ollama offline")

    monkeypatch.setattr(httpx.Client, "post", mock_fail)

    file_path = tmp_data_dir / "uploads" / "fail_ollama.txt"
    file_path.write_text("Valid text that fails at Ollama step.", encoding="utf-8")

    doc = Document(
        id="fail_ollama_doc",
        title="Ollama Fail",
        original_filename="fail_ollama.txt",
        stored_filename="fail_ollama.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=file_path.stat().st_size,
        status="uploaded",
    )
    db_session.add(doc)
    db_session.commit()

    with pytest.raises(OllamaConnectionError):
        process_document(doc.id, db_session)

    db_session.refresh(doc)
    assert doc.status == "failed"
    assert "Cannot connect to Ollama" in doc.error_message


def test_reindexing_failure_preserves_old_index_and_searchability(
    db_session: Session, tmp_data_dir: Path, monkeypatch
):
    """If re-indexing a ready document fails, old chunks remain active and searchable."""
    monkeypatch.setattr(settings, "data_dir", str(tmp_data_dir))
    monkeypatch.setattr("app.config.Settings.resolve_upload_dir", lambda self: tmp_data_dir / "uploads")
    _setup_mock_ollama(monkeypatch)

    file_path = tmp_data_dir / "uploads" / "preserve_test.txt"
    file_path.write_text("Original valuable lore.", encoding="utf-8")

    doc = Document(
        id="preserve_doc",
        title="Preserve Lore",
        original_filename="preserve_test.txt",
        stored_filename="preserve_test.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=file_path.stat().st_size,
        status="uploaded",
    )
    db_session.add(doc)
    db_session.commit()

    # 1. Initial indexing succeeds
    res1 = process_document(doc.id, db_session)
    assert res1.status == "ready"
    original_indexed_at = doc.indexed_at
    assert doc.chunk_count == 1

    # Verify search finds it
    search_hits = search_chunks([0.1, 0.2, 0.3, 0.4], db_session, query_model=settings.embedding_model)
    assert len(search_hits) == 1
    assert search_hits[0].document_id == doc.id

    # 2. Re-indexing fails due to Ollama outage
    def mock_fail(self, url, **kwargs):
        raise httpx.ConnectError("Ollama disconnected")

    monkeypatch.setattr(httpx.Client, "post", mock_fail)

    with pytest.raises(OllamaConnectionError):
        process_document(doc.id, db_session)

    db_session.refresh(doc)
    # Status remains ready!
    assert doc.status == "ready"
    assert doc.reindex_error is not None
    assert "Cannot connect to Ollama" in doc.reindex_error
    # Metadata preserved
    assert doc.indexed_at == original_indexed_at
    assert doc.chunk_count == 1

    # Chunks are still present in database
    chunks = db_session.query(Chunk).filter(Chunk.document_id == doc.id).all()
    assert len(chunks) == 1

    # Chunks remain searchable!
    search_hits_after_fail = search_chunks(
        [0.1, 0.2, 0.3, 0.4], db_session, query_model=settings.embedding_model
    )
    assert len(search_hits_after_fail) == 1
    assert search_hits_after_fail[0].document_id == doc.id


def test_reindexing_retry_succeeds_and_replaces_index(
    db_session: Session, tmp_data_dir: Path, monkeypatch
):
    """Retrying re-indexing after a failure replaces the old index cleanly."""
    monkeypatch.setattr(settings, "data_dir", str(tmp_data_dir))
    monkeypatch.setattr("app.config.Settings.resolve_upload_dir", lambda self: tmp_data_dir / "uploads")
    _setup_mock_ollama(monkeypatch)

    file_path = tmp_data_dir / "uploads" / "retry_doc.txt"
    file_path.write_text("Version 1 content.", encoding="utf-8")

    doc = Document(
        id="retry_doc",
        title="Retry Doc",
        original_filename="retry_doc.txt",
        stored_filename="retry_doc.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=file_path.stat().st_size,
        status="uploaded",
    )
    db_session.add(doc)
    db_session.commit()

    # Step 1: Initial index
    process_document(doc.id, db_session)
    assert doc.chunk_count == 1

    # Step 2: Failed re-index
    def mock_fail(self, url, **kwargs):
        raise httpx.ConnectError("Temporary outage")

    monkeypatch.setattr(httpx.Client, "post", mock_fail)
    file_path.write_text("Version 2 new paragraph 1.\n\nVersion 2 new paragraph 2.", encoding="utf-8")

    with pytest.raises(OllamaConnectionError):
        process_document(doc.id, db_session)

    db_session.refresh(doc)
    assert doc.status == "ready"
    assert doc.chunk_count == 1
    assert doc.reindex_error is not None

    # Step 3: Service restored, retry re-indexing
    _setup_mock_ollama(monkeypatch)
    res_retry = process_document(doc.id, db_session)

    db_session.refresh(doc)
    assert res_retry.status == "ready"
    assert doc.status == "ready"
    assert doc.reindex_error is None
    assert doc.chunk_count == 2

    # Exactly 2 chunks in DB, no duplicates
    chunks = db_session.query(Chunk).filter(Chunk.document_id == doc.id).all()
    assert len(chunks) == 2

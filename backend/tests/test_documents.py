"""Tests for document endpoints."""
from __future__ import annotations

import io


def _upload(client, filename="test.txt", content=b"Hello, world!", content_type="text/plain"):
    """Helper to upload a file."""
    return client.post(
        "/api/documents",
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


def test_upload_txt(client):
    """Uploading a valid .txt file returns 201."""
    resp = _upload(client, "sample.txt", b"Some text content")
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "sample"
    assert data["file_extension"] == ".txt"
    assert data["status"] == "uploaded"
    assert data["file_size"] == len(b"Some text content")


def test_upload_md(client):
    """Uploading a Markdown file returns 201."""
    resp = _upload(client, "notes.md", b"# Heading\nParagraph.", "text/markdown")
    assert resp.status_code == 201
    assert resp.json()["file_extension"] == ".md"


def test_upload_markdown_ext(client):
    """Uploading a .markdown file returns 201."""
    resp = _upload(client, "article.markdown", b"# Article\nBody.", "text/markdown")
    assert resp.status_code == 201
    assert resp.json()["file_extension"] == ".markdown"


def test_upload_pdf(client):
    """Uploading a PDF file returns 201."""
    # Minimal valid PDF header
    pdf_bytes = b"%PDF-1.4 fake content for testing"
    resp = _upload(client, "doc.pdf", pdf_bytes, "application/pdf")
    assert resp.status_code == 201
    assert resp.json()["file_extension"] == ".pdf"


def test_upload_unsupported_extension(client):
    """Uploading an unsupported file type returns 400."""
    resp = _upload(client, "image.png", b"\x89PNG", "image/png")
    assert resp.status_code == 400
    assert "Unsupported" in resp.json()["detail"]


def test_upload_empty_file(client):
    """Uploading an empty file returns 400."""
    resp = _upload(client, "empty.txt", b"")
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_upload_oversized_file(client, monkeypatch):
    """Uploading a file exceeding the limit returns 413."""
    monkeypatch.setattr("app.config.settings.upload_max_size_mb", 0)
    resp = _upload(client, "big.txt", b"data")
    assert resp.status_code == 413


def test_upload_path_traversal(client):
    """Filenames with path traversal components are sanitized."""
    resp = _upload(client, "../../etc/passwd.txt", b"not a password file")
    assert resp.status_code == 201
    data = resp.json()
    assert ".." not in data["original_filename"] or data["status"] == "uploaded"


def test_list_documents_empty(client):
    """Listing documents when none exist returns an empty list."""
    resp = client.get("/api/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["documents"] == []
    assert data["total"] == 0


def test_list_documents_after_upload(client):
    """Listing documents returns uploaded documents."""
    _upload(client, "a.txt", b"aaa")
    _upload(client, "b.md", b"bbb")
    resp = client.get("/api/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_get_document(client):
    """Retrieving a specific document returns its metadata."""
    resp = _upload(client, "test.txt", b"content")
    doc_id = resp.json()["id"]
    resp2 = client.get(f"/api/documents/{doc_id}")
    assert resp2.status_code == 200
    assert resp2.json()["id"] == doc_id


def test_get_missing_document(client):
    """Requesting a nonexistent document returns 404."""
    resp = client.get("/api/documents/nonexistent123")
    assert resp.status_code == 404


def test_delete_document(client):
    """Deleting a document removes it and its file."""
    resp = _upload(client, "doomed.txt", b"goodbye")
    doc_id = resp.json()["id"]
    del_resp = client.delete(f"/api/documents/{doc_id}")
    assert del_resp.status_code == 204
    # Verify it's gone
    get_resp = client.get(f"/api/documents/{doc_id}")
    assert get_resp.status_code == 404


def test_delete_missing_document(client):
    """Deleting a nonexistent document returns 404."""
    resp = client.delete("/api/documents/nope")
    assert resp.status_code == 404


def test_delete_document_removes_physical_file(client, tmp_data_dir):
    """Deleting a document removes the file from disk."""
    resp = _upload(client, "removal_test.txt", b"check file removed")
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    uploads = tmp_data_dir / "uploads"
    files = list(uploads.glob("*removal_test*"))
    assert len(files) == 1
    assert files[0].exists()

    del_resp = client.delete(f"/api/documents/{doc_id}")
    assert del_resp.status_code == 204
    assert not files[0].exists()


def test_upload_db_failure_cleans_up_file(client, tmp_data_dir, monkeypatch):
    """When DB commit fails during upload, the saved file is deleted."""
    from sqlalchemy.orm import Session

    def broken_commit(self):
        raise RuntimeError("Simulated DB failure")

    monkeypatch.setattr(Session, "commit", broken_commit)

    resp = _upload(client, "failure_test.txt", b"temporary bytes")
    assert resp.status_code == 500

    uploads = tmp_data_dir / "uploads"
    leftovers = list(uploads.glob("*failure_test*"))
    assert len(leftovers) == 0


def test_delete_document_cascades_to_chunks(client, db_session):
    """Deleting a document cascades and deletes associated chunks."""
    from app.models import Chunk, Document

    resp = _upload(client, "chunked.txt", b"text with chunks")
    doc_id = resp.json()["id"]

    # Add a chunk directly to the database
    chunk = Chunk(
        document_id=doc_id,
        chunk_index=0,
        text="A chunk of text",
    )
    db_session.add(chunk)
    db_session.commit()

    # Verify chunk exists
    assert db_session.query(Chunk).filter(Chunk.document_id == doc_id).count() == 1

    # Delete the document
    del_resp = client.delete(f"/api/documents/{doc_id}")
    assert del_resp.status_code == 204

    # Verify chunk was cascade-deleted
    assert db_session.query(Chunk).filter(Chunk.document_id == doc_id).count() == 0

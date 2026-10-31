"""Integration tests for document processing, chunk retrieval, and semantic search endpoints."""
from __future__ import annotations

import httpx
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document


def _setup_mock_ollama(monkeypatch):
    """Mock Ollama embed_texts to return static 4D vectors for Ollama embed requests."""
    orig_post = httpx.Client.post

    def mock_post(self, url, *args, **kwargs):
        if "api/embed" in str(url):
            req_json = kwargs.get("json", {})
            count = len(req_json.get("input", []))
            return httpx.Response(
                status_code=200,
                json={"embeddings": [[0.5, 0.5, 0.0, 0.0]] * count},
                request=httpx.Request("POST", str(url)),
            )
        return orig_post(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "post", mock_post)


# ── Process Document Endpoint ─────────────────────────────────────────


def test_api_process_missing_document(client: TestClient):
    resp = client.post("/api/documents/nonexistent/process")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_api_process_empty_document(client: TestClient, tmp_data_dir: Path):
    upload_resp = client.post(
        "/api/documents",
        files={"file": ("blank.txt", b"   \n\t  ", "text/plain")},
    )
    # The upload itself checks empty length; let's upload spaces which passes upload
    # Wait, upload checks len(content) == 0. Spaces len is > 0.
    doc_id = upload_resp.json()["id"]

    resp = client.post(f"/api/documents/{doc_id}/process")
    assert resp.status_code == 422
    assert "extractable text" in resp.json()["detail"].lower()


def test_api_process_document_success(client: TestClient, monkeypatch):
    _setup_mock_ollama(monkeypatch)

    upload_resp = client.post(
        "/api/documents",
        files={
            "file": (
                "archive_lore.md",
                b"# Prologue\n\nNight fell upon the sunken library.\n\n# Chapter 1\n\nThe tide rose steadily.",
                "text/markdown",
            )
        },
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]

    # Process the document
    process_resp = client.post(f"/api/documents/{doc_id}/process")
    assert process_resp.status_code == 200
    data = process_resp.json()
    assert data["document_id"] == doc_id
    assert data["status"] == "ready"
    assert data["chunk_count"] >= 2
    assert data["embedding_model"] == settings.embedding_model
    assert data["dimensions"] == 4


def test_api_process_ollama_unavailable(client: TestClient, monkeypatch):
    orig_post = httpx.Client.post

    def mock_fail(self, url, *args, **kwargs):
        if "api/embed" in str(url):
            raise httpx.ConnectError("Connection refused")
        return orig_post(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "post", mock_fail)

    upload_resp = client.post(
        "/api/documents",
        files={"file": ("valid.txt", b"Valid text content for processing.", "text/plain")},
    )
    doc_id = upload_resp.json()["id"]

    resp = client.post(f"/api/documents/{doc_id}/process")
    assert resp.status_code == 503
    assert "Cannot connect to Ollama" in resp.json()["detail"]


# ── Chunks Endpoint ───────────────────────────────────────────────────


def test_api_get_chunks_missing_doc(client: TestClient):
    resp = client.get("/api/documents/nonexistent/chunks")
    assert resp.status_code == 404


def test_api_get_chunks_success(client: TestClient, monkeypatch):
    _setup_mock_ollama(monkeypatch)

    upload_resp = client.post(
        "/api/documents",
        files={
            "file": (
                "manuscript.txt",
                b"First paragraph of the manuscript.\n\nSecond paragraph of the manuscript.",
                "text/plain",
            )
        },
    )
    doc_id = upload_resp.json()["id"]
    client.post(f"/api/documents/{doc_id}/process")

    resp = client.get(f"/api/documents/{doc_id}/chunks")
    assert resp.status_code == 200
    data = resp.json()
    assert data["document_id"] == doc_id
    assert data["total"] == 2
    assert len(data["chunks"]) == 2
    assert data["chunks"][0]["chunk_index"] == 0
    assert "embedding" not in data["chunks"][0]  # Verify raw vector omitted


# ── Search Endpoint ───────────────────────────────────────────────────


def test_api_search_empty_query(client: TestClient):
    resp = client.post("/api/search", json={"query": "   "})
    assert resp.status_code == 400


def test_api_search_success(client: TestClient, monkeypatch):
    _setup_mock_ollama(monkeypatch)

    # Ingest a document
    upload_resp = client.post(
        "/api/documents",
        files={
            "file": (
                "astronomy.md",
                b"# Observatories\n\nThe brass telescopes recorded comet trajectories across centuries.",
                "text/markdown",
            )
        },
    )
    doc_id = upload_resp.json()["id"]
    client.post(f"/api/documents/{doc_id}/process")

    # Search
    search_resp = client.post("/api/search", json={"query": "brass telescope", "top_k": 3})
    assert search_resp.status_code == 200
    data = search_resp.json()
    assert data["query"] == "brass telescope"
    assert data["total"] >= 1
    assert data["embedding_model"] == settings.embedding_model
    assert len(data["results"]) >= 1
    first = data["results"][0]
    assert first["document_id"] == doc_id
    assert "brass telescopes" in first["text"]
    assert "similarity_score" in first


def test_api_search_document_filter(client: TestClient, monkeypatch):
    _setup_mock_ollama(monkeypatch)

    # Ingest two documents
    d1 = client.post(
        "/api/documents",
        files={"file": ("doc_a.txt", b"First subject matter document.", "text/plain")},
    ).json()["id"]
    client.post(f"/api/documents/{d1}/process")

    d2 = client.post(
        "/api/documents",
        files={"file": ("doc_b.txt", b"Second subject matter document.", "text/plain")},
    ).json()["id"]
    client.post(f"/api/documents/{d2}/process")

    # Search filtering exclusively for doc_b
    search_resp = client.post(
        "/api/search",
        json={"query": "document", "document_ids": [d2]},
    )
    assert search_resp.status_code == 200
    results = search_resp.json()["results"]
    for r in results:
        assert r["document_id"] == d2


def test_api_search_ollama_offline(client: TestClient, monkeypatch):
    orig_post = httpx.Client.post

    def mock_fail(self, url, *args, **kwargs):
        if "api/embed" in str(url):
            raise httpx.ConnectError("Ollama offline")
        return orig_post(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "post", mock_fail)

    resp = client.post("/api/search", json={"query": "test query"})
    assert resp.status_code == 503
    assert "Cannot connect to Ollama" in resp.json()["detail"]


def test_api_search_dimension_mismatch(client: TestClient, monkeypatch):
    """Search returns 422 if stored chunk dimension does not match query embedding dimension."""
    orig_post = httpx.Client.post

    # Ingest document with 4D vectors
    def mock_post_4d(self, url, *args, **kwargs):
        if "api/embed" in str(url):
            count = len(kwargs.get("json", {}).get("input", []))
            return httpx.Response(
                status_code=200,
                json={"embeddings": [[0.1, 0.2, 0.3, 0.4]] * count},
                request=httpx.Request("POST", str(url)),
            )
        return orig_post(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "post", mock_post_4d)

    d1 = client.post(
        "/api/documents",
        files={"file": ("lore.txt", b"Ancient archive text.", "text/plain")},
    ).json()["id"]
    client.post(f"/api/documents/{d1}/process")

    # Now simulate query returning a 3D vector
    def mock_post_3d(self, url, *args, **kwargs):
        if "api/embed" in str(url):
            return httpx.Response(
                status_code=200,
                json={"embeddings": [[0.1, 0.2, 0.3]]},
                request=httpx.Request("POST", str(url)),
            )
        return orig_post(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "post", mock_post_3d)

    resp = client.post("/api/search", json={"query": "ancient archive"})
    assert resp.status_code == 422
    assert "dimension mismatch" in resp.json()["detail"].lower()


def test_api_search_model_mismatch(client: TestClient, monkeypatch):
    """Search returns 422 if document was indexed with a model different from active query model."""
    orig_post = httpx.Client.post

    def mock_post(self, url, *args, **kwargs):
        if "api/embed" in str(url):
            count = len(kwargs.get("json", {}).get("input", []))
            return httpx.Response(
                status_code=200,
                json={"embeddings": [[0.1, 0.2, 0.3, 0.4]] * count},
                request=httpx.Request("POST", str(url)),
            )
        return orig_post(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    # Ingest document with model A
    monkeypatch.setattr("app.config.settings.embedding_model", "old-model")
    d1 = client.post(
        "/api/documents",
        files={"file": ("legacy.txt", b"Legacy text.", "text/plain")},
    ).json()["id"]
    client.post(f"/api/documents/{d1}/process")

    # Change active model to model B
    monkeypatch.setattr("app.config.settings.embedding_model", "new-model")

    resp = client.post("/api/search", json={"query": "legacy"})
    assert resp.status_code == 422
    assert "model mismatch" in resp.json()["detail"].lower()

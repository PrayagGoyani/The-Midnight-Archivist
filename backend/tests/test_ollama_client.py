"""Tests for Ollama embedding client."""
from __future__ import annotations

import httpx
import pytest

from app.services.ollama_client import (
    OllamaConnectionError,
    OllamaEmbeddingError,
    OllamaModelError,
    embed_texts,
)


def test_embed_texts_empty_list():
    with pytest.raises(OllamaEmbeddingError, match="No texts provided"):
        embed_texts([])


def test_embed_texts_success(monkeypatch):
    recorded_requests = []

    def mock_post(self, url, json=None, **kwargs):
        recorded_requests.append({"url": url, "json": json})
        count = len(json["input"])
        # Return 4-dimensional vectors
        return httpx.Response(
            status_code=200,
            json={"embeddings": [[0.1, 0.2, 0.3, 0.4]] * count},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    result = embed_texts(
        ["Passage one", "Passage two"],
        model="nomic-embed-text",
        base_url="http://localhost:11434",
    )

    assert len(result.embeddings) == 2
    assert result.dimensions == 4
    assert result.model == "nomic-embed-text"
    assert len(recorded_requests) == 1
    assert recorded_requests[0]["json"]["truncate"] is False
    assert recorded_requests[0]["json"]["model"] == "nomic-embed-text"


def test_embed_texts_batching(monkeypatch):
    call_count = 0

    def mock_post(self, url, json=None, **kwargs):
        nonlocal call_count
        call_count += 1
        count = len(json["input"])
        return httpx.Response(
            status_code=200,
            json={"embeddings": [[0.5, 0.5]] * count},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    texts = [f"Text #{i}" for i in range(7)]
    result = embed_texts(texts, batch_size=3)

    assert len(result.embeddings) == 7
    assert call_count == 3  # 3 batches: 3 + 3 + 1


def test_embed_texts_model_not_found(monkeypatch):
    def mock_post(self, url, json=None, **kwargs):
        return httpx.Response(
            status_code=404,
            text="model not found",
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    with pytest.raises(OllamaModelError, match="not found"):
        embed_texts(["Some text"], model="nonexistent-model")


def test_embed_texts_connection_error(monkeypatch):
    def mock_post(self, url, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    with pytest.raises(OllamaConnectionError, match="Cannot connect to Ollama"):
        embed_texts(["Some text"])


def test_embed_texts_timeout(monkeypatch):
    def mock_post(self, url, **kwargs):
        raise httpx.TimeoutException("Timed out")

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    with pytest.raises(OllamaConnectionError, match="timed out"):
        embed_texts(["Some text"])


def test_embed_texts_nan_value(monkeypatch):
    def mock_post(self, url, json=None, **kwargs):
        # Python's json.loads supports parsing NaN from raw JSON text
        return httpx.Response(
            status_code=200,
            content=b'{"embeddings": [[0.1, NaN, 0.3]]}',
            headers={"Content-Type": "application/json"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    with pytest.raises(OllamaEmbeddingError, match="invalid value"):
        embed_texts(["Check nan"])


def test_embed_texts_dimension_mismatch(monkeypatch):
    def mock_post(self, url, json=None, **kwargs):
        return httpx.Response(
            status_code=200,
            json={"embeddings": [[0.1, 0.2], [0.1, 0.2, 0.3]]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    with pytest.raises(OllamaEmbeddingError, match="Dimension mismatch"):
        embed_texts(["Text 1", "Text 2"])

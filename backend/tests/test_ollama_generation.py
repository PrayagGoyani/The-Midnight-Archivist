"""Tests for the local Ollama text-generation client."""
from __future__ import annotations

import httpx
import pytest

from app.services.ollama_generation import (
    OllamaConnectionError,
    OllamaGenerationClient,
    OllamaMalformedResponseError,
    OllamaModelNotFoundError,
    OllamaResponseError,
    OllamaTimeoutError,
)


def test_generation_success(monkeypatch):
    """Successful chat completion returns model content."""
    mock_payload = {
        "model": "llama3.2:3b",
        "message": {
            "role": "assistant",
            "content": '{"title": "The Vault", "content": "Cold air seeped through stone.", "branch_choices": []}',
        },
        "done": True,
    }

    def mock_post(self, url, **kwargs):
        req = httpx.Request("POST", url)
        return httpx.Response(200, json=mock_payload, request=req)

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    client = OllamaGenerationClient(base_url="http://mock-ollama:11434", default_model="llama3.2:3b")
    content = client.generate_chat_completion([{"role": "user", "content": "Write a story"}])
    assert "The Vault" in content
    assert "Cold air" in content


def test_generation_model_not_found(monkeypatch):
    """Missing model returns OllamaModelNotFoundError."""
    def mock_post(self, url, **kwargs):
        req = httpx.Request("POST", url)
        return httpx.Response(404, text='{"error": "model \'missing\' not found"}', request=req)

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    client = OllamaGenerationClient(base_url="http://mock-ollama:11434", default_model="missing")
    with pytest.raises(OllamaModelNotFoundError, match="was not found in Ollama"):
        client.generate_chat_completion([{"role": "user", "content": "Hello"}])


def test_generation_connection_error(monkeypatch):
    """Connection failure raises OllamaConnectionError."""
    def mock_post(self, url, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    client = OllamaGenerationClient(base_url="http://mock-ollama:11434")
    with pytest.raises(OllamaConnectionError, match="Cannot connect to Ollama"):
        client.generate_chat_completion([{"role": "user", "content": "Hello"}])


def test_generation_timeout(monkeypatch):
    """Generation timeout raises OllamaTimeoutError."""
    def mock_post(self, url, **kwargs):
        req = httpx.Request("POST", url)
        raise httpx.TimeoutException("Read timed out", request=req)

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    client = OllamaGenerationClient(base_url="http://mock-ollama:11434", timeout=5.0)
    with pytest.raises(OllamaTimeoutError, match="timed out"):
        client.generate_chat_completion([{"role": "user", "content": "Hello"}])


def test_generation_malformed_json_response(monkeypatch):
    """Non-JSON response raises OllamaMalformedResponseError."""
    def mock_post(self, url, **kwargs):
        req = httpx.Request("POST", url)
        return httpx.Response(200, text="NOT JSON AT ALL", request=req)

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    client = OllamaGenerationClient(base_url="http://mock-ollama:11434")
    with pytest.raises(OllamaMalformedResponseError, match="Failed to parse Ollama response as JSON"):
        client.generate_chat_completion([{"role": "user", "content": "Hello"}])


def test_generation_missing_message_field(monkeypatch):
    """Response missing 'message' field raises OllamaMalformedResponseError."""
    def mock_post(self, url, **kwargs):
        req = httpx.Request("POST", url)
        return httpx.Response(200, json={"done": True}, request=req)

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    client = OllamaGenerationClient(base_url="http://mock-ollama:11434")
    with pytest.raises(OllamaMalformedResponseError, match="missing 'message.content'"):
        client.generate_chat_completion([{"role": "user", "content": "Hello"}])


def test_generation_non_200_error(monkeypatch):
    """HTTP 500 error raises OllamaResponseError."""
    def mock_post(self, url, **kwargs):
        req = httpx.Request("POST", url)
        return httpx.Response(500, text="Internal Server Error", request=req)

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    client = OllamaGenerationClient(base_url="http://mock-ollama:11434")
    with pytest.raises(OllamaResponseError, match="HTTP 500"):
        client.generate_chat_completion([{"role": "user", "content": "Hello"}])

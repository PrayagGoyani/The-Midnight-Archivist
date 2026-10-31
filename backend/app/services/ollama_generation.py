"""Ollama local text-generation client for narrative generation and continuation."""
from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from ..config import settings


class OllamaGenerationError(Exception):
    """Base exception for Ollama text-generation errors."""
    pass


class OllamaConnectionError(OllamaGenerationError):
    """Raised when the client cannot connect to Ollama."""
    pass


class OllamaTimeoutError(OllamaGenerationError):
    """Raised when Ollama generation times out."""
    pass


class OllamaModelNotFoundError(OllamaGenerationError):
    """Raised when the requested generation model is not installed or available."""
    pass


class OllamaResponseError(OllamaGenerationError):
    """Raised when Ollama returns an HTTP error status code."""
    pass


class OllamaMalformedResponseError(OllamaGenerationError):
    """Raised when Ollama returns an unexpected or malformed response body."""
    pass


class OllamaGenerationClient:
    """Client for local Ollama chat/generation endpoint."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.default_model = default_model or settings.ollama_generation_model
        self.timeout = timeout or float(settings.ollama_generation_timeout)

    def generate_chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        model: Optional[str] = None,
        format_json: bool = True,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Send a chat completion request to Ollama.

        Args:
            messages: List of message dicts (e.g. [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]).
            model: Generation model name (defaults to configured model).
            format_json: If True, instructs Ollama to enforce valid JSON output format.
            temperature: Sampling temperature (defaults to settings.ollama_temperature).
            max_tokens: Maximum tokens to predict (defaults to settings.ollama_max_tokens).

        Returns:
            The raw text content from the model's message.

        Raises:
            OllamaConnectionError: Cannot connect to Ollama.
            OllamaTimeoutError: Request exceeded configured timeout.
            OllamaModelNotFoundError: Model not found.
            OllamaResponseError: Non-200 HTTP response.
            OllamaMalformedResponseError: Missing or invalid message content in response.
        """
        target_model = model or self.default_model
        temp = temperature if temperature is not None else settings.ollama_temperature
        tokens = max_tokens if max_tokens is not None else settings.ollama_max_tokens

        payload: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temp,
                "num_predict": tokens,
            },
        }
        if format_json:
            payload["format"] = "json"

        endpoint = f"{self.base_url}/api/chat"

        try:
            with httpx.Client(timeout=self.timeout, headers={"Connection": "close"}) as client:
                response = client.post(endpoint, json=payload)
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise OllamaConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. Ensure the service is active."
            ) from exc
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError(
                f"Ollama generation timed out after {self.timeout}s for model '{target_model}'."
            ) from exc
        except Exception as exc:
            raise OllamaConnectionError(
                f"Unexpected error communicating with Ollama: {exc}"
            ) from exc

        if response.status_code == 404:
            raise OllamaModelNotFoundError(
                f"Generation model '{target_model}' was not found in Ollama. Pull it using `ollama pull {target_model}`."
            )

        if response.status_code != 200:
            raise OllamaResponseError(
                f"Ollama returned HTTP {response.status_code}: {response.text[:300]}"
            )

        try:
            data = response.json()
        except Exception as exc:
            raise OllamaMalformedResponseError(
                f"Failed to parse Ollama response as JSON: {exc}"
            ) from exc

        message = data.get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise OllamaMalformedResponseError(
                f"Ollama response missing 'message.content' field: {data}"
            )

        content = message["content"]
        if not isinstance(content, str):
            raise OllamaMalformedResponseError(
                f"Ollama message content is not a string: {type(content)}"
            )

        return content


_default_generation_client: Optional[OllamaGenerationClient] = None


def get_generation_client() -> OllamaGenerationClient:
    """Return a shared OllamaGenerationClient instance."""
    global _default_generation_client
    if _default_generation_client is None:
        _default_generation_client = OllamaGenerationClient()
    return _default_generation_client

"""Local Ollama embedding client."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass

import httpx


class OllamaConnectionError(Exception):
    """Ollama server is not reachable."""
    pass


class OllamaModelError(Exception):
    """The requested model is not available in Ollama."""
    pass


class OllamaEmbeddingError(Exception):
    """Embedding request failed for an unexpected reason."""
    pass


@dataclass
class EmbeddingResult:
    """Result of an embedding batch request."""

    embeddings: list[list[float]]
    model: str
    dimensions: int


def _validate_vector(vec: list[float], index: int) -> None:
    """Check a single embedding vector for NaN or Inf values."""
    for i, v in enumerate(vec):
        if math.isnan(v) or math.isinf(v):
            raise OllamaEmbeddingError(
                f"Embedding vector {index} contains invalid value at dimension {i}: {v}"
            )


def embed_texts(
    texts: list[str],
    *,
    model: str = "nomic-embed-text",
    base_url: str = "http://localhost:11434",
    batch_size: int = 32,
    timeout: int = 120,
) -> EmbeddingResult:
    """Embed a list of texts using the local Ollama server.

    Sends requests to POST /api/embed in batches.
    Uses truncate=false so Ollama does not silently truncate inputs.

    Args:
        texts: Non-empty list of texts to embed.
        model: Ollama model name (e.g. "nomic-embed-text").
        base_url: Ollama server URL.
        batch_size: Maximum texts per request.
        timeout: Request timeout in seconds.

    Returns:
        EmbeddingResult with all embedding vectors.

    Raises:
        OllamaConnectionError: Server unreachable.
        OllamaModelError: Model not found.
        OllamaEmbeddingError: Invalid response or data.
    """
    if not texts:
        raise OllamaEmbeddingError("No texts provided for embedding.")

    all_embeddings: list[list[float]] = []
    dimensions: int | None = None

    url = f"{base_url.rstrip('/')}/api/embed"

    for batch_start in range(0, len(texts), batch_size):
        batch = texts[batch_start : batch_start + batch_size]

        payload = {
            "model": model,
            "input": batch,
            "truncate": False,
        }

        try:
            with httpx.Client(timeout=timeout, headers={"Connection": "close"}) as client:
                response = client.post(url, json=payload)
        except httpx.ConnectError:
            raise OllamaConnectionError(
                f"Cannot connect to Ollama at {base_url}. "
                "Ensure Ollama is running (ollama serve)."
            )
        except httpx.TimeoutException:
            raise OllamaConnectionError(
                f"Ollama request timed out after {timeout}s. "
                "The model may be loading or the input is too large."
            )
        except httpx.HTTPError as e:
            raise OllamaConnectionError(f"HTTP error communicating with Ollama: {e}")

        if response.status_code == 404:
            raise OllamaModelError(
                f"Model '{model}' not found. Pull it with: ollama pull {model}"
            )

        if response.status_code != 200:
            detail = response.text[:500] if response.text else "No details"
            raise OllamaEmbeddingError(
                f"Ollama returned status {response.status_code}: {detail}"
            )

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError):
            raise OllamaEmbeddingError(
                "Ollama returned invalid JSON in the embedding response."
            )

        embeddings = data.get("embeddings")
        if not embeddings or not isinstance(embeddings, list):
            raise OllamaEmbeddingError(
                "Ollama response missing 'embeddings' array."
            )

        if len(embeddings) != len(batch):
            raise OllamaEmbeddingError(
                f"Expected {len(batch)} embeddings but got {len(embeddings)}."
            )

        # Validate each vector
        for idx, vec in enumerate(embeddings):
            if not isinstance(vec, list):
                raise OllamaEmbeddingError(
                    f"Embedding {idx} is not a list: {type(vec)}"
                )
            _validate_vector(vec, batch_start + idx)

            # Check dimension consistency
            if dimensions is None:
                dimensions = len(vec)
            elif len(vec) != dimensions:
                raise OllamaEmbeddingError(
                    f"Dimension mismatch: expected {dimensions} but embedding "
                    f"{batch_start + idx} has {len(vec)} dimensions."
                )

        all_embeddings.extend(embeddings)

    return EmbeddingResult(
        embeddings=all_embeddings,
        model=model,
        dimensions=dimensions or 0,
    )

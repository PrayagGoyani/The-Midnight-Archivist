"""Cosine similarity search over stored chunk embeddings with strict compatibility validation."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session

from ..models import Chunk, Document


class RetrievalError(Exception):
    """Base exception for vector retrieval errors."""
    pass


class EmbeddingDimensionMismatchError(RetrievalError):
    """Raised when query and chunk vector dimensions do not match."""
    pass


class EmbeddingModelMismatchError(RetrievalError):
    """Raised when chunk was embedded with a different model than the query."""
    pass


class MalformedVectorError(RetrievalError):
    """Raised when an embedding vector is malformed, missing, or corrupted."""
    pass


@dataclass
class SearchResult:
    """A single search result with similarity score."""

    chunk_id: str
    document_id: str
    document_title: str
    text: str
    page_number: int | None
    section: str | None
    similarity_score: float


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors using numpy.

    Raises:
        EmbeddingDimensionMismatchError: Vectors have different lengths.
        MalformedVectorError: A vector is empty or contains NaN/Inf values.
    """
    if len(a) == 0 or len(b) == 0:
        raise MalformedVectorError("Cannot compute cosine similarity for an empty vector.")

    if len(a) != len(b):
        raise EmbeddingDimensionMismatchError(
            f"Vector dimension mismatch: vector A has {len(a)} dimensions, "
            f"but vector B has {len(b)} dimensions."
        )

    for i, val in enumerate(a):
        if math.isnan(val) or math.isinf(val):
            raise MalformedVectorError(f"Vector A contains non-finite value at index {i}: {val}")

    for i, val in enumerate(b):
        if math.isnan(val) or math.isinf(val):
            raise MalformedVectorError(f"Vector B contains non-finite value at index {i}: {val}")

    va = np.array(a, dtype=np.float64)
    vb = np.array(b, dtype=np.float64)

    norm_a = float(np.linalg.norm(va))
    norm_b = float(np.linalg.norm(vb))

    # Safe zero-vector handling
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    sim = float(np.dot(va, vb) / (norm_a * norm_b))
    return max(-1.0, min(1.0, sim))


def search_chunks(
    query_embedding: list[float],
    db: Session,
    *,
    query_model: str | None = None,
    top_k: int = 5,
    document_ids: list[str] | None = None,
    min_similarity: float = 0.0,
) -> list[SearchResult]:
    """Search for chunks most similar to the query embedding.

    Performs strict compatibility checks:
    - Verifies stored vectors have identical dimensions to query_embedding.
    - Verifies embedding model compatibility if query_model is provided.
    - Validates against NaN, infinity, and malformed JSON vectors.

    Raises:
        EmbeddingDimensionMismatchError: Dimension difference detected.
        EmbeddingModelMismatchError: Model difference detected.
        MalformedVectorError: Missing, corrupted, or non-finite vectors.
    """
    if not query_embedding or len(query_embedding) == 0:
        raise MalformedVectorError("Query embedding vector cannot be empty.")

    for i, val in enumerate(query_embedding):
        if math.isnan(val) or math.isinf(val):
            raise MalformedVectorError(f"Query embedding contains non-finite value at index {i}: {val}")

    query = (
        db.query(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .filter(
            Document.status == "ready",
            Chunk.embedding.isnot(None),
        )
    )

    if document_ids:
        query = query.filter(Document.id.in_(document_ids))

    results: list[tuple[float, SearchResult]] = []

    for chunk, doc in query.all():
        # 1. Model compatibility check
        if query_model and chunk.embedding_model and chunk.embedding_model != query_model:
            raise EmbeddingModelMismatchError(
                f"Embedding model mismatch: Chunk '{chunk.id}' in document '{doc.title}' "
                f"was indexed using '{chunk.embedding_model}', but search query was embedded "
                f"using '{query_model}'. Please re-index the document to resolve this conflict."
            )

        # 2. Embedding JSON validation
        if not chunk.embedding or not chunk.embedding.strip():
            raise MalformedVectorError(
                f"Chunk '{chunk.id}' in document '{doc.title}' has empty embedding data."
            )

        try:
            stored_embedding = json.loads(chunk.embedding)
        except (json.JSONDecodeError, TypeError) as e:
            raise MalformedVectorError(
                f"Chunk '{chunk.id}' in document '{doc.title}' contains invalid JSON vector: {e}"
            )

        if not isinstance(stored_embedding, list):
            raise MalformedVectorError(
                f"Chunk '{chunk.id}' in document '{doc.title}' embedding is not a JSON array: "
                f"{type(stored_embedding)}"
            )

        # 3. Dimension compatibility check
        if len(stored_embedding) != len(query_embedding):
            raise EmbeddingDimensionMismatchError(
                f"Embedding dimension mismatch: Search query has {len(query_embedding)} dimensions, "
                f"but chunk '{chunk.id}' in document '{doc.title}' has {len(stored_embedding)} dimensions. "
                f"Please re-index document '{doc.title}' with the active model."
            )

        # 4. Compute similarity (also validates NaN/inf and handles zero vectors safely)
        sim = cosine_similarity(query_embedding, stored_embedding)

        if sim < min_similarity:
            continue

        results.append(
            (
                sim,
                SearchResult(
                    chunk_id=chunk.id,
                    document_id=doc.id,
                    document_title=doc.title,
                    text=chunk.text,
                    page_number=chunk.page_number,
                    section=chunk.section,
                    similarity_score=round(sim, 6),
                ),
            )
        )

    # Sort descending by similarity, take top_k
    results.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in results[:top_k]]

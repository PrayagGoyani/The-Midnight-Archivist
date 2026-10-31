"""Tests for vector retrieval, cosine similarity search, and compatibility validation."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.models import Chunk, Document
from app.services.retrieval import (
    EmbeddingDimensionMismatchError,
    EmbeddingModelMismatchError,
    MalformedVectorError,
    cosine_similarity,
    search_chunks,
)


# ── Cosine Similarity ─────────────────────────────────────────────────


def test_cosine_similarity_identical():
    v = [1.0, 2.0, 3.0]
    sim = cosine_similarity(v, v)
    assert math.isclose(sim, 1.0, rel_tol=1e-5)


def test_cosine_similarity_orthogonal():
    v1 = [1.0, 0.0]
    v2 = [0.0, 1.0]
    sim = cosine_similarity(v1, v2)
    assert math.isclose(sim, 0.0, abs_tol=1e-5)


def test_cosine_similarity_opposite():
    v1 = [1.0, 0.0]
    v2 = [-1.0, 0.0]
    sim = cosine_similarity(v1, v2)
    assert math.isclose(sim, -1.0, rel_tol=1e-5)


def test_cosine_similarity_zero_vector():
    # Safely returns 0.0 without division by zero error
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity([1.0, 2.0], [0.0, 0.0]) == 0.0


def test_cosine_similarity_dimension_mismatch():
    with pytest.raises(EmbeddingDimensionMismatchError, match="Vector dimension mismatch"):
        cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])


def test_cosine_similarity_empty():
    with pytest.raises(MalformedVectorError, match="empty vector"):
        cosine_similarity([], [])


def test_cosine_similarity_nan_or_inf():
    with pytest.raises(MalformedVectorError, match="non-finite value"):
        cosine_similarity([1.0, float("nan")], [1.0, 2.0])

    with pytest.raises(MalformedVectorError, match="non-finite value"):
        cosine_similarity([1.0, 2.0], [float("inf"), 2.0])


# ── Chunk Search ──────────────────────────────────────────────────────


def test_search_chunks_ranking_and_filters(db_session: Session):
    # 1. Ready document with 2 chunks
    doc1 = Document(
        id="doc_ready_1",
        title="Grimoire of Shadows",
        original_filename="shadows.txt",
        stored_filename="shadows.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=100,
        status="ready",
    )
    chunk1_1 = Chunk(
        id="c1",
        document_id=doc1.id,
        chunk_index=0,
        text="The candle flickers in the drafty hall.",
        page_number=1,
        section="Chapter 1",
        embedding=json.dumps([1.0, 0.0, 0.0]),
        embedding_model="nomic-embed-text",
    )
    chunk1_2 = Chunk(
        id="c2",
        document_id=doc1.id,
        chunk_index=1,
        text="An ancient key turns with difficulty in the lock.",
        page_number=2,
        section="Chapter 2",
        embedding=json.dumps([0.0, 1.0, 0.0]),
        embedding_model="nomic-embed-text",
    )

    # 2. Another ready document
    doc2 = Document(
        id="doc_ready_2",
        title="Maritime Records",
        original_filename="maritime.txt",
        stored_filename="maritime.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=200,
        status="ready",
    )
    chunk2_1 = Chunk(
        id="c3",
        document_id=doc2.id,
        chunk_index=0,
        text="The salt air preserves the parchment bindings.",
        page_number=1,
        section="Ledger",
        embedding=json.dumps([0.8, 0.2, 0.0]),
        embedding_model="nomic-embed-text",
    )

    # 3. Document that is NOT ready (status=processing) — must be excluded
    doc3 = Document(
        id="doc_processing_3",
        title="Unprocessed Draft",
        original_filename="draft.txt",
        stored_filename="draft.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=50,
        status="processing",
    )
    chunk3_1 = Chunk(
        id="c4",
        document_id=doc3.id,
        chunk_index=0,
        text="Draft content that should not appear.",
        embedding=json.dumps([1.0, 0.0, 0.0]),
        embedding_model="nomic-embed-text",
    )

    db_session.add_all([doc1, doc2, doc3, chunk1_1, chunk1_2, chunk2_1, chunk3_1])
    db_session.commit()

    # Query vector close to [1.0, 0.0, 0.0]
    query_vec = [0.95, 0.05, 0.0]

    # Search all documents
    results = search_chunks(query_vec, db_session, query_model="nomic-embed-text", top_k=5)

    assert len(results) == 3
    # c1 should be highest score
    assert results[0].chunk_id == "c1"
    assert results[0].document_title == "Grimoire of Shadows"
    assert results[0].similarity_score > 0.9

    # c3 should be second highest
    assert results[1].chunk_id == "c3"
    assert results[1].document_title == "Maritime Records"

    # c4 from unready document should not be present
    found_ids = {r.chunk_id for r in results}
    assert "c4" not in found_ids

    # Search with document_ids filter (only doc2)
    filtered_results = search_chunks(
        query_vec, db_session, query_model="nomic-embed-text", top_k=5, document_ids=["doc_ready_2"]
    )
    assert len(filtered_results) == 1
    assert filtered_results[0].chunk_id == "c3"

    # Search with top_k=1
    top1 = search_chunks(query_vec, db_session, query_model="nomic-embed-text", top_k=1)
    assert len(top1) == 1
    assert top1[0].chunk_id == "c1"


def test_search_chunks_dimension_mismatch(db_session: Session):
    doc = Document(
        id="doc_mismatch",
        title="Mismatch Doc",
        original_filename="mismatch.txt",
        stored_filename="mismatch.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=100,
        status="ready",
    )
    chunk = Chunk(
        id="c_mismatch",
        document_id=doc.id,
        chunk_index=0,
        text="Sample text",
        embedding=json.dumps([0.1, 0.2, 0.3]),  # 3 dimensions
        embedding_model="nomic-embed-text",
    )
    db_session.add_all([doc, chunk])
    db_session.commit()

    # Query has 4 dimensions -> Must raise informative EmbeddingDimensionMismatchError!
    with pytest.raises(EmbeddingDimensionMismatchError, match="Embedding dimension mismatch"):
        search_chunks([0.1, 0.2, 0.3, 0.4], db_session, query_model="nomic-embed-text")


def test_search_chunks_model_mismatch(db_session: Session):
    doc = Document(
        id="doc_old_model",
        title="Old Model Doc",
        original_filename="old.txt",
        stored_filename="old.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=100,
        status="ready",
    )
    chunk = Chunk(
        id="c_old",
        document_id=doc.id,
        chunk_index=0,
        text="Sample text",
        embedding=json.dumps([0.1, 0.2]),
        embedding_model="all-minilm",  # Different model
    )
    db_session.add_all([doc, chunk])
    db_session.commit()

    # Query uses nomic-embed-text -> Must raise informative EmbeddingModelMismatchError!
    with pytest.raises(EmbeddingModelMismatchError, match="Embedding model mismatch"):
        search_chunks([0.1, 0.2], db_session, query_model="nomic-embed-text")


def test_search_chunks_corrupted_vector(db_session: Session):
    doc = Document(
        id="doc_corrupt",
        title="Corrupted Vector Doc",
        original_filename="corrupt.txt",
        stored_filename="corrupt.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=100,
        status="ready",
    )
    chunk = Chunk(
        id="c_corrupt",
        document_id=doc.id,
        chunk_index=0,
        text="Corrupted vector chunk",
        embedding="not a valid json list",
        embedding_model="nomic-embed-text",
    )
    db_session.add_all([doc, chunk])
    db_session.commit()

    with pytest.raises(MalformedVectorError, match="invalid JSON vector"):
        search_chunks([0.1, 0.2], db_session, query_model="nomic-embed-text")

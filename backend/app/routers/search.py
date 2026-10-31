"""Semantic search endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..dependencies import get_db
from ..schemas import ErrorResponse, SearchRequest, SearchResponse, SearchResultItem
from ..services.ollama_client import (
    OllamaConnectionError,
    OllamaEmbeddingError,
    OllamaModelError,
    embed_texts,
)
from ..services.retrieval import (
    EmbeddingDimensionMismatchError,
    EmbeddingModelMismatchError,
    MalformedVectorError,
    search_chunks,
)

router = APIRouter(prefix="/search", tags=["search"])


@router.post(
    "",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def semantic_search(
    request: SearchRequest,
    db: Session = Depends(get_db),
) -> SearchResponse:
    """Perform semantic cosine similarity search over indexed chunks."""
    cleaned_query = request.query.strip()
    if not cleaned_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty or whitespace only.",
        )

    # 1. Embed the search query
    try:
        embedding_result = embed_texts(
            [cleaned_query],
            model=settings.embedding_model,
            base_url=settings.ollama_base_url,
            batch_size=1,
            timeout=settings.ollama_timeout,
        )
    except (OllamaConnectionError, OllamaModelError) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except OllamaEmbeddingError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate query embedding: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error generating query embedding: {e}",
        )

    query_embedding = embedding_result.embeddings[0]

    # 2. Search database for nearest chunks with compatibility validation
    try:
        results = search_chunks(
            query_embedding=query_embedding,
            db=db,
            query_model=settings.embedding_model,
            top_k=request.top_k,
            document_ids=request.document_ids,
        )
    except (EmbeddingDimensionMismatchError, EmbeddingModelMismatchError, MalformedVectorError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    items = [
        SearchResultItem(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            document_title=r.document_title,
            text=r.text,
            page_number=r.page_number,
            section=r.section,
            similarity_score=r.similarity_score,
        )
        for r in results
    ]

    return SearchResponse(
        query=cleaned_query,
        total=len(items),
        embedding_model=settings.embedding_model,
        results=items,
    )

"""Health check and system status endpoints."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends
import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..database import check_db
from ..dependencies import get_db
from ..models import Chunk, Document, Story
from ..schemas import (
    HealthResponse,
    SystemDatabaseStatus,
    SystemOllamaStatus,
    SystemStorageStatus,
    SystemStatusResponse,
)

router = APIRouter(tags=["health"])


def _check_ollama_models() -> tuple[str, list[str], bool, bool]:
    """Query local Ollama /api/tags and verify model availability."""
    ollama_url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    available_models: list[str] = []
    ollama_status = "unreachable"

    try:
        with httpx.Client(timeout=4.0, headers={"Connection": "close"}) as client:
            resp = client.get(ollama_url)
            if resp.status_code == 200:
                ollama_status = "connected"
                data = resp.json()
                models = data.get("models", [])
                for m in models:
                    name = m.get("name") or m.get("model")
                    if name:
                        available_models.append(name)
    except Exception:
        ollama_status = "unreachable"

    def _is_model_present(target: str) -> bool:
        target_clean = target.lower()
        target_base = target_clean.split(":")[0]
        for m in available_models:
            m_clean = m.lower()
            if m_clean == target_clean:
                return True
            if m_clean.split(":")[0] == target_base:
                return True
        return False

    gen_ok = _is_model_present(settings.generation_model)
    emb_ok = _is_model_present(settings.embedding_model)

    return ollama_status, available_models, gen_ok, emb_ok


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Check application and database health."""
    db_ok = check_db()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database="connected" if db_ok else "unavailable",
    )


@router.get("/system/status", response_model=SystemStatusResponse)
def system_status(db: Session = Depends(get_db)) -> SystemStatusResponse:
    """Check comprehensive runtime status of SQLite, storage, and Ollama."""
    db_ok = check_db()

    # Model and connection check
    ollama_status, available_models, gen_ok, emb_ok = _check_ollama_models()

    # Query counts safely
    try:
        doc_count = db.query(Document).count()
        chunk_count = db.query(Chunk).count()
        story_count = db.query(Story).count()
    except Exception:
        doc_count, chunk_count, story_count = 0, 0, 0

    overall_healthy = db_ok and (ollama_status == "connected") and gen_ok and emb_ok

    return SystemStatusResponse(
        status="healthy" if overall_healthy else "degraded",
        version="0.1.0",
        database=SystemDatabaseStatus(
            status="connected" if db_ok else "unavailable",
            engine="sqlite",
            path="Local storage (data/archivist.db)",
        ),
        ollama=SystemOllamaStatus(
            status=ollama_status,
            base_url=settings.ollama_base_url,
            generation_model=settings.generation_model,
            generation_model_available=gen_ok,
            embedding_model=settings.embedding_model,
            embedding_model_available=emb_ok,
            available_models=available_models,
        ),
        storage=SystemStorageStatus(
            data_dir="Local storage (data)",
            upload_dir="Local storage (data/uploads)",
            max_upload_size_mb=settings.upload_max_size_mb,
            document_count=doc_count,
            chunk_count=chunk_count,
            story_count=story_count,
        ),
    )


@router.get("/ollama/status", response_model=SystemOllamaStatus)
def ollama_status() -> SystemOllamaStatus:
    """Check live status of Ollama specifically."""
    status_str, available_models, gen_ok, emb_ok = _check_ollama_models()
    return SystemOllamaStatus(
        status=status_str,
        base_url=settings.ollama_base_url,
        generation_model=settings.generation_model,
        generation_model_available=gen_ok,
        embedding_model=settings.embedding_model,
        embedding_model_available=emb_ok,
        available_models=available_models,
    )


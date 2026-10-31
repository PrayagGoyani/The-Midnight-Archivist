"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Health & System Status ──────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    database: str
    version: str = "0.1.0"


class SystemDatabaseStatus(BaseModel):
    status: str
    engine: str = "sqlite"
    path: str


class SystemOllamaStatus(BaseModel):
    status: str
    base_url: str
    generation_model: str
    generation_model_available: bool
    embedding_model: str
    embedding_model_available: bool
    available_models: list[str]


class SystemStorageStatus(BaseModel):
    data_dir: str
    upload_dir: str
    max_upload_size_mb: int
    document_count: int
    chunk_count: int
    story_count: int


class SystemStatusResponse(BaseModel):
    status: str
    version: str = "0.1.0"
    database: SystemDatabaseStatus
    ollama: SystemOllamaStatus
    storage: SystemStorageStatus


# ── Documents ───────────────────────────────────────────────────────

class DocumentOut(BaseModel):
    id: str
    title: str
    original_filename: str
    file_extension: str
    content_type: str
    file_size: int
    status: str
    error_message: Optional[str] = None
    page_count: Optional[int] = None
    indexed_at: Optional[datetime] = None
    embedding_model_used: Optional[str] = None
    chunk_count: Optional[int] = None
    reindex_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentOut]
    total: int


class ProcessingResponse(BaseModel):
    document_id: str
    title: str
    status: str
    chunk_count: int
    embedding_model: str
    dimensions: int
    indexed_at: datetime


# ── Chunks ──────────────────────────────────────────────────────────

class ChunkOut(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    text: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    embedding_model: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChunkListResponse(BaseModel):
    chunks: list[ChunkOut]
    total: int
    document_id: str


# ── Search ──────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    document_ids: Optional[list[str]] = None
    top_k: int = Field(default=5, ge=1, le=50)


class SearchResultItem(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    text: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    similarity_score: float


class SearchResponse(BaseModel):
    query: str
    total: int
    embedding_model: str
    results: list[SearchResultItem]


# ── Stories ─────────────────────────────────────────────────────────

class BranchChoice(BaseModel):
    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    description: str = Field(default="")


class StoryGenerateRequest(BaseModel):
    premise: str = Field(..., min_length=1, max_length=2000)
    atmosphere: str = Field(default="Gothic", min_length=1, max_length=100)
    length: str = Field(default="short", pattern=r"^(short|medium|long)$")
    grounding_mode: str = Field(default="freeform", pattern=r"^(archive|freeform)$")
    document_ids: Optional[list[str]] = None
    top_k: int = Field(default=3, ge=1, le=10)


class StoryContinueRequest(BaseModel):
    choice_id: str = Field(..., min_length=1)


class StoryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    premise: str = Field(..., min_length=1)
    atmosphere: str = Field(..., min_length=1, max_length=100)
    requested_length: str = Field(..., pattern=r"^(short|medium|long)$")
    grounding_mode: str = Field(default="freeform", pattern=r"^(archive|freeform)$")
    body: str = Field(..., min_length=1)
    source_references: Optional[str] = Field(default="[]")
    parent_story_id: Optional[str] = None
    branch_choice: Optional[str] = None
    branch_choices: Optional[str] = Field(default="[]")
    word_count: Optional[int] = None
    generation_model: Optional[str] = None
    status: Optional[str] = "completed"

    @field_validator("source_references")
    @classmethod
    def validate_source_references(cls, v: Optional[str]) -> str:
        if v is None:
            return "[]"
        import json
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, list):
                raise ValueError("source_references must be a JSON array")
        except json.JSONDecodeError:
            raise ValueError("source_references must be valid JSON")
        return v


class StoryOut(BaseModel):
    id: str
    title: str
    premise: str
    atmosphere: str
    requested_length: str
    grounding_mode: str
    body: str
    source_references: Optional[str] = None
    parent_story_id: Optional[str] = None
    branch_choice: Optional[str] = None
    branch_choices: Optional[str] = None
    word_count: Optional[int] = None
    generation_model: Optional[str] = None
    status: Optional[str] = "completed"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StoryGenerationResponse(BaseModel):
    id: str
    title: str
    content: str
    body: str
    premise: str
    atmosphere: str
    requested_length: str
    grounding_mode: str
    branch_choices: list[BranchChoice]
    source_references: list[dict]
    parent_story_id: Optional[str] = None
    branch_choice: Optional[str] = None
    word_count: int
    generation_model: str
    status: str
    created_at: datetime


class NarrativeSegment(BaseModel):
    story_id: str
    title: str
    branch_label: Optional[str] = None
    content: str
    word_count: Optional[int] = None
    created_at: datetime


class FullStoryNarrativeResponse(BaseModel):
    story_id: str
    title: str
    premise: str
    atmosphere: str
    grounding_mode: str
    full_content: str
    total_word_count: int
    segments: list[NarrativeSegment]
    available_choices: list[BranchChoice]
    source_references: list[dict]


class ChildBranchNode(BaseModel):
    story_id: str
    branch_label: Optional[str] = None
    title: str
    preview: str
    created_at: datetime


class StoryBranchesResponse(BaseModel):
    story_id: str
    title: str
    available_choices: list[BranchChoice]
    child_branches: list[ChildBranchNode]


class StoryListResponse(BaseModel):
    stories: list[StoryOut]
    total: int


# ── Errors ──────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str

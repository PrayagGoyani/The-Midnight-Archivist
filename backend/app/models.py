"""SQLAlchemy ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(32), primary_key=True, default=_new_id)
    title = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    stored_filename = Column(String(500), nullable=False, unique=True)
    file_extension = Column(String(20), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    status = Column(
        Enum("uploaded", "processing", "ready", "failed", name="document_status"),
        nullable=False,
        default="uploaded",
    )
    error_message = Column(Text, nullable=True)
    page_count = Column(Integer, nullable=True)
    # Phase 3 — indexing metadata
    indexed_at = Column(DateTime(timezone=True), nullable=True)
    embedding_model_used = Column(String(100), nullable=True)
    chunk_count = Column(Integer, nullable=True)
    reindex_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    chunks = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_documents_created", "created_at"),)


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String(32), primary_key=True, default=_new_id)
    document_id = Column(
        String(32), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    section = Column(String(500), nullable=True)
    embedding = Column(Text, nullable=True)  # JSON-serialized float vector
    embedding_model = Column(String(100), nullable=True)  # Phase 3 — model that produced the embedding
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    document = relationship("Document", back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_document", "document_id"),
        Index("ix_chunks_document_index", "document_id", "chunk_index"),
    )


class Story(Base):
    __tablename__ = "stories"

    id = Column(String(32), primary_key=True, default=_new_id)
    title = Column(String(500), nullable=False)
    premise = Column(Text, nullable=False)
    atmosphere = Column(String(100), nullable=False)
    requested_length = Column(String(50), nullable=False)
    grounding_mode = Column(
        Enum("archive", "freeform", name="grounding_mode"),
        nullable=False,
        default="freeform",
    )
    body = Column(Text, nullable=False)
    source_references = Column(Text, nullable=True, default="[]")  # JSON array
    parent_story_id = Column(
        String(32), ForeignKey("stories.id", ondelete="SET NULL"), nullable=True
    )
    branch_choice = Column(String(500), nullable=True)
    # Phase 4A — Branching narrative & generation metadata
    branch_choices = Column(Text, nullable=True, default="[]")  # JSON array of available choices
    word_count = Column(Integer, nullable=True)
    generation_model = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default="completed")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    parent = relationship("Story", remote_side=[id], foreign_keys=[parent_story_id])

    __table_args__ = (Index("ix_stories_created", "created_at"),)

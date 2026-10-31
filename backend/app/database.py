"""SQLite database engine and session management."""
from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    """Declarative base for all models."""
    pass


_db_url = settings.resolve_database_path()
engine = create_engine(_db_url, connect_args={"check_same_thread": False}, echo=False)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign keys and WAL mode for SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables and apply lightweight column migrations if needed.
    
    Safe to call multiple times.
    """
    Base.metadata.create_all(bind=engine)

    # Lightweight column migration for existing SQLite databases
    with engine.begin() as conn:
        # Check documents columns
        cursor = conn.exec_driver_sql("PRAGMA table_info(documents)")
        existing_doc_cols = {row[1] for row in cursor.fetchall()}
        if "indexed_at" not in existing_doc_cols:
            conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN indexed_at DATETIME")
        if "embedding_model_used" not in existing_doc_cols:
            conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN embedding_model_used VARCHAR(100)")
        if "chunk_count" not in existing_doc_cols:
            conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN chunk_count INTEGER")
        if "reindex_error" not in existing_doc_cols:
            conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN reindex_error TEXT")

        # Check chunks columns
        cursor = conn.exec_driver_sql("PRAGMA table_info(chunks)")
        existing_chunk_cols = {row[1] for row in cursor.fetchall()}
        if "embedding_model" not in existing_chunk_cols:
            conn.exec_driver_sql("ALTER TABLE chunks ADD COLUMN embedding_model VARCHAR(100)")

        # Check stories columns (Phase 4A)
        cursor = conn.exec_driver_sql("PRAGMA table_info(stories)")
        existing_story_cols = {row[1] for row in cursor.fetchall()}
        if "branch_choices" not in existing_story_cols:
            conn.exec_driver_sql("ALTER TABLE stories ADD COLUMN branch_choices TEXT DEFAULT '[]'")
        if "word_count" not in existing_story_cols:
            conn.exec_driver_sql("ALTER TABLE stories ADD COLUMN word_count INTEGER")
        if "generation_model" not in existing_story_cols:
            conn.exec_driver_sql("ALTER TABLE stories ADD COLUMN generation_model VARCHAR(100)")
        if "status" not in existing_story_cols:
            conn.exec_driver_sql("ALTER TABLE stories ADD COLUMN status VARCHAR(50) DEFAULT 'completed'")


def check_db() -> bool:
    """Return True if the database is accessible."""
    try:
        with Session(engine) as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

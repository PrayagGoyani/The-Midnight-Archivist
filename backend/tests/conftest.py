"""Pytest fixtures for backend tests."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from collections.abc import Generator

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from app.database import Base
from app.dependencies import get_db
from app.main import app


@pytest.fixture(scope="function")
def tmp_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory for uploads."""
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    return tmp_path


@pytest.fixture(scope="function")
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    """Create a fresh in-memory SQLite database for each test."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(scope="function")
def client(db_session: Session, tmp_data_dir: Path, monkeypatch) -> Generator[TestClient, None, None]:
    """Create a test client with an isolated database and storage."""
    # Patch settings to use temporary upload directory
    monkeypatch.setattr("app.config.settings.data_dir", str(tmp_data_dir))
    monkeypatch.setattr("app.config.Settings.resolve_upload_dir", lambda self: tmp_data_dir / "uploads")

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()

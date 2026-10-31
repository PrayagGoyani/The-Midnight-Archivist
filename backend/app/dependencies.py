"""FastAPI dependency injection."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and ensure cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_settings():
    """Return the application settings singleton."""
    return settings

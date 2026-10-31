"""Application configuration via environment variables."""
from __future__ import annotations

import json
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Midnight Archivist configuration.

    Loaded from a .env file in the backend directory, then from
    environment variables. Sensible local defaults are provided.
    """

    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # Database — relative paths are resolved from the backend directory
    database_url: str = "sqlite:///data/archivist.db"

    # Local storage
    data_dir: str = "data"
    upload_max_size_mb: int = 20

    # CORS
    cors_origins: str = '["http://localhost:5173","http://127.0.0.1:5173"]'

    # Ollama (Phase 3 & Phase 4)
    ollama_base_url: str = "http://localhost:11434"
    ollama_generation_model: str = "llama3.2:3b"
    generation_model: str = "llama3.2:3b"  # Alias for backward compatibility
    embedding_model: str = "nomic-embed-text"
    ollama_generation_timeout: int = 180
    ollama_temperature: float = 0.75
    ollama_max_tokens: int = 2048

    # Chunking (Phase 3)
    chunk_size: int = 1200
    chunk_overlap: int = 180
    embedding_batch_size: int = 32
    ollama_timeout: int = 120

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def parsed_cors_origins(self) -> list[str]:
        return json.loads(self.cors_origins)

    @property
    def upload_max_bytes(self) -> int:
        return self.upload_max_size_mb * 1024 * 1024

    def resolve_data_dir(self) -> Path:
        """Resolve the data directory relative to the backend root."""
        raw = Path(self.data_dir)
        if raw.is_absolute():
            data_path = raw
        else:
            backend_root = Path(__file__).resolve().parent.parent
            data_path = backend_root / self.data_dir
        data_path.mkdir(parents=True, exist_ok=True)
        return data_path

    def resolve_upload_dir(self) -> Path:
        """Resolve the uploads subdirectory."""
        upload_path = self.resolve_data_dir() / "uploads"
        upload_path.mkdir(parents=True, exist_ok=True)
        return upload_path

    def resolve_database_path(self) -> str:
        """Resolve the SQLite database path.

        If database_url uses the sqlite:/// scheme with a relative path,
        resolve it relative to the backend root directory.
        """
        if self.database_url.startswith("sqlite:///"):
            raw = self.database_url.replace("sqlite:///", "")
            raw_path = Path(raw)
            if not raw_path.is_absolute():
                backend_root = Path(__file__).resolve().parent.parent
                abs_path = backend_root / raw
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                return f"sqlite:///{abs_path.as_posix()}"
            else:
                return f"sqlite:///{raw_path.as_posix()}"
        return self.database_url


settings = Settings()

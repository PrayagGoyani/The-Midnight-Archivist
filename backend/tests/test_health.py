"""Tests for the health endpoint."""
from __future__ import annotations


def test_health_returns_ok(client):
    """Health endpoint reports database status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "version" in data


def test_health_degraded_when_db_fails(client, monkeypatch):
    """Health endpoint reports degraded when database check fails."""
    monkeypatch.setattr("app.routers.health.check_db", lambda: False)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "unavailable"


def test_system_status_success(client, monkeypatch):
    """System status returns detailed connectivity and counts."""
    # Mock Ollama check returning models
    monkeypatch.setattr(
        "app.routers.health._check_ollama_models",
        lambda: ("connected", ["llama3.2:3b", "nomic-embed-text:latest"], True, True),
    )
    response = client.get("/api/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"]["status"] == "connected"
    assert data["ollama"]["status"] == "connected"
    assert data["ollama"]["generation_model_available"] is True
    assert data["ollama"]["embedding_model_available"] is True
    assert data["storage"]["max_upload_size_mb"] > 0


def test_system_status_unreachable_ollama(client, monkeypatch):
    """System status reports degraded when Ollama is unreachable."""
    monkeypatch.setattr(
        "app.routers.health._check_ollama_models",
        lambda: ("unreachable", [], False, False),
    )
    response = client.get("/api/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["ollama"]["status"] == "unreachable"
    assert data["ollama"]["generation_model_available"] is False


def test_ollama_status_endpoint(client, monkeypatch):
    """Ollama status endpoint returns specific Ollama metadata."""
    monkeypatch.setattr(
        "app.routers.health._check_ollama_models",
        lambda: ("connected", ["llama3.2:3b"], True, False),
    )
    response = client.get("/api/ollama/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "connected"
    assert data["generation_model_available"] is True
    assert data["embedding_model_available"] is False


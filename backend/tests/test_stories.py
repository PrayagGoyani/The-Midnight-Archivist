"""Tests for story endpoints."""
from __future__ import annotations

import json


VALID_STORY = {
    "title": "The Hollow Staircase",
    "premise": "A librarian discovers that the stairs in her building go down one floor further than they should.",
    "atmosphere": "haunted",
    "requested_length": "medium",
    "grounding_mode": "freeform",
    "body": "She noticed it on a Tuesday. The stairwell, which had always ended at B1, now continued downward.",
    "source_references": "[]",
}


def test_create_story(client):
    """Creating a valid story returns 201."""
    resp = client.post("/api/stories", json=VALID_STORY)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == VALID_STORY["title"]
    assert data["atmosphere"] == "haunted"
    assert "id" in data


def test_create_story_missing_title(client):
    """Creating a story without a title returns 422."""
    payload = {**VALID_STORY}
    del payload["title"]
    resp = client.post("/api/stories", json=payload)
    assert resp.status_code == 422


def test_create_story_invalid_length(client):
    """Creating a story with an invalid length returns 422."""
    payload = {**VALID_STORY, "requested_length": "epic"}
    resp = client.post("/api/stories", json=payload)
    assert resp.status_code == 422


def test_create_story_invalid_grounding(client):
    """Creating a story with an invalid grounding mode returns 422."""
    payload = {**VALID_STORY, "grounding_mode": "internet"}
    resp = client.post("/api/stories", json=payload)
    assert resp.status_code == 422


def test_create_story_invalid_source_refs(client):
    """source_references must be valid JSON array."""
    payload = {**VALID_STORY, "source_references": "not json"}
    resp = client.post("/api/stories", json=payload)
    assert resp.status_code == 422


def test_create_story_with_parent(client):
    """Creating a continuation of an existing story succeeds."""
    resp1 = client.post("/api/stories", json=VALID_STORY)
    parent_id = resp1.json()["id"]
    child = {**VALID_STORY, "title": "Chapter 2", "parent_story_id": parent_id, "branch_choice": "descend"}
    resp2 = client.post("/api/stories", json=child)
    assert resp2.status_code == 201
    assert resp2.json()["parent_story_id"] == parent_id


def test_create_story_unknown_parent(client):
    """Referencing a nonexistent parent story returns 404."""
    payload = {**VALID_STORY, "parent_story_id": "ghost123"}
    resp = client.post("/api/stories", json=payload)
    assert resp.status_code == 404


def test_list_stories_empty(client):
    """Listing stories when none exist returns empty."""
    resp = client.get("/api/stories")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_list_stories(client):
    """Listing stories returns saved stories."""
    client.post("/api/stories", json=VALID_STORY)
    client.post("/api/stories", json={**VALID_STORY, "title": "Another"})
    resp = client.get("/api/stories")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_get_story(client):
    """Retrieving a story returns its full content."""
    resp = client.post("/api/stories", json=VALID_STORY)
    story_id = resp.json()["id"]
    resp2 = client.get(f"/api/stories/{story_id}")
    assert resp2.status_code == 200
    assert resp2.json()["body"] == VALID_STORY["body"]


def test_get_missing_story(client):
    """Requesting a nonexistent story returns 404."""
    resp = client.get("/api/stories/nonexistent")
    assert resp.status_code == 404


def test_delete_story(client):
    """Deleting a story removes it."""
    resp = client.post("/api/stories", json=VALID_STORY)
    story_id = resp.json()["id"]
    del_resp = client.delete(f"/api/stories/{story_id}")
    assert del_resp.status_code == 204
    assert client.get(f"/api/stories/{story_id}").status_code == 404


def test_delete_missing_story(client):
    """Deleting a nonexistent story returns 404."""
    resp = client.delete("/api/stories/nope")
    assert resp.status_code == 404

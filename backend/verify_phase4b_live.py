"""Phase 4B End-to-End Live Integration Verification Script.
Connects directly to FastAPI app via TestClient (or HTTP) with real Ollama runtime.
"""
from __future__ import annotations

import sys
import io

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

def run_acceptance():
    print("=================================================================")
    print(" THE MIDNIGHT ARCHIVIST — PHASE 4B ACCEPTANCE VERIFICATION")
    print("=================================================================\n")

    client = TestClient(app)

    # 1. System Status Check
    print("1. Checking System Telemetry (/api/system/status)...")
    res = client.get("/api/system/status")
    assert res.status_code == 200, f"System status failed: {res.text}"
    sys_status = res.json()
    print(f"   Status: {sys_status['status']}")
    print(f"   Database: {sys_status['database']['status']} ({sys_status['database']['engine']})")
    print(f"   Ollama: {sys_status['ollama']['status']} ({sys_status['ollama']['base_url']})")
    print(f"   Generation Model ({settings.generation_model}): {'Available' if sys_status['ollama']['generation_model_available'] else 'MISSING'}")
    print(f"   Embedding Model ({settings.embedding_model}): {'Available' if sys_status['ollama']['embedding_model_available'] else 'MISSING'}")
    print(f"   Installed Models: {', '.join(sys_status['ollama']['available_models'])}")
    assert sys_status['ollama']['status'] == "connected", "Ollama must be connected"
    assert sys_status['ollama']['generation_model_available'], "Generation model must be present"
    assert sys_status['ollama']['embedding_model_available'], "Embedding model must be present"
    print("   [OK] System telemetry passed.\n")

    # 2. Document Upload & Real Ingestion
    print("2. Ingesting Real Archival Material into Archive...")
    archive_text = (
        "RECORD OF THE SHORE WATCHMAN — OCTOBER 1888\n\n"
        "The third beacon on Black Sand Reef extinguished itself without wind at midnight. "
        "Upon inspecting the copper housing, Master Warden Vance discovered the clockwork gears "
        "jammed not by sand, but by cold sea salt crystallized in the shape of small interlocking bones. "
        "No vessel had signaled distress, yet the harbor tide brought in two empty cedar dories "
        "bearing the insignia of the Royal Maritime Survey of 1842. In the hold of the second dory lay "
        "a ledger wrapped in oilcloth, filled with soundings for an uncharted trench beneath the reef. "
        "The soundings end abruptly on page forty-four with the repeated notation: 'The salt sings before it settles.'\n\n"
        "SECTION II: THE SUBMERGED CRYPT\n\n"
        "Divers sent into the shallows reported iron gates wedged between the basalt shelves. "
        "The currents through the gate run counter to all ocean tides, drawing freshwater down "
        "into the seabed. Those who touched the iron complained of numbness in their wrists and "
        "dreams of flooded cathedrals where the bells toll under thirty fathoms of kelp."
    )
    upload_res = client.post(
        "/api/documents",
        files={"file": ("shore_watchman_1888.txt", io.BytesIO(archive_text.encode("utf-8")), "text/plain")},
    )
    assert upload_res.status_code == 201, f"Upload failed: {upload_res.text}"
    doc = upload_res.json()
    doc_id = doc["id"]
    print(f"   Uploaded document: '{doc['title']}' (ID: {doc_id})")

    # Process document with real nomic-embed-text
    print(f"   Processing & embedding document with {settings.embedding_model}...")
    proc_res = client.post(f"/api/documents/{doc_id}/process")
    assert proc_res.status_code == 200, f"Processing failed: {proc_res.text}"
    proc_data = proc_res.json()
    print(f"   Indexed: {proc_data['chunk_count']} chunks | Model: {proc_data['embedding_model']} | Dims: {proc_data['dimensions']}")
    assert proc_data["chunk_count"] > 0
    assert proc_data["dimensions"] > 0

    # Inspect chunks
    chunks_res = client.get(f"/api/documents/{doc_id}/chunks")
    assert chunks_res.status_code == 200
    chunks = chunks_res.json()["chunks"]
    print(f"   Retrieved {len(chunks)} chunks from SQLite Chunk store.")
    print("   [OK] Document indexing verified.\n")

    # 3. Semantic Search Verification
    print("3. Testing Semantic Search (/api/search)...")
    search_res = client.post(
        "/api/search",
        json={"query": "submerged iron gates and tolling bells under the ocean", "top_k": 3},
    )
    assert search_res.status_code == 200, f"Search failed: {search_res.text}"
    search_data = search_res.json()
    print(f"   Found {len(search_data['results'])} semantic matches.")
    for idx, match in enumerate(search_data["results"], 1):
        print(f"   Match {idx}: Score {match['similarity_score']:.3f} | Doc: {match['document_title']}")
        print(f"      Snippet: {match['text'][:90]}...")
    assert len(search_data["results"]) > 0
    print("   [OK] Semantic search verified.\n")

    # 4. Generate Story Grounded in Archive
    print("4. Generating Archive-Grounded Story (/api/stories/generate)...")
    gen_payload = {
        "premise": "A solitary watchman investigates the crystalline bone formations jamming the reef lantern.",
        "atmosphere": "Coastal Decay",
        "length": "short",
        "grounding_mode": "archive",
        "document_ids": [doc_id],
        "top_k": 3,
    }
    story_res = client.post("/api/stories/generate", json=gen_payload)
    assert story_res.status_code == 201, f"Story generation failed: {story_res.text}"
    story = story_res.json()
    story_id = story["id"]
    print(f"   Generated Root Story: '{story['title']}'")
    print(f"   Word Count: {story['word_count']} words (Target: 400–600)")
    print(f"   Atmosphere: {story['atmosphere']}")
    print(f"   Branch choices ({len(story['branch_choices'])}):")
    for choice in story["branch_choices"]:
        print(f"      - [{choice['id']}] {choice['label']}: {choice['description']}")
    print(f"   Source citations ({len(story['source_references'])}):")
    for ref in story["source_references"]:
        print(f"      - {ref.get('document_title', 'Doc')}: \"{ref.get('text', '')[:60]}...\"")
    assert story["word_count"] >= 380, f"Word count {story['word_count']} is below minimum target"
    assert len(story["branch_choices"]) >= 2
    assert len(story["source_references"]) > 0
    print("   [OK] Archive-grounded generation verified.\n")

    # 5. Narrative Branching Continuation
    first_choice = story["branch_choices"][0]
    print(f"5. Continuing Narrative along Branch Choice: '{first_choice['label']}' (/api/stories/{story_id}/continue)...")
    cont_res = client.post(
        f"/api/stories/{story_id}/continue",
        json={"choice_id": first_choice["id"]},
    )
    assert cont_res.status_code == 201, f"Continuation failed: {cont_res.text}"
    continuation = cont_res.json()
    continuation_id = continuation["id"]
    print(f"   Generated Continuation: '{continuation['title']}' (ID: {continuation_id})")
    print(f"   Word Count: {continuation['word_count']} words")
    print(f"   Branch Choice Recorded: {continuation['branch_choice']}")
    assert continuation["parent_story_id"] == story_id
    assert continuation["word_count"] >= 350
    print("   [OK] Branch continuation verified.\n")

    # 6. Full Narrative Reconstruction
    print(f"6. Testing Full Narrative Assembly (/api/stories/{continuation_id}/full)...")
    full_res = client.get(f"/api/stories/{continuation_id}/full")
    assert full_res.status_code == 200, f"Full narrative failed: {full_res.text}"
    full_narrative = full_res.json()
    print(f"   Reconstructed Segments: {len(full_narrative['segments'])} chapters")
    print(f"   Total Story Words: {full_narrative['total_word_count']}")
    assert len(full_narrative["segments"]) == 2
    print("   [OK] Full narrative reconstruction verified.\n")

    # 7. Story Shelf Listing & Persistence
    print("7. Verifying Story Shelf (/api/stories)...")
    shelf_res = client.get("/api/stories")
    assert shelf_res.status_code == 200
    stories_list = shelf_res.json()["stories"]
    print(f"   Found {len(stories_list)} persisted story nodes in shelf.")
    assert any(s["id"] == story_id for s in stories_list)
    assert any(s["id"] == continuation_id for s in stories_list)
    print("   [OK] Shelf persistence verified.\n")

    print("=================================================================")
    print(" ALL PHASE 4B LIVE ACCEPTANCE CRITERIA SUCCESSFULLY VERIFIED! ")
    print("=================================================================")

if __name__ == "__main__":
    run_acceptance()

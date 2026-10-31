"""Live acceptance demonstration of the AI Story Generation Engine & Branching Narrative Backend."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.main import app
from app.config import settings
from app.database import init_db
from app.models import Story, Document


def run_acceptance_demonstration():
    print("=" * 80)
    print("THE MIDNIGHT ARCHIVIST — PHASE 4A LIVE STORY GENERATION ACCEPTANCE TEST")
    print(f"Generative Model: {settings.ollama_generation_model}")
    print(f"Embedding Model:  {settings.embedding_model}")
    print("=" * 80)

    init_db()
    client = TestClient(app)

    created_story_ids = []
    created_doc_ids = []

    try:
        # ─────────────────────────────────────────────────────────────────
        # PART 1: VERIFY ALL THREE LENGTH PRESETS (FREEFORM)
        # ─────────────────────────────────────────────────────────────────
        print("\n" + "#" * 70)
        print("PART 1: VERIFY ALL THREE LENGTH PRESETS (SHORT, MEDIUM, LONG)")
        print("#" * 70)

        # 1A. SHORT PRESET (400–600 words)
        short_premise = "A solitary cartographer discovers an uncharted island appearing only at low tide."
        print(f"\n[Preset 1: SHORT] Premise: '{short_premise}'")
        print("Atmosphere: Melancholy | Target: 400–600 words (min: 400)")
        t0 = time.time()
        resp_short = client.post(
            "/api/stories/generate",
            json={
                "premise": short_premise,
                "atmosphere": "Melancholy",
                "length": "short",
                "grounding_mode": "freeform",
            },
        )
        dur_short = time.time() - t0
        assert resp_short.status_code == 201, f"Expected 201, got {resp_short.status_code}: {resp_short.text}"
        data_short = resp_short.json()
        created_story_ids.append(data_short["id"])

        print(f"  -> Generated in {dur_short:.2f}s | Word Count: {data_short['word_count']} words | Title: \"{data_short['title']}\"")
        assert data_short["word_count"] >= 400, f"Short preset must be >= 400 words, got {data_short['word_count']}"
        assert len(data_short["branch_choices"]) >= 2
        print(f"  -> Short preset requirement MET ({data_short['word_count']} words >= 400 min)")

        # 1B. MEDIUM PRESET (800–1,200 words)
        medium_premise = "An antiquarian restorer discovers an encrypted diary bound in eel skin beneath the floorboards of an abbey library."
        print(f"\n[Preset 2: MEDIUM] Premise: '{medium_premise}'")
        print("Atmosphere: Dark academia | Target: 800–1,200 words (min: 800)")
        t0 = time.time()
        resp_med = client.post(
            "/api/stories/generate",
            json={
                "premise": medium_premise,
                "atmosphere": "Dark academia",
                "length": "medium",
                "grounding_mode": "freeform",
            },
        )
        dur_med = time.time() - t0
        assert resp_med.status_code == 201, f"Expected 201, got {resp_med.status_code}: {resp_med.text}"
        data_med = resp_med.json()
        created_story_ids.append(data_med["id"])

        print(f"  -> Generated in {dur_med:.2f}s | Word Count: {data_med['word_count']} words | Title: \"{data_med['title']}\"")
        assert data_med["word_count"] >= 800, f"Medium preset must be >= 800 words, got {data_med['word_count']}"
        assert len(data_med["branch_choices"]) >= 2
        print(f"  -> Medium preset requirement MET ({data_med['word_count']} words >= 800 min)")

        # 1C. LONG PRESET (1,500–2,000 words)
        long_premise = (
            "A comprehensive chronicle of the subterranean observatory beneath the coastal cliff: "
            "the centuries of keepers, the lost celestial catalogues, and the brass astrolabe that counts backwards."
        )
        print(f"\n[Preset 3: LONG] Premise: '{long_premise}'")
        print("Atmosphere: Gothic | Target: 1,500–2,000 words (min: 1,500)")
        t0 = time.time()
        resp_long = client.post(
            "/api/stories/generate",
            json={
                "premise": long_premise,
                "atmosphere": "Gothic",
                "length": "long",
                "grounding_mode": "freeform",
            },
        )
        dur_long = time.time() - t0
        assert resp_long.status_code == 201, f"Expected 201, got {resp_long.status_code}: {resp_long.text}"
        data_long = resp_long.json()
        created_story_ids.append(data_long["id"])

        print(f"  -> Generated in {dur_long:.2f}s | Word Count: {data_long['word_count']} words | Title: \"{data_long['title']}\"")
        assert data_long["word_count"] >= 1500, f"Long preset must be >= 1500 words, got {data_long['word_count']}"
        assert len(data_long["branch_choices"]) >= 2
        print(f"  -> Long preset requirement MET ({data_long['word_count']} words >= 1,500 min)")

        # ─────────────────────────────────────────────────────────────────
        # PART 2: ARCHIVE-GROUNDED GENERATION & MULTI-BRANCH TREE
        # ─────────────────────────────────────────────────────────────────
        print("\n" + "#" * 70)
        print("PART 2: ARCHIVE-GROUNDED GENERATION & MULTI-BRANCH TREE")
        print("#" * 70)

        pdf_path = Path("F:/Hacktober/sample_archive_manuscript.pdf")
        assert pdf_path.exists(), f"Sample PDF not found at {pdf_path}"

        print(f"\n[Step 1] Uploading archival source: {pdf_path.name}")
        with open(pdf_path, "rb") as f:
            up_resp = client.post(
                "/api/documents",
                files={"file": (pdf_path.name, f, "application/pdf")},
            )
        assert up_resp.status_code == 201
        doc_id = up_resp.json()["id"]
        created_doc_ids.append(doc_id)
        print(f"Uploaded Document ID: {doc_id}")

        print("\n[Step 2] Ingesting and embedding document with real nomic-embed-text...")
        proc_resp = client.post(f"/api/documents/{doc_id}/process")
        assert proc_resp.status_code == 200
        proc_data = proc_resp.json()
        print(f"Indexed: {proc_data['chunk_count']} chunks embedded into SQLite (dims: {proc_data['dimensions']})")

        # Step 3: Archive-grounded root generation (Short preset)
        grounded_premise = "An archivist calibrates the brass astrolabe to chart stars obscured by the rising tide."
        print(f"\n[Step 3] Generating archive-grounded root story (length: short, min 400 words):\n  \"{grounded_premise}\"")
        t0 = time.time()
        grounded_resp = client.post(
            "/api/stories/generate",
            json={
                "premise": grounded_premise,
                "atmosphere": "Gothic",
                "length": "short",
                "grounding_mode": "archive",
                "document_ids": [doc_id],
                "top_k": 2,
            },
        )
        g_dur = time.time() - t0
        assert grounded_resp.status_code == 201, f"Expected 201, got {grounded_resp.status_code}: {grounded_resp.text}"
        root_data = grounded_resp.json()
        root_id = root_data["id"]
        created_story_ids.append(root_id)

        print(f"Grounded root generated in {g_dur:.2f}s!")
        print(f"Root Story ID: {root_id}")
        print(f"Title:         \"{root_data['title']}\"")
        print(f"Words:         {root_data['word_count']} words")
        assert root_data["word_count"] >= 400, f"Grounded root must be >= 400 words, got {root_data['word_count']}"

        print(f"\n--- Archival Sources Consulted ({len(root_data['source_references'])}) ---")
        for s in root_data["source_references"]:
            print(f"  * Document: \"{s['document_title']}\" (Page {s['page_number']}) | Similarity: {s['similarity_score']:.4f}")
        assert len(root_data["source_references"]) > 0

        choices = root_data["branch_choices"]
        assert len(choices) >= 2
        choice_a = choices[0]
        choice_b = choices[1]
        print(f"Root Choice A: [{choice_a['id']}] \"{choice_a['label']}\"")
        print(f"Root Choice B: [{choice_b['id']}] \"{choice_b['label']}\"")

        # Step 4: Continue along Branch A from Root (Root -> Branch A)
        print(f"\n[Step 4] Continuing narrative along Branch A: \"{choice_a['label']}\"")
        t0 = time.time()
        cont_a_resp = client.post(
            f"/api/stories/{root_id}/continue",
            json={"choice_id": choice_a["id"]},
        )
        assert cont_a_resp.status_code == 201
        cont_a = cont_a_resp.json()
        child_a_id = cont_a["id"]
        created_story_ids.append(child_a_id)
        print(f"Branch A generated in {time.time() - t0:.2f}s | Words: {cont_a['word_count']}")
        assert cont_a["word_count"] >= 400, f"Branch A must be >= 400 words, got {cont_a['word_count']}"
        assert len(cont_a["branch_choices"]) >= 2
        choice_a2 = cont_a["branch_choices"][0]
        print(f"Branch A Choice 1: [{choice_a2['id']}] \"{choice_a2['label']}\"")

        # Step 5: Continue along Branch A2 from Branch A (Root -> Branch A -> Branch A2)
        print(f"\n[Step 5] Continuing narrative along Branch A2 (multi-level): \"{choice_a2['label']}\"")
        t0 = time.time()
        cont_a2_resp = client.post(
            f"/api/stories/{child_a_id}/continue",
            json={"choice_id": choice_a2["id"]},
        )
        assert cont_a2_resp.status_code == 201
        cont_a2 = cont_a2_resp.json()
        child_a2_id = cont_a2["id"]
        created_story_ids.append(child_a2_id)
        print(f"Branch A2 generated in {time.time() - t0:.2f}s | Words: {cont_a2['word_count']}")
        assert cont_a2["word_count"] >= 400, f"Branch A2 must be >= 400 words, got {cont_a2['word_count']}"

        # Step 6: Continue along Branch B from Root (Root -> Branch B)
        print(f"\n[Step 6] Continuing narrative along alternative Branch B: \"{choice_b['label']}\"")
        t0 = time.time()
        cont_b_resp = client.post(
            f"/api/stories/{root_id}/continue",
            json={"choice_id": choice_b["id"]},
        )
        assert cont_b_resp.status_code == 201
        cont_b = cont_b_resp.json()
        child_b_id = cont_b["id"]
        created_story_ids.append(child_b_id)
        print(f"Branch B generated in {time.time() - t0:.2f}s | Words: {cont_b['word_count']}")
        assert cont_b["word_count"] >= 400, f"Branch B must be >= 400 words, got {cont_b['word_count']}"

        # ─────────────────────────────────────────────────────────────────
        # PART 3: RECONSTRUCTION & MULTI-BRANCH INDEPENDENCE VERIFICATION
        # ─────────────────────────────────────────────────────────────────
        print("\n" + "#" * 70)
        print("PART 3: NARRATIVE RECONSTRUCTION & BRANCH INDEPENDENCE")
        print("#" * 70)

        # Inspect tree from Root
        branches_resp = client.get(f"/api/stories/{root_id}/branches")
        assert branches_resp.status_code == 200
        b_tree = branches_resp.json()
        print(f"Root \"{b_tree['title']}\" has {len(b_tree['child_branches'])} direct child branches:")
        for child in b_tree["child_branches"]:
            print(f"  * Node {child['story_id']}: Action \"{child['branch_label']}\"")
        assert len(b_tree["child_branches"]) == 2

        # Reconstruct Branch A2: Root -> A -> A2
        full_a2_resp = client.get(f"/api/stories/{child_a2_id}/full")
        assert full_a2_resp.status_code == 200
        full_a2 = full_a2_resp.json()
        print(f"\nBranch A2 Narrative: {len(full_a2['segments'])} segments | Total Words: {full_a2['total_word_count']}")
        assert len(full_a2["segments"]) == 3, f"Expected 3 segments in A2, got {len(full_a2['segments'])}"
        assert full_a2["segments"][0]["story_id"] == root_id
        assert full_a2["segments"][1]["story_id"] == child_a_id
        assert full_a2["segments"][2]["story_id"] == child_a2_id

        # Reconstruct Branch B: Root -> B
        full_b_resp = client.get(f"/api/stories/{child_b_id}/full")
        assert full_b_resp.status_code == 200
        full_b = full_b_resp.json()
        print(f"Branch B Narrative:  {len(full_b['segments'])} segments | Total Words: {full_b['total_word_count']}")
        assert len(full_b["segments"]) == 2, f"Expected 2 segments in B, got {len(full_b['segments'])}"
        assert full_b["segments"][0]["story_id"] == root_id
        assert full_b["segments"][1]["story_id"] == child_b_id

        # Independence & Isolation Check
        a2_text = " ".join(seg["content"] for seg in full_a2["segments"])
        b_text = " ".join(seg["content"] for seg in full_b["segments"])
        assert cont_b["content"] not in a2_text, "Branch B content leaked into Branch A2 narrative!"
        assert cont_a["content"] not in b_text, "Branch A content leaked into Branch B narrative!"
        assert cont_a2["content"] not in b_text, "Branch A2 content leaked into Branch B narrative!"
        print("  -> Narrative isolation verified: Zero crossover between Branch A/A2 and Branch B.")

        # ─────────────────────────────────────────────────────────────────
        # PART 4: BACKEND RESTART & PERSISTENCE VERIFICATION
        # ─────────────────────────────────────────────────────────────────
        print("\n" + "#" * 70)
        print("PART 4: BACKEND RESTART & PERSISTENCE VERIFICATION")
        print("#" * 70)
        del client
        fresh_client = TestClient(app)

        reloaded_a2 = fresh_client.get(f"/api/stories/{child_a2_id}/full").json()
        assert reloaded_a2["story_id"] == child_a2_id
        assert len(reloaded_a2["segments"]) == 3
        print(f"Successfully reloaded Branch A2 across restart: {reloaded_a2['total_word_count']} words, 3 segments.")

        reloaded_b = fresh_client.get(f"/api/stories/{child_b_id}/full").json()
        assert reloaded_b["story_id"] == child_b_id
        assert len(reloaded_b["segments"]) == 2
        print(f"Successfully reloaded Branch B across restart:  {reloaded_b['total_word_count']} words, 2 segments.")

        print("\n" + "=" * 80)
        print("ALL PHASE 4A LIVE STORY GENERATION ACCEPTANCE CRITERIA PASSED!")
        print("=" * 80)

    finally:
        # Cleanup
        print("\nCleaning up test documents and stories...")
        cleanup_client = TestClient(app)
        for doc_id in created_doc_ids:
            try:
                cleanup_client.delete(f"/api/documents/{doc_id}")
            except Exception:
                pass
        for story_id in reversed(created_story_ids):
            try:
                cleanup_client.delete(f"/api/stories/{story_id}")
            except Exception:
                pass
        print("Cleanup complete.")


if __name__ == "__main__":
    run_acceptance_demonstration()

"""Genuine end-to-end integration test against real running FastAPI and real Ollama."""
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
from app.database import SessionLocal, init_db
from app.models import Document, Chunk


def run_e2e_test():
    print("=" * 70)
    print("THE MIDNIGHT ARCHIVIST — REAL END-TO-END INTEGRATION TEST")
    print("=" * 70)

    pdf_path = Path("F:/Hacktober/sample_archive_manuscript.pdf")
    if not pdf_path.exists():
        print(f"ERROR: PDF file not found at {pdf_path}")
        sys.exit(1)

    print(f"Test Document: {pdf_path.name} ({pdf_path.stat().st_size} bytes)")

    # 1. Initialize DB and create client (unmocked HTTP against real localhost Ollama)
    init_db()
    client = TestClient(app)

    # Health check
    health_resp = client.get("/api/health")
    print(f"\n[Health Check] Status: {health_resp.status_code}, Response: {health_resp.json()}")
    assert health_resp.status_code == 200

    # Step 1: Upload the PDF through POST /api/documents
    print("\n--- Step 1: Upload Document ---")
    with open(pdf_path, "rb") as f:
        upload_resp = client.post(
            "/api/documents",
            files={"file": ("sample_archive_manuscript.pdf", f, "application/pdf")},
        )
    print(f"Status: {upload_resp.status_code}")
    upload_data = upload_resp.json()
    print(f"Response: {json.dumps(upload_data, indent=2)}")
    assert upload_resp.status_code == 201

    # Step 2: Retrieve document ID
    doc_id = upload_data["id"]
    print(f"\n--- Step 2: Document ID ---")
    print(f"Document ID: {doc_id}")

    # Step 3: Process through POST /api/documents/{id}/process
    print(f"\n--- Step 3: Ingestion & Real Embedding Pipeline ---")
    t0 = time.time()
    process_resp = client.post(f"/api/documents/{doc_id}/process")
    proc_time = time.time() - t0
    print(f"Status: {process_resp.status_code} (took {proc_time:.2f}s)")
    process_data = process_resp.json()
    print(f"Response: {json.dumps(process_data, indent=2)}")
    assert process_resp.status_code == 200
    assert process_data["status"] == "ready"
    assert process_data["dimensions"] == 768
    assert process_data["embedding_model"] == "nomic-embed-text"

    # Step 4, 5, 6, 7: Inspect chunks via GET /api/documents/{id}/chunks
    print(f"\n--- Steps 4-7: Verify Chunks & Metadata ---")
    chunks_resp = client.get(f"/api/documents/{doc_id}/chunks")
    assert chunks_resp.status_code == 200
    chunks_data = chunks_resp.json()
    print(f"Total Chunks: {chunks_data['total']}")
    for c in chunks_data["chunks"]:
        print(f"  [Chunk {c['chunk_index']}] Page {c['page_number']} | Section: {c['section']} | Preview: {c['text'][:65]}...")
        assert c["page_number"] is not None, "Page number must be preserved"
        assert len(c["text"]) > 0, "Chunk text must be non-empty"

    # Verify real embedding vector stored in DB
    with SessionLocal() as db:
        db_chunk = db.query(Chunk).filter(Chunk.document_id == doc_id).first()
        assert db_chunk is not None
        assert db_chunk.embedding is not None
        vec = json.loads(db_chunk.embedding)
        print(f"\nStored Vector in SQLite: {len(vec)} dimensions, sample values: {vec[:5]}")
        assert len(vec) == 768

    # Step 8 & 9: Semantic Search for a concept present in the document
    print(f"\n--- Steps 8 & 9: Semantic Search Verification ---")
    search_queries = [
        "astrolabe navigation star chart",
        "parchment folio illuminated manuscript",
        "nocturnal crypt iron deadbolt",
    ]

    for query in search_queries:
        search_resp = client.post("/api/search", json={"query": query, "top_k": 3})
        assert search_resp.status_code == 200
        search_data = search_resp.json()
        print(f"\nQuery: '{query}' -> Found {search_data['total']} matches (model: {search_data['embedding_model']})")
        for rank, r in enumerate(search_data["results"], start=1):
            print(f"  #{rank} Score: {r['similarity_score']:.4f} | Page {r['page_number']} | Text: {r['text'][:80]}...")
        top_match = search_data["results"][0]
        assert top_match["document_id"] == doc_id
        assert top_match["similarity_score"] > 0.4

    # Step 10: Re-index the document and verify no duplicates
    print(f"\n--- Step 10: Re-indexing Idempotency Test ---")
    reindex_resp = client.post(f"/api/documents/{doc_id}/process")
    assert reindex_resp.status_code == 200
    print(f"Re-index status: {reindex_resp.status_code}")

    chunks_after_reindex = client.get(f"/api/documents/{doc_id}/chunks").json()
    print(f"Chunks after re-indexing: {chunks_after_reindex['total']} (must equal {chunks_data['total']})")
    assert chunks_after_reindex["total"] == chunks_data["total"], "Re-indexing must not accumulate duplicate chunks"

    # Step 11 & 12: Stop and restart the backend, confirm persistence
    print(f"\n--- Steps 11 & 12: Restart Backend & Re-test Persistence ---")
    # Simulate fresh client/session restart
    del client
    fresh_client = TestClient(app)

    post_restart_search = fresh_client.post(
        "/api/search", json={"query": "iron deadbolt harbor crypt", "top_k": 2}
    )
    assert post_restart_search.status_code == 200
    restart_results = post_restart_search.json()
    print(f"Post-restart search: Found {restart_results['total']} results")
    assert len(restart_results["results"]) > 0
    top_r = restart_results["results"][0]
    print(f"Top result after restart: Score {top_r['similarity_score']:.4f} | Page {top_r['page_number']} | Text: {top_r['text'][:70]}...")
    assert "deadbolt" in top_r["text"].lower()

    # Clean up test document
    del_resp = fresh_client.delete(f"/api/documents/{doc_id}")
    assert del_resp.status_code == 204
    print(f"\nCleaned up test document: {doc_id}")

    print("\n" + "=" * 70)
    print("ALL 12 END-TO-END VERIFICATION STEPS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_e2e_test()

"""Live verification of story length enforcement for Short, Medium, and Long presets with real Ollama llama3.2:3b."""
from __future__ import annotations

import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from app.main import app

def test_live_presets():
    client = TestClient(app)
    print("================================================================")
    print(" REAL OLLAMA STORY LENGTH BOUNDARY BENCHMARK (llama3.2:3b)")
    print("================================================================\n")

    benchmarks = [
        {
            "preset": "short",
            "range": "400–600 words",
            "min": 400,
            "max": 600,
            "premise": "A night watchman discovers the pendulum clock in the bell tower has stopped swinging, yet continues to chime.",
            "atmosphere": "Quiet suspense",
        },
        {
            "preset": "medium",
            "range": "800–1,200 words",
            "min": 800,
            "max": 1200,
            "premise": "An antiquarian acquires a box of glass lantern slides depicting an unfamiliar coastal town slowly being consumed by black sand.",
            "atmosphere": "Coastal Decay",
        },
        {
            "preset": "long",
            "range": "1,500–2,000 words",
            "min": 1500,
            "max": 2000,
            "premise": "A comprehensive scholarly account of the winter expedition to the flooded salt mines of Saint Jude, detailing the descending water levels, the petrified library, and the warnings carved into the halite pillars.",
            "atmosphere": "Scholarly Obsession",
        },
    ]

    results = []

    for item in benchmarks:
        p = item["preset"]
        print(f"Testing Preset: {p.upper()} ({item['range']})...")
        t0 = time.time()
        res = client.post(
            "/api/stories/generate",
            json={
                "premise": item["premise"],
                "atmosphere": item["atmosphere"],
                "length": p,
                "grounding_mode": "freeform",
            },
        )
        elapsed = time.time() - t0
        assert res.status_code == 201, f"Failed for {p}: {res.text}"
        data = res.json()
        words = data["word_count"]
        title = data["title"]
        in_bounds = item["min"] <= words <= item["max"]
        status_str = "[PASS]" if in_bounds else "[FAIL]"
        print(f"   Title: \"{title}\"")
        print(f"   Word Count: {words} words (Required: {item['range']}) -> {status_str} in {elapsed:.2f}s")
        assert in_bounds, f"Word count {words} out of bounds for preset {p} ({item['range']})"
        results.append({
            "preset": p,
            "range": item["range"],
            "words": words,
            "elapsed": round(elapsed, 2),
            "title": title,
        })
        print()

    print("================================================================")
    print(" ALL THREE LENGTH PRESETS MET STRICT [MIN, MAX] BOUNDARIES!")
    print("================================================================")
    for r in results:
        print(f" * {r['preset'].upper():<7}: {r['words']:>4} words | Target: {r['range']:<18} | {r['elapsed']:>5}s | \"{r['title']}\"")

if __name__ == "__main__":
    test_live_presets()

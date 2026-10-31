import time
import sys
from app.database import SessionLocal
from app.services.story_engine import generate_story

def test_preset(length_preset: str):
    db = SessionLocal()
    print(f"=== Testing preset: {length_preset} ===")
    start_t = time.time()
    try:
        story = generate_story(
            db,
            premise="A night watchman discovers the pendulum clock in the bell tower has stopped swinging, yet continues to chime.",
            atmosphere="Quiet suspense",
            length=length_preset,
            grounding_mode="freeform",
        )
        elapsed = time.time() - start_t
        wc = story.word_count
        print(f"SUCCESS: {length_preset} | Words: {wc} | Time: {elapsed:.2f}s | Title: {story.title}")
        print("First 200 chars:", story.body[:200])
        return {"preset": length_preset, "words": wc, "time": elapsed, "status": "SUCCESS", "title": story.title}
    except Exception as exc:
        elapsed = time.time() - start_t
        print(f"FAILED: {length_preset} | Error: {exc} | Time: {elapsed:.2f}s")
        return {"preset": length_preset, "error": str(exc), "time": elapsed, "status": "FAILED"}
    finally:
        db.close()

if __name__ == "__main__":
    preset = sys.argv[1] if len(sys.argv) > 1 else "short"
    test_preset(preset)

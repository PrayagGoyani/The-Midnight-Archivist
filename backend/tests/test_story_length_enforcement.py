"""Comprehensive test suite for strict story length boundaries (minimum and maximum).
Tests short, medium, and long presets, bounded expansion, bounded compression, and failure cases.
"""
from __future__ import annotations

import json
import pytest

from app.models import Document, Story
from app.services.prompt_builder import (
    LENGTH_SPECS,
    build_compression_prompt,
    build_expansion_prompt,
)
from app.services.retrieval import SearchResult
from app.services.story_engine import (
    ExcessiveStoryLengthError,
    InsufficientStoryLengthError,
    StoryLengthOutOfBoundsError,
    continue_story,
    generate_story,
)


class MockGenClient:
    """Mock Ollama generation client that returns predetermined responses in order."""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.call_count = 0
        self.recorded_messages: list[list[dict[str, str]]] = []
        self.default_model = "mock-llama3.2:3b"

    def generate_chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        format_json: bool = True,
    ) -> str:
        self.recorded_messages.append(messages)
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        self.call_count += 1
        return self.responses[-1]


def make_prose(word_count: int, seed: str = "The archivist turned the bronze key in the iron lock") -> str:
    """Generate prose with exactly word_count words."""
    words = seed.split()
    repeated = (words * ((word_count // len(words)) + 2))[:word_count]
    return " ".join(repeated)


def make_story_json(title: str, word_count: int, choices: list[dict] | None = None) -> str:
    """Build a valid JSON story string with exact word count."""
    if choices is None:
        choices = [
            {"id": "choice_1", "label": "Inspect the stone", "description": "Examine the cold surface."},
            {"id": "choice_2", "label": "Retreat to the stairs", "description": "Climb away from the dark."},
        ]
    return json.dumps({
        "title": title,
        "content": make_prose(word_count),
        "branch_choices": choices,
    })


# ── Short Preset Tests (400–600 words) ────────────────────────────────

def test_short_below_minimum_fails_after_expansion(db_session):
    """Short preset below 400 words fails with InsufficientStoryLengthError if expansion cannot reach 400."""
    under_draft = make_story_json("Short Under", 250)
    failed_expansion = make_story_json("Short Under Expanded", 290)

    gen_client = MockGenClient([under_draft, failed_expansion])

    with pytest.raises(InsufficientStoryLengthError) as exc_info:
        generate_story(
            db_session,
            premise="Under-length test",
            length="short",
            generation_client=gen_client,
        )

    assert "below the minimum required (400 words) for preset 'short'" in str(exc_info.value)
    assert exc_info.value.actual_words == 290
    assert exc_info.value.min_words == 400
    assert db_session.query(Story).count() == 0


def test_short_above_maximum_fails_after_compression(db_session):
    """Short preset above 600 words fails with ExcessiveStoryLengthError if compression cannot reduce to <= 600."""
    over_draft = make_story_json("Short Over", 750)
    failed_compression = make_story_json("Short Over Compressed", 680)

    gen_client = MockGenClient([over_draft, failed_compression])

    with pytest.raises(ExcessiveStoryLengthError) as exc_info:
        generate_story(
            db_session,
            premise="Over-length test",
            length="short",
            generation_client=gen_client,
        )

    assert "exceeds the maximum allowed (600 words) for preset 'short'" in str(exc_info.value)
    assert exc_info.value.actual_words == 680
    assert exc_info.value.max_words == 600
    assert db_session.query(Story).count() == 0


def test_short_successful_bounded_expansion(db_session):
    """Short draft starting at 280 words successfully expands to 490 words."""
    under_draft = make_story_json("Short Expanding", 280)
    successful_expansion = make_story_json("Short Expanding", 490)

    gen_client = MockGenClient([under_draft, successful_expansion])

    story = generate_story(
        db_session,
        premise="Expansion test",
        length="short",
        generation_client=gen_client,
    )

    assert gen_client.call_count == 2
    assert story.word_count == 490
    assert 400 <= story.word_count <= 600
    assert db_session.query(Story).count() == 1


def test_short_successful_bounded_compression(db_session):
    """Short draft starting at 800 words successfully compresses to 520 words."""
    over_draft = make_story_json("Short Compressing", 800)
    successful_compression = make_story_json("Short Compressing", 520)

    gen_client = MockGenClient([over_draft, successful_compression])

    story = generate_story(
        db_session,
        premise="Compression test",
        length="short",
        generation_client=gen_client,
    )

    assert gen_client.call_count == 2
    assert story.word_count == 520
    assert 400 <= story.word_count <= 600
    assert db_session.query(Story).count() == 1


# ── Medium Preset Tests (800–1,200 words) ─────────────────────────────

def test_medium_below_minimum_fails_after_expansion(db_session):
    """Medium preset below 800 words fails if expansion stays below 800."""
    under_draft = make_story_json("Med Under", 500)
    failed_expansion = make_story_json("Med Under", 650)

    gen_client = MockGenClient([under_draft, failed_expansion])

    with pytest.raises(InsufficientStoryLengthError) as exc_info:
        generate_story(
            db_session,
            premise="Medium under test",
            length="medium",
            generation_client=gen_client,
        )

    assert "below the minimum required (800 words) for preset 'medium'" in str(exc_info.value)
    assert db_session.query(Story).count() == 0


def test_medium_above_maximum_fails_after_compression(db_session):
    """Medium preset above 1,200 words fails if compression stays above 1,200."""
    over_draft = make_story_json("Med Over", 1450)
    failed_compression = make_story_json("Med Over", 1280)

    gen_client = MockGenClient([over_draft, failed_compression])

    with pytest.raises(ExcessiveStoryLengthError) as exc_info:
        generate_story(
            db_session,
            premise="Medium over test",
            length="medium",
            generation_client=gen_client,
        )

    assert "exceeds the maximum allowed (1200 words) for preset 'medium'" in str(exc_info.value)
    assert db_session.query(Story).count() == 0


def test_medium_successful_bounded_compression(db_session):
    """Medium draft starting at 1,400 words successfully compresses to 1,020 words."""
    over_draft = make_story_json("Med Compressing", 1400)
    successful_compression = make_story_json("Med Compressing", 1020)

    gen_client = MockGenClient([over_draft, successful_compression])

    story = generate_story(
        db_session,
        premise="Medium compress test",
        length="medium",
        generation_client=gen_client,
    )

    assert gen_client.call_count == 2
    assert story.word_count == 1020
    assert 800 <= story.word_count <= 1200


def test_medium_successful_bounded_expansion(db_session):
    """Medium draft starting at 620 words successfully expands to 950 words."""
    under_draft = make_story_json("Med Expanding", 620)
    successful_expansion = make_story_json("Med Expanding", 950)

    gen_client = MockGenClient([under_draft, successful_expansion])

    story = generate_story(
        db_session,
        premise="Medium expand test",
        length="medium",
        generation_client=gen_client,
    )

    assert gen_client.call_count == 2
    assert story.word_count == 950
    assert 800 <= story.word_count <= 1200


# ── Long Preset Tests (1,500–2,000 words) ─────────────────────────────

def make_outline_json(title: str = "Long Tale") -> str:
    return json.dumps({
        "title": title,
        "sections": [
            {"act": "Act I", "summary": "Inciting Incident"},
            {"act": "Act II", "summary": "Complication"},
            {"act": "Act III", "summary": "Climax"},
        ],
    })


def test_long_below_minimum_fails_after_expansion(db_session):
    """Long preset below 1,500 words fails if expansion stays below 1,500."""
    outline = make_outline_json("Long Under")
    sec1 = make_story_json("Long Under", 370)
    sec2 = make_story_json("Long Under", 370)
    sec3 = make_story_json("Long Under", 370)
    failed_expansion = make_story_json("Long Under", 1350)

    gen_client = MockGenClient([outline, sec1, sec2, sec3, failed_expansion])

    with pytest.raises(InsufficientStoryLengthError) as exc_info:
        generate_story(
            db_session,
            premise="Long under test",
            length="long",
            generation_client=gen_client,
        )

    assert "below the minimum required (1500 words) for preset 'long'" in str(exc_info.value)
    assert db_session.query(Story).count() == 0
    assert gen_client.call_count == 5


def test_long_above_maximum_fails_after_compression(db_session):
    """Long preset above 2,000 words fails if compression stays above 2,000."""
    outline = make_outline_json("Long Over")
    sec1 = make_story_json("Long Over", 750)
    sec2 = make_story_json("Long Over", 750)
    sec3 = make_story_json("Long Over", 750)
    failed_compression = make_story_json("Long Over", 2150)

    gen_client = MockGenClient([outline, sec1, sec2, sec3, failed_compression])

    with pytest.raises(ExcessiveStoryLengthError) as exc_info:
        generate_story(
            db_session,
            premise="Long over test",
            length="long",
            generation_client=gen_client,
        )

    assert "exceeds the maximum allowed (2000 words) for preset 'long'" in str(exc_info.value)
    assert db_session.query(Story).count() == 0
    assert gen_client.call_count == 5


def test_long_successful_bounded_expansion(db_session):
    """Long draft starting at 1,200 words (3x400) successfully expands to 1,720 words."""
    outline = make_outline_json("Long Expanding")
    sec1 = make_story_json("Long Expanding", 400)
    sec2 = make_story_json("Long Expanding", 400)
    sec3 = make_story_json("Long Expanding", 400)
    successful_expansion = make_story_json("Long Expanding", 1720)

    gen_client = MockGenClient([outline, sec1, sec2, sec3, successful_expansion])

    story = generate_story(
        db_session,
        premise="Long expand test",
        length="long",
        generation_client=gen_client,
    )

    assert gen_client.call_count == 5
    assert story.word_count == 1720
    assert 1500 <= story.word_count <= 2000


def test_long_successful_bounded_compression(db_session):
    """Long draft starting at 2,350 words (3x~783) successfully compresses to 1,850 words."""
    outline = make_outline_json("Long Compressing")
    sec1 = make_story_json("Long Compressing", 780)
    sec2 = make_story_json("Long Compressing", 780)
    sec3 = make_story_json("Long Compressing", 790)
    successful_compression = make_story_json("Long Compressing", 1850)

    gen_client = MockGenClient([outline, sec1, sec2, sec3, successful_compression])

    story = generate_story(
        db_session,
        premise="Long compress test",
        length="long",
        generation_client=gen_client,
    )

    assert gen_client.call_count == 5
    assert story.word_count == 1850
    assert 1500 <= story.word_count <= 2000


# ── Source Reference & Branch Preservation During Compression ─────────

def test_source_reference_and_branch_preservation_during_compression(db_session):
    """During compression of an archive-grounded story, sources and choices are preserved."""
    # Seed ready document & chunk
    doc = Document(
        title="Tide Registry",
        original_filename="tide.txt",
        stored_filename="tide_uuid.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=200,
        status="ready",
    )
    db_session.add(doc)
    db_session.commit()

    query_vec = [1.0, 0.0]
    dummy_source = SearchResult(
        chunk_id="chk_1",
        document_id=doc.id,
        document_title=doc.title,
        text="The high tide engulfed the third marker at sunset.",
        page_number=1,
        section="Observations",
        similarity_score=0.88,
    )

    initial_choices = [
        {"id": "choice_a", "label": "Wait for twilight", "description": "Watch the water rise."},
        {"id": "choice_b", "label": "Signal the mainland", "description": "Light the distress pyre."},
    ]
    over_draft = make_story_json("The Tide Call", 750, choices=initial_choices)
    # Compressed output omits choices; verify engine preserves initial_choices
    compressed_without_choices = json.dumps({
        "title": "The Tide Call",
        "content": make_prose(500),
        "branch_choices": [],
    })

    gen_client = MockGenClient([over_draft, compressed_without_choices])

    def mock_embed(texts, **kwargs):
        from app.services.ollama_client import EmbeddingResult
        return EmbeddingResult(embeddings=[query_vec for _ in texts], model="nomic-embed-text", dimensions=2)

    def mock_search_chunks(**kwargs):
        return [dummy_source]

    import app.services.story_engine as se
    monkeypatch_search = pytest.MonkeyPatch()
    monkeypatch_search.setattr(se, "search_chunks", mock_search_chunks)

    story = generate_story(
        db_session,
        premise="Waiting by the high tide marker.",
        grounding_mode="archive",
        document_ids=[doc.id],
        length="short",
        generation_client=gen_client,
        embed_fn=mock_embed,
    )

    monkeypatch_search.undo()

    assert gen_client.call_count == 2
    assert story.word_count == 500
    # Verify archival references preserved
    refs = json.loads(story.source_references)
    assert len(refs) == 1
    assert refs[0]["document_title"] == "Tide Registry"
    assert refs[0]["similarity_score"] == 0.88
    # Verify branch choices preserved
    choices = json.loads(story.branch_choices)
    assert len(choices) == 2
    assert choices[0]["label"] == "Wait for twilight"
    assert choices[1]["label"] == "Signal the mainland"


# ── Continuation Length Enforcement Tests ─────────────────────────────

def test_continuation_length_boundaries_enforced(db_session):
    """Continuation segment exceeding maximum triggers bounded compression."""
    root_json = make_story_json("Root Chapter", 450)
    over_continuation = make_story_json("Over Continuation", 780)
    compressed_continuation = make_story_json("Compressed Continuation", 480)

    gen_client = MockGenClient([root_json, over_continuation, compressed_continuation])

    root = generate_story(
        db_session,
        premise="Beginning of the descent.",
        length="short",
        generation_client=gen_client,
    )

    cont = continue_story(
        root.id,
        choice_id="choice_1",
        db=db_session,
        generation_client=gen_client,
    )

    assert gen_client.call_count == 3  # root + over_cont + compressed_cont
    assert cont.word_count == 480
    assert 400 <= cont.word_count <= 600
    assert cont.parent_story_id == root.id

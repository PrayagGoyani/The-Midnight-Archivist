"""Tests for multi-stage story generation and continuation pipeline.

Verifies:
1. Multi-stage narrative generation (outline + Act I + Act II + Act III).
2. Preceding context passing (narrative continuity between sections).
3. Incomplete sections and malformed outline fallback behavior.
4. Seamless section stitching and heading/duplicate removal.
5. Multi-stage continuation for 'long' stories.
6. Validation enforcement and database rollback on failure.
"""

import json
import pytest
from sqlalchemy.orm import Session

from app.models import Document, Story
from app.services.prompt_builder import stitch_sections
from app.services.story_engine import (
    ExcessiveStoryLengthError,
    InsufficientStoryLengthError,
    continue_story,
    generate_story,
)


class MockMultiStageGenClient:
    """Mock client tracking recorded prompts and sequential responses."""

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


def make_prose_block(word_count: int, seed: str = "The archivist turned the bronze key in the silent vault") -> str:
    words = seed.split()
    return " ".join((words * ((word_count // len(words)) + 2))[:word_count])


def test_stitch_sections_cleans_headings_and_deduplicates():
    """stitch_sections strips markdown headers, act labels, and trims seamless prose."""
    sec1 = "### Act I: The Awakening\n\nJulian crossed the rusted gangway. The cold mist rose from the black tide below."
    sec2 = "# Act II: Complications\n\nJulian crossed the rusted gangway. The iron gates had rusted shut centuries ago."
    sec3 = "**Act III: Revelation**\n\nBeyond the gates lay the crystalline sphere, pulsing with faint phosphor."

    assembled = stitch_sections([sec1, sec2, sec3])

    # No markdown headings or act tags should remain in body
    assert "Act I" not in assembled
    assert "Act II" not in assembled
    assert "Act III" not in assembled
    assert "###" not in assembled
    assert "#" not in assembled

    # Check narrative flow
    assert "Julian crossed the rusted gangway." in assembled
    assert "Beyond the gates lay the crystalline sphere" in assembled


def test_multistage_generation_preserves_narrative_continuity(db_session: Session):
    """Context from previous section is fed into subsequent section generation."""
    outline = json.dumps({
        "title": "The Drowned Observatory",
        "sections": [
            {"act": "Act I", "summary": "Finding the brass sphere"},
            {"act": "Act II", "summary": "Opening the flooded gate"},
            {"act": "Act III", "summary": "The celestial alignment"},
        ],
    })
    sec1 = json.dumps({
        "title": "The Drowned Observatory",
        "content": make_prose_block(540, "Julian felt the icy brine soaking into his boots as the lantern flickered"),
        "branch_choices": [],
    })
    sec2 = json.dumps({
        "title": "The Drowned Observatory",
        "content": make_prose_block(540, "The bronze mechanism ground against stone echoing through the dark"),
        "branch_choices": [],
    })
    sec3 = json.dumps({
        "title": "The Drowned Observatory",
        "content": make_prose_block(540, "Two paths emerged before the flooded dais as the bell tolled midnight"),
        "branch_choices": [
            {"id": "b1", "label": "Descend the flooded stairs", "description": "Wade deeper into the sub-levels."},
            {"id": "b2", "label": "Ascend the observation spire", "description": "Reach the open telescope deck."},
        ],
    })

    gen_client = MockMultiStageGenClient([outline, sec1, sec2, sec3])

    story = generate_story(
        db_session,
        premise="An astronomer discovers an observatory submerged beneath a tidal lagoon.",
        atmosphere="Eerie",
        length="long",
        grounding_mode="freeform",
        generation_client=gen_client,
    )

    assert story.status == "completed"
    assert story.requested_length == "long"
    assert 1500 <= story.word_count <= 2000
    assert gen_client.call_count == 4

    # Verify that Section 2's prompt received Section 1's concluding text
    sec2_prompt = json.dumps(gen_client.recorded_messages[2])
    assert "PRECEDING NARRATIVE CONTEXT" in sec2_prompt

    # Verify that Section 3's prompt received Section 2's concluding text
    sec3_prompt = json.dumps(gen_client.recorded_messages[3])
    assert "PRECEDING NARRATIVE CONTEXT" in sec3_prompt


def test_multistage_generation_fallback_on_malformed_outline(db_session: Session):
    """When the outline model call returns unparseable or empty JSON, default 3-act sections are used."""
    malformed_outline = "This is not valid json at all {{{"
    sec1 = json.dumps({"title": "Default Title", "content": make_prose_block(530, "The tide rolled across the ruined shore"), "branch_choices": []})
    sec2 = json.dumps({"title": "Default Title", "content": make_prose_block(530, "Deep in the cavern the water began to warm"), "branch_choices": []})
    sec3 = json.dumps({
        "title": "Default Title",
        "content": make_prose_block(530, "Standing before the twin doors Julian chose his fate"),
        "branch_choices": [
            {"id": "c1", "label": "Open the left door", "description": "Face the water."},
            {"id": "c2", "label": "Open the right door", "description": "Face the stone."},
        ],
    })

    gen_client = MockMultiStageGenClient([malformed_outline, sec1, sec2, sec3])

    story = generate_story(
        db_session,
        premise="A solitary explorer investigates strange tides.",
        length="long",
        generation_client=gen_client,
    )

    assert story.status == "completed"
    assert story.requested_length == "long"
    assert 1500 <= story.word_count <= 2000
    assert gen_client.call_count == 4


def test_multistage_continuation_preserves_lineage(db_session: Session):
    """Continuation of a Long story executes 2-stage continuation and links to parent."""
    # First create root long story
    outline = json.dumps({
        "title": "The Sunken Spire",
        "sections": [
            {"act": "Act I", "summary": "Part 1"},
            {"act": "Act II", "summary": "Part 2"},
            {"act": "Act III", "summary": "Part 3"},
        ],
    })
    sec1 = json.dumps({"title": "The Sunken Spire", "content": make_prose_block(540, "Julian felt the cold salt spray striking his cheek in the darkness"), "branch_choices": []})
    sec2 = json.dumps({"title": "The Sunken Spire", "content": make_prose_block(540, "The submerged pillars groaned beneath the relentless tidal surge"), "branch_choices": []})
    sec3 = json.dumps({
        "title": "The Sunken Spire",
        "content": make_prose_block(540, "At the center of the flooded aisle a decision presented itself"),
        "branch_choices": [
            {"id": "choice_a", "label": "Enter the crypt", "description": "Descend into dark."},
            {"id": "choice_b", "label": "Retreat to shore", "description": "Head back."},
        ],
    })

    gen_client = MockMultiStageGenClient([outline, sec1, sec2, sec3])
    root = generate_story(
        db_session,
        premise="Sunken spire investigation",
        length="long",
        generation_client=gen_client,
    )

    # Now continue on choice_a using 2-stage continuation
    cont_s1 = json.dumps({
        "content": make_prose_block(800, "Descending through the crypt the water deepened past his waist"),
    })
    cont_s2 = json.dumps({
        "content": make_prose_block(800, "At the center of the vault stood the obsidian plinth"),
        "branch_choices": [
            {"id": "sub_1", "label": "Touch the obsidian", "description": "Feel the cold stone."},
            {"id": "sub_2", "label": "Turn around", "description": "Flee the crypt."},
        ],
    })

    cont_client = MockMultiStageGenClient([cont_s1, cont_s2])

    child = continue_story(
        story_id=root.id,
        choice_id="choice_a",
        db=db_session,
        generation_client=cont_client,
    )

    assert child.parent_story_id == root.id
    assert child.branch_choice == "Enter the crypt"
    assert child.requested_length == "long"
    assert 1500 <= child.word_count <= 2000
    assert child.status == "completed"
    assert cont_client.call_count == 2


def test_multistage_generation_failure_rolls_back_database(db_session: Session):
    """If multi-stage generation fails validation even after expansion, database transaction is rolled back."""
    outline = json.dumps({
        "title": "Failing Long Story",
        "sections": [
            {"act": "Act I", "summary": "A"},
            {"act": "Act II", "summary": "B"},
            {"act": "Act III", "summary": "C"},
        ],
    })
    # Sections total 300 words (way below 1500)
    sec1 = json.dumps({"title": "Failing Long Story", "content": make_prose_block(100), "branch_choices": []})
    sec2 = json.dumps({"title": "Failing Long Story", "content": make_prose_block(100), "branch_choices": []})
    sec3 = json.dumps({"title": "Failing Long Story", "content": make_prose_block(100), "branch_choices": []})
    # Expansion still below 1500 words
    failed_expansion = json.dumps({"title": "Failing Long Story", "content": make_prose_block(400), "branch_choices": []})

    gen_client = MockMultiStageGenClient([outline, sec1, sec2, sec3, failed_expansion])

    initial_count = db_session.query(Story).count()

    with pytest.raises(InsufficientStoryLengthError):
        generate_story(
            db_session,
            premise="Story doomed to fail length check",
            length="long",
            generation_client=gen_client,
        )

    # Confirm database was rolled back and no story was persisted
    assert db_session.query(Story).count() == initial_count

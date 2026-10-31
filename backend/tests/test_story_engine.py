"""Unit and integration tests for the story engine and branching narrative system."""
from __future__ import annotations

import json
import pytest

from app.models import Chunk, Document, Story
from app.services.ollama_client import EmbeddingResult
from app.services.ollama_generation import OllamaGenerationClient
from app.services.prompt_builder import LENGTH_SPECS
from app.services.story_engine import (
    InsufficientArchiveContextError,
    InsufficientStoryLengthError,
    InvalidBranchChoiceError,
    StoryEngineError,
    StoryNotFoundError,
    StoryValidationError,
    continue_story,
    generate_story,
    get_full_narrative,
    get_story_branches,
)


VALID_SHORT_PROSE = (
    "The clock struck thirteen in the silent conservatory, an impossible reverberation that shook the leaded "
    "glass panes until the air tasted of copper and ancient dust. Julian stood beside the overgrown belladonna, "
    "his notebook pressed against his ribs, watching the shadows fold inward like wet parchment. The house had "
    "been shuttered since November, yet warmth radiated from beneath the cold slate flagstones, as though an immense "
    "furnace labored below the cellars. He uncapped his fountain pen, but the ink had congealed into thick dark "
    "crystals upon the nib. Outside, across the salt marsh, the evening fog rolled inland, carrying the faint scent "
    "of burning cedar and low tide.\n\n"
    "He adjusted his brass spectacles and approached the pedestal where the iron astrolabe rested beneath a bell jar. "
    "Every surface bore the faint residue of sea salt, though the shoreline lay three miles to the south. In the ledger "
    "kept by his predecessor, Master Corvus, the final entry recorded only a series of astronomical bearings and a single "
    "word repeated three times: listen, listen, listen. Now, in the hollow interval following the thirteenth chime, a "
    "subterranean hum vibrated through the iron floorplates, matching the rhythm of his own pulse.\n\n"
    "Julian lifted the heavy glass cloche. The air imprisoned beneath it smelled of brine, dried thyme, and ozone. On "
    "the astrolabe rete, the star pointers had been bent by deliberate force, aligned toward a constellation no modern "
    "almanac recognized. Beside the instrument lay a key fashioned from dull gray metal that felt extraordinarily cold to "
    "the touch, far colder than the unheated air of the conservatory. When he brought his lantern near, the gray surface "
    "absorbed the candlelight rather than reflecting it, casting an oval pool of shadow over his gloved fingertips.\n\n"
    "Somewhere beneath the floor, water began to drip with relentless cadence. It was not the casual runoff of rain, "
    "but the measured drainage of an ancient sluice gate opening in the dark. Julian hesitated, feeling the weight of the "
    "decaying estate leaning into the heavy silence, demanding an irreversible decision before the sea fog reached the tall "
    "library windows. The stone walls seemed to breathe, expelling cold vapor that curled around his ankles like creeping water.\n\n"
    "He pocketed the meteoric iron key and trimmed the lantern wick. Two pathways lay open before him: the spiral stone "
    "stairs winding steeply downward into the flooded archival vault, or the narrow exterior gallery overlooking the black "
    "waters of the restless bay. The floor shuddered once more, and Julian stepped forward into the cold damp air with deliberate resolve."
)

VALID_CONT_PROSE = (
    "Julian guided his trembling hand along the damp masonry of the spiral descent, feeling the salt crust crumble "
    "beneath his wool mittens. The lantern light swung in erratic arcs, catching patches of dark lichen that glistened "
    "like wet oil upon the curved walls. Every twelve paces, an alcove had been carved into the living bedrock, each "
    "containing a row of lead canisters sealed with yellow wax. The labels had long since rotted into gray lint, yet "
    "the smell emanating from the seams was unmistakably that of sea water and burnt copper.\n\n"
    "At the seventeenth step, his boot broke through a submerged riser. Cold brine surged over his ankles, sharp enough "
    "to steal his breath. He held the lantern aloft, revealing that the lower four tiers of the archive had vanished "
    "beneath three feet of black tide. Floating upon the surface were loose sheets of rag paper, their iron gall ink "
    "softened into indigo clouds that drifted between floating pine crates and fractured book spines.\n\n"
    "Ahead, at the center of the flooded chamber, an octagonal reading desk remained marooned above the water like an island. "
    "Upon its slanted oak surface lay an open folio, its parchment leaves pinned against the draft by two heavy bronze calipers. "
    "As Julian waded toward it, the water pushing against his knees with the steady pressure of an ocean current, the astrolabe "
    "in his leather bag hummed again, vibrating against his hip.\n\n"
    "He reached the oak desk and leaned against its fluted columns to steady his footing. The text inscribed upon the calfskin "
    "folio was not Latin or Greek, but a cipher composed entirely of coastal soundings, lunar elevations, and tidal depths. In "
    "the left margin, inked in fresh red vermilion that had not yet dried, was his own name, spelled letter by letter alongside "
    "tonight date.\n\n"
    "A sudden surge rose against the heavy foundations, lifting the floating debris against the drowned bookshelves with a muffled "
    "groan. Julian gripped the folio with one hand while the other sought the rusted iron latch of the drainage mechanism submerged "
    "below the reading table. The water was climbing rapidly toward his chest, smelling of ancient silt and cold brine. He had only "
    "seconds to decide whether to unseal the drainage conduit and risk draining the entire archive into the ocean abyss, or salvage "
    "the damp manuscript and scramble back toward the lantern light on the upper staircase. The cold tide waited for no hesitation."
)

SAMPLE_STORY_JSON = json.dumps({
    "title": "The Glass Bell",
    "content": VALID_SHORT_PROSE,
    "branch_choices": [
        {"id": "choice_1", "label": "Examine the bell", "description": "Inspect the hairline crack along the rim."},
        {"id": "choice_2", "label": "Extinguish the lantern", "description": "Stand in complete darkness and listen."},
    ],
})

SAMPLE_CONTINUATION_JSON = json.dumps({
    "title": "The Resonance",
    "content": VALID_CONT_PROSE,
    "branch_choices": [
        {"id": "choice_3", "label": "Strike the tuning fork", "description": "Test the frequency against iron."},
        {"id": "choice_4", "label": "Retreat to the foyer", "description": "Barricade the glass doors."},
    ],
})


class MockGenClient(OllamaGenerationClient):
    def __init__(self, responses: list[str]):
        super().__init__(base_url="http://mock:11434", default_model="mock-model")
        self.responses = list(responses)
        self.call_count = 0

    def generate_chat_completion(self, messages, **kwargs) -> str:
        self.call_count += 1
        if self.responses:
            return self.responses.pop(0)
        return SAMPLE_STORY_JSON


def make_mock_embed_fn(vector: list[float]):
    def _mock_embed(texts, **kwargs):
        return EmbeddingResult(
            embeddings=[vector for _ in texts],
            model="nomic-embed-text",
            dimensions=len(vector),
        )
    return _mock_embed


def test_generate_story_freeform_success(db_session):
    """Freeform story generation creates a completed root story node."""
    gen_client = MockGenClient([SAMPLE_STORY_JSON])
    story = generate_story(
        db_session,
        premise="A clocks strikes thirteen in an abandoned conservatory.",
        atmosphere="Uncanny",
        length="short",
        grounding_mode="freeform",
        generation_client=gen_client,
    )

    assert story.id is not None
    assert story.title == "The Glass Bell"
    assert story.status == "completed"
    assert story.parent_story_id is None
    assert story.branch_choice is None
    assert story.word_count == len(story.body.split())
    assert story.generation_model == "mock-model"

    choices = json.loads(story.branch_choices)
    assert len(choices) == 2
    assert choices[0]["id"] == "choice_1"


def test_generate_story_empty_premise(db_session):
    """Empty premise raises StoryValidationError."""
    gen_client = MockGenClient([SAMPLE_STORY_JSON])
    with pytest.raises(StoryValidationError, match="premise cannot be empty"):
        generate_story(
            db_session,
            premise="   ",
            atmosphere="Gothic",
            generation_client=gen_client,
        )


def test_generate_story_archive_grounded_success(db_session):
    """Archive-grounded story incorporates retrieved passages and stores source references."""
    unit_vec = [1.0, 0.0, 0.0]
    doc = Document(
        title="Botanical Anomalies",
        original_filename="botany.pdf",
        stored_filename="botany_uuid.pdf",
        file_extension=".pdf",
        content_type="application/pdf",
        file_size=1024,
        status="ready",
    )
    db_session.add(doc)
    db_session.commit()

    chunk = Chunk(
        document_id=doc.id,
        chunk_index=0,
        text="The bronze bell was preserved under glass to mute its subterranean resonance.",
        page_number=3,
        section="Appendix B",
        embedding=json.dumps(unit_vec),
        embedding_model="nomic-embed-text",
    )
    db_session.add(chunk)
    db_session.commit()

    gen_client = MockGenClient([SAMPLE_STORY_JSON])

    story = generate_story(
        db_session,
        premise="Finding the bronze bell under glass.",
        atmosphere="Gothic",
        length="short",
        grounding_mode="archive",
        document_ids=[doc.id],
        generation_client=gen_client,
        embed_fn=make_mock_embed_fn(unit_vec),
    )

    assert story.grounding_mode == "archive"
    sources = json.loads(story.source_references)
    assert len(sources) == 1
    assert sources[0]["document_title"] == "Botanical Anomalies"
    assert sources[0]["page_number"] == 3
    assert sources[0]["similarity_score"] > 0.9


def test_generate_story_archive_grounded_no_relevant_sources(db_session):
    """Archive search with zero matching passages raises InsufficientArchiveContextError."""
    # Chunk vector is orthogonal to query vector -> similarity 0.0 < 0.30
    chunk_vec = [0.0, 1.0, 0.0]
    query_vec = [1.0, 0.0, 0.0]

    doc = Document(
        title="Unrelated Register",
        original_filename="reg.txt",
        stored_filename="reg_uuid.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=500,
        status="ready",
    )
    db_session.add(doc)
    db_session.commit()

    chunk = Chunk(
        document_id=doc.id,
        chunk_index=0,
        text="Taxes recorded for the year 1842 in county cork.",
        embedding=json.dumps(chunk_vec),
        embedding_model="nomic-embed-text",
    )
    db_session.add(chunk)
    db_session.commit()

    gen_client = MockGenClient([SAMPLE_STORY_JSON])

    with pytest.raises(InsufficientArchiveContextError, match="No sufficiently relevant passages"):
        generate_story(
            db_session,
            premise="Searching for spectral voices.",
            grounding_mode="archive",
            document_ids=[doc.id],
            generation_client=gen_client,
            embed_fn=make_mock_embed_fn(query_vec),
        )

    # Ensure no story was committed
    assert db_session.query(Story).count() == 0


def test_generate_story_missing_or_unready_document(db_session):
    """Selecting a missing or unready document raises StoryEngineError."""
    gen_client = MockGenClient([SAMPLE_STORY_JSON])

    with pytest.raises(StoryEngineError, match="not found"):
        generate_story(
            db_session,
            premise="Test",
            grounding_mode="archive",
            document_ids=["missing_doc_id"],
            generation_client=gen_client,
            embed_fn=make_mock_embed_fn([1.0, 0.0]),
        )

    doc = Document(
        title="Pending Doc",
        original_filename="p.txt",
        stored_filename="p_uuid.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=100,
        status="processing",
    )
    db_session.add(doc)
    db_session.commit()

    with pytest.raises(StoryEngineError, match="is not ready for retrieval"):
        generate_story(
            db_session,
            premise="Test",
            grounding_mode="archive",
            document_ids=[doc.id],
            generation_client=gen_client,
            embed_fn=make_mock_embed_fn([1.0, 0.0]),
        )


def test_generate_story_malformed_json_repair_retry(db_session):
    """Malformed output triggers bounded repair retry and succeeds."""
    malformed = "Here is your story: {title: 'Broken', content: '...'}"
    gen_client = MockGenClient([malformed, SAMPLE_STORY_JSON])

    story = generate_story(
        db_session,
        premise="Repair test",
        generation_client=gen_client,
    )
    assert gen_client.call_count == 2
    assert story.title == "The Glass Bell"


def test_generate_story_unrepairable_malformed_json(db_session):
    """Persistently invalid output raises StoryValidationError and does not save."""
    gen_client = MockGenClient(["bad 1", "bad 2"])

    with pytest.raises(StoryValidationError, match="could not be parsed"):
        generate_story(
            db_session,
            premise="Repair test",
            generation_client=gen_client,
        )
    assert db_session.query(Story).count() == 0


def test_continue_story_success(db_session):
    """Continuing a story validates the choice and creates a linked child node."""
    gen_client = MockGenClient([SAMPLE_STORY_JSON, SAMPLE_CONTINUATION_JSON])

    root = generate_story(
        db_session,
        premise="Clock strikes thirteen.",
        atmosphere="Gothic",
        generation_client=gen_client,
    )

    child = continue_story(
        story_id=root.id,
        choice_id="choice_1",
        db=db_session,
        generation_client=gen_client,
    )

    assert child.id != root.id
    assert child.parent_story_id == root.id
    assert child.branch_choice == "Examine the bell"
    assert child.title == "The Resonance"
    assert "drainage" in child.body

    # Verify choices at child node
    child_choices = json.loads(child.branch_choices)
    assert len(child_choices) == 2
    assert child_choices[0]["id"] == "choice_3"


def test_continue_story_invalid_choice_id(db_session):
    """Providing a choice ID not present in parent choices raises InvalidBranchChoiceError."""
    gen_client = MockGenClient([SAMPLE_STORY_JSON])
    root = generate_story(
        db_session,
        premise="Test",
        generation_client=gen_client,
    )

    with pytest.raises(InvalidBranchChoiceError, match="not an available branch choice"):
        continue_story(root.id, "choice_nonexistent", db_session, generation_client=gen_client)


def test_continue_story_missing_parent(db_session):
    """Continuing a nonexistent story raises StoryNotFoundError."""
    gen_client = MockGenClient([SAMPLE_STORY_JSON])
    with pytest.raises(StoryNotFoundError, match="not found"):
        continue_story("missing_id", "choice_1", db_session, generation_client=gen_client)


def test_full_narrative_multi_level_and_branches(db_session):
    """Full narrative reconstructs multi-level ancestral chain, and branches endpoint returns children."""
    gen_client = MockGenClient([SAMPLE_STORY_JSON, SAMPLE_CONTINUATION_JSON])

    root = generate_story(db_session, premise="Test multi-level", generation_client=gen_client)
    child1 = continue_story(root.id, "choice_1", db=db_session, generation_client=gen_client)

    # Branch 2 from root with choice_2
    gen_client.responses.append(SAMPLE_CONTINUATION_JSON)
    child2 = continue_story(root.id, "choice_2", db=db_session, generation_client=gen_client)

    # 1. Full narrative for child1
    full_narrative = get_full_narrative(child1.id, db_session)
    assert full_narrative.story_id == child1.id
    assert len(full_narrative.segments) == 2
    assert full_narrative.segments[0].story_id == root.id
    assert full_narrative.segments[1].story_id == child1.id
    assert full_narrative.segments[1].branch_label == "Examine the bell"
    assert full_narrative.total_word_count == (root.word_count + child1.word_count)
    assert len(full_narrative.available_choices) == 2
    assert full_narrative.available_choices[0].id == "choice_3"

    # 2. Branches for root
    root_branches = get_story_branches(root.id, db_session)
    assert root_branches.story_id == root.id
    assert len(root_branches.available_choices) == 2
    assert len(root_branches.child_branches) == 2
    branch_labels = {c.branch_label for c in root_branches.child_branches}
    assert "Examine the bell" in branch_labels
    assert "Extinguish the lantern" in branch_labels


def test_generate_story_underlength_triggers_successful_expansion(db_session):
    """Under-length initial draft triggers a bounded corrective expansion which succeeds."""
    brief_draft_json = json.dumps({
        "title": "A Brief Fragment",
        "content": "Julian stepped onto the cold stone floor and paused.",
        "branch_choices": [
            {"id": "c1", "label": "Listen to the dark", "description": "Wait in the silent room."},
            {"id": "c2", "label": "Strike a match", "description": "Illuminate the shadows."},
        ],
    })
    expanded_json = json.dumps({
        "title": "A Brief Fragment",
        "content": VALID_SHORT_PROSE,
        "branch_choices": [
            {"id": "c1", "label": "Listen to the dark", "description": "Wait in the silent room."},
            {"id": "c2", "label": "Strike a match", "description": "Illuminate the shadows."},
        ],
    })

    gen_client = MockGenClient([brief_draft_json, expanded_json])

    story = generate_story(
        db_session,
        premise="Waiting in the silent room.",
        atmosphere="Quiet suspense",
        length="short",
        grounding_mode="freeform",
        generation_client=gen_client,
    )

    # gen_client called twice: initial generation + bounded expansion
    assert gen_client.call_count == 2
    assert story.id is not None
    assert story.status == "completed"
    assert story.word_count >= 400
    assert story.word_count <= 600
    assert db_session.query(Story).filter(Story.id == story.id).count() == 1


def test_generate_story_underlength_expansion_fails_cleanly(db_session):
    """When expansion still fails to reach the minimum word count, InsufficientStoryLengthError is raised and no story is saved."""
    stubborn_json = json.dumps({
        "title": "Unyielding Vignette",
        "content": "A very short fragment that refuses to expand into adequate prose.",
        "branch_choices": [
            {"id": "c1", "label": "Wait", "description": "Wait."},
            {"id": "c2", "label": "Run", "description": "Run."},
        ],
    })

    gen_client = MockGenClient([stubborn_json, stubborn_json])

    with pytest.raises(InsufficientStoryLengthError) as exc_info:
        generate_story(
            db_session,
            premise="Short test.",
            atmosphere="Gothic",
            length="short",
            grounding_mode="freeform",
            generation_client=gen_client,
        )

    assert "below the minimum required (400 words) for preset 'short'" in str(exc_info.value)
    # Ensure story was not committed or saved
    assert db_session.query(Story).count() == 0


def test_generate_story_medium_preset_success(db_session):
    """Medium preset requires 800 to 1,200 words and persists successfully when met."""
    medium_prose = (VALID_SHORT_PROSE + "\n\n" + VALID_CONT_PROSE).strip()
    medium_word_count = len(medium_prose.split())
    assert medium_word_count >= 800 and medium_word_count <= 1200

    medium_json = json.dumps({
        "title": "The Dual Chamber",
        "content": medium_prose,
        "branch_choices": [
            {"id": "c1", "label": "Inspect the altar", "description": "Approach the stone table."},
            {"id": "c2", "label": "Descend the shaft", "description": "Climb into the cistern."},
        ],
    })

    gen_client = MockGenClient([medium_json])

    story = generate_story(
        db_session,
        premise="Exploring both upper conservatory and flooded lower archive.",
        atmosphere="Melancholy",
        length="medium",
        grounding_mode="freeform",
        generation_client=gen_client,
    )

    assert story.status == "completed"
    assert story.requested_length == "medium"
    assert story.word_count == medium_word_count
    assert story.word_count >= 800


def test_generate_story_long_preset_success(db_session):
    """Long preset requires 1,500 to 2,000 words and persists successfully via multi-stage generation."""
    outline_json = json.dumps({
        "title": "The Grand Chronicle",
        "sections": [
            {"act": "Act I: Inciting Incident", "summary": "Discovery of the ancient vault."},
            {"act": "Act II: Complication", "summary": "The rising tide threatens escape."},
            {"act": "Act III: Resolution", "summary": "Julian reaches the inner sanctum."},
        ],
    })
    sec_content = (VALID_SHORT_PROSE + "\n\n" + VALID_CONT_PROSE[:700]).strip()
    sec1_json = json.dumps({"title": "The Grand Chronicle", "content": sec_content, "branch_choices": []})
    sec2_json = json.dumps({"title": "The Grand Chronicle", "content": sec_content, "branch_choices": []})
    sec3_json = json.dumps({
        "title": "The Grand Chronicle",
        "content": sec_content,
        "branch_choices": [
            {"id": "c1", "label": "Unseal the vault", "description": "Open the final seal."},
            {"id": "c2", "label": "Return to shore", "description": "Escape across the sands."},
        ],
    })

    gen_client = MockGenClient([outline_json, sec1_json, sec2_json, sec3_json])

    story = generate_story(
        db_session,
        premise="The comprehensive history of the drowned conservatory and its keepers.",
        atmosphere="Gothic",
        length="long",
        grounding_mode="freeform",
        generation_client=gen_client,
    )

    assert story.status == "completed"
    assert story.requested_length == "long"
    assert 1500 <= story.word_count <= 2000
    assert story.title == "The Grand Chronicle"
    assert len(json.loads(story.branch_choices)) == 2


def test_expansion_preserves_choices_and_archive_sources(db_session):
    """Corrective expansion preserves source references and falls back to draft choices if omitted."""
    doc = Document(
        title="Archival Register",
        original_filename="register.pdf",
        stored_filename="register_uuid.pdf",
        file_extension=".pdf",
        content_type="application/pdf",
        file_size=1024,
        status="ready",
    )
    db_session.add(doc)
    db_session.commit()

    chunk = Chunk(
        document_id=doc.id,
        chunk_index=0,
        text="The bronze astrolabe was calibrated for midnight tides.",
        page_number=1,
        section="Chapter 1",
        embedding=json.dumps([1.0, 0.0, 0.0]),
        embedding_model="nomic-embed-text",
    )
    db_session.add(chunk)
    db_session.commit()

    draft_with_choices = json.dumps({
        "title": "Calibrating the Stars",
        "content": "Julian adjusted the brass astrolabe and gazed into the dark.",
        "branch_choices": [
            {"id": "c_orig_1", "label": "Turn the altitude ring", "description": "Check the polar star."},
            {"id": "c_orig_2", "label": "Check the tide marker", "description": "Measure the rising water."},
        ],
    })
    # Expansion response that omitted branch_choices
    expansion_omitted_choices = json.dumps({
        "title": "Calibrating the Stars",
        "content": VALID_SHORT_PROSE,
        "branch_choices": [],
    })

    gen_client = MockGenClient([draft_with_choices, expansion_omitted_choices])
    mock_embed = make_mock_embed_fn([1.0, 0.0, 0.0])

    story = generate_story(
        db_session,
        premise="Calibrating the brass astrolabe.",
        atmosphere="Supernatural mystery",
        length="short",
        grounding_mode="archive",
        document_ids=[doc.id],
        generation_client=gen_client,
        embed_fn=mock_embed,
    )

    assert story.status == "completed"
    assert story.word_count >= 400
    # Source references preserved
    sources = json.loads(story.source_references)
    assert len(sources) == 1
    assert sources[0]["document_title"] == "Archival Register"
    # Choices preserved from original draft
    choices = json.loads(story.branch_choices)
    assert len(choices) == 2
    assert choices[0]["id"] == "c_orig_1"
    assert choices[1]["id"] == "c_orig_2"


def test_multi_branch_tree_and_isolation(db_session):
    """Verify 3-level branching: Root -> A -> A2, Root -> B, with complete narrative isolation."""
    # Root story
    root_json = SAMPLE_STORY_JSON
    # Branch A from Root (choice_1)
    branch_a_json = json.dumps({
        "title": "Branch A: The Upper Gallery",
        "content": VALID_CONT_PROSE,
        "branch_choices": [
            {"id": "choice_a2_1", "label": "Ascend to the bell tower", "description": "Climb the iron spiral."},
            {"id": "choice_a2_2", "label": "Unlock the lead door", "description": "Turn the heavy key."},
        ],
    })
    # Branch A2 from Branch A (choice_a2_1)
    branch_a2_prose = (
        "Julian climbed into the belfry where the wind shrieked through the louvered slats. "
        + VALID_SHORT_PROSE
    )
    branch_a2_json = json.dumps({
        "title": "Branch A2: The Belfry",
        "content": branch_a2_prose,
        "branch_choices": [
            {"id": "choice_a3_1", "label": "Ring the bronze bell", "description": "Strike the hammer."},
            {"id": "choice_a3_2", "label": "Peer through the spyglass", "description": "Look toward the shoal."},
        ],
    })
    # Branch B from Root (choice_2)
    branch_b_prose = (
        "Extinguishing the lantern, Julian stood immersed in total blackness as the tide sighed against the pilings. "
        + VALID_CONT_PROSE
    )
    branch_b_json = json.dumps({
        "title": "Branch B: The Darkness",
        "content": branch_b_prose,
        "branch_choices": [
            {"id": "choice_b2_1", "label": "Call into the void", "description": "Speak into the dark."},
            {"id": "choice_b2_2", "label": "Crawl toward the sound", "description": "Follow the dripping water."},
        ],
    })

    gen_client = MockGenClient([root_json, branch_a_json, branch_a2_json, branch_b_json])

    # 1. Generate Root
    root = generate_story(db_session, premise="Conservative mystery", generation_client=gen_client)
    assert root.parent_story_id is None

    # 2. Branch A from Root (choice_1)
    node_a = continue_story(root.id, "choice_1", db_session, generation_client=gen_client)
    assert node_a.parent_story_id == root.id
    assert node_a.branch_choice == "Examine the bell"

    # 3. Branch A2 from Branch A (choice_a2_1)
    node_a2 = continue_story(node_a.id, "choice_a2_1", db_session, generation_client=gen_client)
    assert node_a2.parent_story_id == node_a.id
    assert node_a2.branch_choice == "Ascend to the bell tower"

    # 4. Branch B from Root (choice_2)
    node_b = continue_story(root.id, "choice_2", db_session, generation_client=gen_client)
    assert node_b.parent_story_id == root.id
    assert node_b.branch_choice == "Extinguish the lantern"

    # 5. Full narrative reconstruction for Branch A2: Root -> A -> A2
    narrative_a2 = get_full_narrative(node_a2.id, db_session)
    assert len(narrative_a2.segments) == 3
    assert narrative_a2.segments[0].story_id == root.id
    assert narrative_a2.segments[1].story_id == node_a.id
    assert narrative_a2.segments[2].story_id == node_a2.id
    assert narrative_a2.segments[1].branch_label == "Examine the bell"
    assert narrative_a2.segments[2].branch_label == "Ascend to the bell tower"

    # 6. Full narrative reconstruction for Branch B: Root -> B
    narrative_b = get_full_narrative(node_b.id, db_session)
    assert len(narrative_b.segments) == 2
    assert narrative_b.segments[0].story_id == root.id
    assert narrative_b.segments[1].story_id == node_b.id
    assert narrative_b.segments[1].branch_label == "Extinguish the lantern"

    # 7. Strict isolation check:
    # A2 narrative contains zero Branch B text
    a2_full_text = " ".join(seg.content for seg in narrative_a2.segments)
    b_full_text = " ".join(seg.content for seg in narrative_b.segments)

    assert "Branch B: The Darkness" not in a2_full_text
    assert "Call into the void" not in [c.label for c in narrative_a2.available_choices]
    assert "Branch A: The Upper Gallery" not in b_full_text
    assert "Branch A2: The Belfry" not in b_full_text

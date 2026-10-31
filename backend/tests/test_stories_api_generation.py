"""API integration tests for story generation, continuation, full narrative reconstruction, and branching."""
from __future__ import annotations

import json
from app.models import Chunk, Document
from app.services import story_engine
from app.services.ollama_client import EmbeddingResult
from app.services.ollama_generation import OllamaConnectionError


VALID_SHORT_PROSE_A = (
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

VALID_CONT_PROSE_A = (
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

MOCK_GEN_JSON = json.dumps({
    "title": "The Drowned Observatory",
    "content": VALID_SHORT_PROSE_A,
    "branch_choices": [
        {"id": "c1", "label": "Ascend the spiral stairs", "description": "Seek higher elevation before the surge."},
        {"id": "c2", "label": "Retrieve the brass cylinder", "description": "Dive toward the submerged pedestal."},
    ],
})

MOCK_CONT_JSON = json.dumps({
    "title": "The Flooded Stairwell",
    "content": VALID_CONT_PROSE_A,
    "branch_choices": [
        {"id": "c3", "label": "Break through the trapdoor", "description": "Force open the copper hatch."},
        {"id": "c4", "label": "Listen to the vibration", "description": "Wait for the resonance to subside."},
    ],
})


def test_api_generate_story_freeform(client, monkeypatch):
    """POST /api/stories/generate creates and returns a freeform story."""
    class FakeGenClient:
        default_model = "test-gen-model"
        def generate_chat_completion(self, messages, **kwargs):
            return MOCK_GEN_JSON

    monkeypatch.setattr(story_engine, "get_generation_client", lambda: FakeGenClient())

    resp = client.post(
        "/api/stories/generate",
        json={
            "premise": "Water flooding an old observatory.",
            "atmosphere": "Quiet suspense",
            "length": "short",
            "grounding_mode": "freeform",
        },
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "The Drowned Observatory"
    assert data["grounding_mode"] == "freeform"
    assert data["status"] == "completed"
    assert len(data["branch_choices"]) == 2
    assert data["branch_choices"][0]["id"] == "c1"
    assert data["word_count"] > 0
    assert data["parent_story_id"] is None


def test_api_generate_story_archive_grounded(client, db_session, monkeypatch):
    """POST /api/stories/generate with archive grounding embeds and returns source refs."""
    doc = Document(
        title="Estuary Hydrology",
        original_filename="hydro.pdf",
        stored_filename="hydro_stored.pdf",
        file_extension=".pdf",
        content_type="application/pdf",
        file_size=2048,
        status="ready",
    )
    db_session.add(doc)
    db_session.commit()

    chunk = Chunk(
        document_id=doc.id,
        chunk_index=0,
        text="High tides regularly submerge the observatory foundation during lunar equinox.",
        page_number=5,
        section="Chapter 1",
        embedding=json.dumps([1.0, 0.0, 0.0]),
        embedding_model="nomic-embed-text",
    )
    db_session.add(chunk)
    db_session.commit()

    class FakeGenClient:
        default_model = "test-gen-model"
        def generate_chat_completion(self, messages, **kwargs):
            return MOCK_GEN_JSON

    monkeypatch.setattr(story_engine, "get_generation_client", lambda: FakeGenClient())
    monkeypatch.setattr(
        story_engine,
        "embed_texts",
        lambda texts, **kwargs: EmbeddingResult(
            embeddings=[[1.0, 0.0, 0.0]],
            model="nomic-embed-text",
            dimensions=3,
        ),
    )

    resp = client.post(
        "/api/stories/generate",
        json={
            "premise": "High tides flooding the observatory.",
            "atmosphere": "Gothic",
            "length": "short",
            "grounding_mode": "archive",
            "document_ids": [doc.id],
        },
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["grounding_mode"] == "archive"
    assert len(data["source_references"]) == 1
    assert data["source_references"][0]["document_title"] == "Estuary Hydrology"
    assert data["source_references"][0]["page_number"] == 5


def test_api_generate_story_insufficient_archive(client, db_session, monkeypatch):
    """POST /api/stories/generate returns 422 if archive has no relevant passages."""
    doc = Document(
        title="Unrelated Archive",
        original_filename="unrelated.txt",
        stored_filename="unrelated_stored.txt",
        file_extension=".txt",
        content_type="text/plain",
        file_size=100,
        status="ready",
    )
    db_session.add(doc)
    db_session.commit()

    chunk = Chunk(
        document_id=doc.id,
        chunk_index=0,
        text="A ledger of grain exports.",
        embedding=json.dumps([0.0, 1.0, 0.0]),
        embedding_model="nomic-embed-text",
    )
    db_session.add(chunk)
    db_session.commit()

    monkeypatch.setattr(
        story_engine,
        "embed_texts",
        lambda texts, **kwargs: EmbeddingResult(
            embeddings=[[1.0, 0.0, 0.0]],  # Orthogonal to chunk -> score 0.0
            model="nomic-embed-text",
            dimensions=3,
        ),
    )

    resp = client.post(
        "/api/stories/generate",
        json={
            "premise": "Searching for meteors.",
            "grounding_mode": "archive",
            "document_ids": [doc.id],
        },
    )

    assert resp.status_code == 422
    assert "No sufficiently relevant passages" in resp.json()["detail"]


def test_api_generate_story_ollama_offline(client, monkeypatch):
    """POST /api/stories/generate returns 503 if Ollama is unreachable."""
    class FakeOfflineGenClient:
        def generate_chat_completion(self, messages, **kwargs):
            raise OllamaConnectionError("Cannot connect to Ollama")

    monkeypatch.setattr(story_engine, "get_generation_client", lambda: FakeOfflineGenClient())

    resp = client.post(
        "/api/stories/generate",
        json={"premise": "Test", "grounding_mode": "freeform"},
    )
    assert resp.status_code == 503
    assert "Cannot connect to Ollama" in resp.json()["detail"]


def test_api_continue_story_and_branching(client, monkeypatch):
    """POST /api/stories/{id}/continue generates child story node and links branches."""
    responses = [MOCK_GEN_JSON, MOCK_CONT_JSON]

    class FakeGenClient:
        default_model = "test-gen-model"
        def generate_chat_completion(self, messages, **kwargs):
            return responses.pop(0) if responses else MOCK_CONT_JSON

    monkeypatch.setattr(story_engine, "get_generation_client", lambda: FakeGenClient())

    # 1. Generate root
    root_resp = client.post(
        "/api/stories/generate",
        json={"premise": "Flooding observatory.", "grounding_mode": "freeform"},
    )
    assert root_resp.status_code == 201
    root_id = root_resp.json()["id"]

    # 2. Continue with choice 'c1'
    cont_resp = client.post(
        f"/api/stories/{root_id}/continue",
        json={"choice_id": "c1"},
    )
    assert cont_resp.status_code == 201
    child_data = cont_resp.json()
    assert child_data["parent_story_id"] == root_id
    assert child_data["branch_choice"] == "Ascend the spiral stairs"
    child_id = child_data["id"]

    # 3. Test invalid choice ID -> 422
    invalid_resp = client.post(
        f"/api/stories/{root_id}/continue",
        json={"choice_id": "unknown_choice"},
    )
    assert invalid_resp.status_code == 422

    # 4. GET /api/stories/{id}/full
    full_resp = client.get(f"/api/stories/{child_id}/full")
    assert full_resp.status_code == 200
    full_data = full_resp.json()
    assert full_data["story_id"] == child_id
    assert len(full_data["segments"]) == 2
    assert full_data["segments"][0]["story_id"] == root_id
    assert full_data["segments"][1]["story_id"] == child_id
    assert full_data["total_word_count"] > 0
    assert len(full_data["available_choices"]) == 2
    assert full_data["available_choices"][0]["id"] == "c3"

    # 5. GET /api/stories/{id}/branches
    branch_resp = client.get(f"/api/stories/{root_id}/branches")
    assert branch_resp.status_code == 200
    branch_data = branch_resp.json()
    assert branch_data["story_id"] == root_id
    assert len(branch_data["available_choices"]) == 2
    assert len(branch_data["child_branches"]) == 1
    assert branch_data["child_branches"][0]["story_id"] == child_id
    assert branch_data["child_branches"][0]["branch_label"] == "Ascend the spiral stairs"


def test_api_generate_story_underlength_expansion_failure_returns_422(client, monkeypatch):
    """POST /api/stories/generate returns 422 when generation and expansion are both under-length."""
    short_json = json.dumps({
        "title": "Vignette",
        "content": "A very brief narrative that cannot possibly meet the required word count minimum.",
        "branch_choices": [
            {"id": "c1", "label": "Turn left", "description": "Go west."},
            {"id": "c2", "label": "Turn right", "description": "Go east."},
        ],
    })

    class StubbornShortGenClient:
        default_model = "test-gen-model"
        def generate_chat_completion(self, messages, **kwargs):
            return short_json

    monkeypatch.setattr(story_engine, "get_generation_client", lambda: StubbornShortGenClient())

    resp = client.post(
        "/api/stories/generate",
        json={
            "premise": "A brief scene in the fog.",
            "atmosphere": "Gothic",
            "length": "short",
            "grounding_mode": "freeform",
        },
    )

    assert resp.status_code == 422
    data = resp.json()
    assert "below the minimum required" in data["detail"]
    assert "400 words" in data["detail"]


def test_api_continue_story_underlength_expansion_failure_returns_422(client, monkeypatch):
    """POST /api/stories/{id}/continue returns 422 when continuation is stubbornly under-length."""
    responses = [MOCK_GEN_JSON]
    short_json = json.dumps({
        "title": "Stubborn Fragment",
        "content": "She took three steps and stopped walking altogether.",
        "branch_choices": [
            {"id": "c10", "label": "Wait", "description": "Stand still."},
            {"id": "c11", "label": "Flee", "description": "Run away."},
        ],
    })

    class MultiGenClient:
        default_model = "test-gen-model"
        def generate_chat_completion(self, messages, **kwargs):
            if responses:
                return responses.pop(0)
            return short_json

    monkeypatch.setattr(story_engine, "get_generation_client", lambda: MultiGenClient())

    # Create root
    root_resp = client.post(
        "/api/stories/generate",
        json={"premise": "Flooding observatory.", "grounding_mode": "freeform"},
    )
    assert root_resp.status_code == 201
    root_id = root_resp.json()["id"]

    # Continue should fail with 422
    cont_resp = client.post(
        f"/api/stories/{root_id}/continue",
        json={"choice_id": "c1"},
    )
    assert cont_resp.status_code == 422
    assert "below the minimum required" in cont_resp.json()["detail"]

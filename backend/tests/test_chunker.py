"""Tests for passage chunking."""
from __future__ import annotations

from app.services.chunker import chunk_passages
from app.services.document_parser import ExtractedPassage


def test_chunk_empty_passages():
    assert chunk_passages([]) == []


def test_chunk_whitespace_passages():
    passages = [ExtractedPassage(text="   \n\t  ")]
    assert chunk_passages(passages) == []


def test_chunk_short_passage():
    passages = [
        ExtractedPassage(
            text="The ink was faded but legible.",
            page_number=3,
            section="Manuscripts",
        )
    ]
    chunks = chunk_passages(passages, chunk_size=500, chunk_overlap=50)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == "The ink was faded but legible."
    assert chunks[0].page_number == 3
    assert chunks[0].section == "Manuscripts"


def test_chunk_long_passage_multiple_sentences():
    sentence_1 = "The archivist lit the tallow candle and approached the iron door."
    sentence_2 = "Behind the latch lay sixty volumes of municipal registry from the flooded year."
    sentence_3 = "Each ledger bore the wax seal of the drowned diocese."
    sentence_4 = "He laid his palm against the cold binding and felt the faint vibration of deep water."

    text = f"{sentence_1} {sentence_2} {sentence_3} {sentence_4}"
    passage = ExtractedPassage(text=text, page_number=1, section="Intro")

    # Target chunk_size small enough to force splitting
    chunks = chunk_passages([passage], chunk_size=120, chunk_overlap=40)

    assert len(chunks) >= 2
    # Verify sequential indices
    for i, c in enumerate(chunks):
        assert c.chunk_index == i
        assert c.page_number == 1
        assert c.section == "Intro"


def test_chunk_very_long_sentence():
    # A single sentence that exceeds chunk_size
    long_sentence = "A" * 300
    passage = ExtractedPassage(text=long_sentence, page_number=2)

    chunks = chunk_passages([passage], chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) <= 100
        assert c.page_number == 2


def test_chunk_metadata_across_passages():
    p1 = ExtractedPassage(text="First passage text.", page_number=1, section="Ch1")
    p2 = ExtractedPassage(text="Second passage text.", page_number=2, section="Ch2")

    chunks = chunk_passages([p1, p2], chunk_size=500, chunk_overlap=50)
    assert len(chunks) == 2
    assert chunks[0].chunk_index == 0
    assert chunks[0].section == "Ch1"
    assert chunks[0].page_number == 1

    assert chunks[1].chunk_index == 1
    assert chunks[1].section == "Ch2"
    assert chunks[1].page_number == 2


def test_chunk_parameter_boundary_handling():
    passage = ExtractedPassage(text="Simple text for safety boundaries test.")
    # Extreme/invalid params should not crash
    c1 = chunk_passages([passage], chunk_size=10, chunk_overlap=20)
    assert len(c1) > 0

    c2 = chunk_passages([passage], chunk_size=100, chunk_overlap=-10)
    assert len(c2) > 0

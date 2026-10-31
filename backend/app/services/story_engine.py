"""Core story generation engine for archive-grounded and freeform atmospheric fiction."""
from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Document, Story
from ..schemas import (
    BranchChoice,
    ChildBranchNode,
    FullStoryNarrativeResponse,
    NarrativeSegment,
    StoryBranchesResponse,
    StoryGenerationResponse,
)
from .ollama_client import (
    OllamaConnectionError as OllamaEmbedConnectionError,
    OllamaEmbeddingError,
    OllamaModelError as OllamaEmbedModelError,
    embed_texts,
)
from .ollama_generation import OllamaGenerationClient, get_generation_client
from .prompt_builder import (
    LENGTH_SPECS,
    build_compression_prompt,
    build_continuation_prompt,
    build_expansion_prompt,
    build_initial_story_prompt,
    build_long_story_outline_prompt,
    build_long_story_section_prompt,
    build_repair_prompt,
    stitch_sections,
)
from .retrieval import SearchResult, search_chunks


class StoryEngineError(Exception):
    """Base exception for story generation engine errors."""
    pass


class InsufficientArchiveContextError(StoryEngineError):
    """Raised when archive-grounded search returns no sufficiently relevant passages."""
    pass


class StoryValidationError(StoryEngineError):
    """Raised when generated story output fails structural or literary validation."""
    pass


class StoryLengthOutOfBoundsError(StoryValidationError):
    """Raised when generated story falls outside the required [min_words, max_words] window."""

    def __init__(
        self,
        actual_words: int,
        min_words: int,
        max_words: int,
        length_preset: str,
        reason: str = "out_of_bounds",
    ):
        self.actual_words = actual_words
        self.min_words = min_words
        self.max_words = max_words
        self.length_preset = length_preset
        self.reason = reason
        if reason == "below_minimum":
            msg = (
                f"Generated story length ({actual_words} words) is below the minimum required "
                f"({min_words} words) for preset '{length_preset}' (required: {min_words}–{max_words} words)."
            )
        elif reason == "above_maximum":
            msg = (
                f"Generated story length ({actual_words} words) exceeds the maximum allowed "
                f"({max_words} words) for preset '{length_preset}' (required: {min_words}–{max_words} words)."
            )
        else:
            msg = (
                f"Generated story length ({actual_words} words) is outside the allowed range "
                f"({min_words}–{max_words} words) for preset '{length_preset}'."
            )
        super().__init__(msg)


class InsufficientStoryLengthError(StoryLengthOutOfBoundsError):
    """Raised when generated story does not meet the minimum required word count after expansion."""

    def __init__(self, actual_words: int, min_words: int, length_preset: str, max_words: int = 0):
        if not max_words and length_preset in LENGTH_SPECS:
            max_words = LENGTH_SPECS[length_preset]["max_words"]
        super().__init__(actual_words, min_words, max_words or min_words, length_preset, reason="below_minimum")


class ExcessiveStoryLengthError(StoryLengthOutOfBoundsError):
    """Raised when generated story exceeds the maximum allowed word count after compression."""

    def __init__(self, actual_words: int, max_words: int, length_preset: str, min_words: int = 0):
        if not min_words and length_preset in LENGTH_SPECS:
            min_words = LENGTH_SPECS[length_preset]["min_words"]
        super().__init__(actual_words, min_words or 0, max_words, length_preset, reason="above_maximum")


class StoryNotFoundError(StoryEngineError):
    """Raised when a requested story node is not found."""
    pass


class InvalidBranchChoiceError(StoryEngineError):
    """Raised when a selected choice ID is not valid for the target story."""
    pass


class GeneratedStoryPayload(BaseModel):
    """Internal validation model for LLM structured output."""

    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=10)
    branch_choices: list[BranchChoice] = Field(..., min_length=2, max_length=4)


def _extract_prose_from_raw(raw_content: Any) -> str:
    """Extract and normalize prose text from various LLM JSON response formats."""
    if raw_content is None:
        return ""
    if isinstance(raw_content, str):
        return raw_content.strip()
    if isinstance(raw_content, list):
        paras = []
        for item in raw_content:
            p = _extract_prose_from_raw(item)
            if p:
                paras.append(p)
        return "\n\n".join(paras)
    if isinstance(raw_content, dict):
        paras = []
        for k, v in raw_content.items():
            # Check if key is a long narrative paragraph (common LLM JSON formatting quirk)
            if isinstance(k, str) and len(k.strip()) > 50:
                paras.append(k.strip())
            # Check if value is a long narrative paragraph
            if isinstance(v, str) and len(v.strip()) > 50:
                paras.append(v.strip())
            elif isinstance(v, (dict, list)):
                p = _extract_prose_from_raw(v)
                if p:
                    paras.append(p)
            elif isinstance(v, str) and len(v.strip()) > 0 and not (isinstance(k, str) and len(k.strip()) > 50):
                if k.lower() not in {"id", "choice", "key", "action", "label", "description"}:
                    if not v.strip().startswith(("branch_choice", "choice_", "{", "[")):
                        paras.append(v.strip())
        return "\n\n".join(paras)
    return str(raw_content).strip()


def _repair_truncated_json(text: str) -> str:
    """Attempt robust repairs for truncated JSON (unclosed quotes, missing dict values, unclosed braces)."""
    t = text.strip()
    in_quotes = False
    escape = False
    for ch in t:
        if ch == '\\' and not escape:
            escape = True
            continue
        if ch == '"' and not escape:
            in_quotes = not in_quotes
        escape = False
    if in_quotes:
        t += '"'

    t_clean = t.rstrip()
    if t_clean.endswith(","):
        t = t_clean[:-1].rstrip()

    open_braces = t.count('{') - t.count('}')
    open_brackets = t.count('[') - t.count(']')

    attempt = t + (']' * max(0, open_brackets)) + ('}' * max(0, open_braces))
    try:
        json.loads(attempt)
        return attempt
    except json.JSONDecodeError as e:
        err_msg = str(e)
        if "Expecting ':' delimiter" in err_msg:
            attempt2 = t + ': ""' + (']' * max(0, open_brackets)) + ('}' * max(0, open_braces))
            try:
                json.loads(attempt2)
                return attempt2
            except Exception:
                pass
        elif "Expecting value" in err_msg:
            attempt3 = t.rstrip(':').rstrip(',') + (']' * max(0, open_brackets)) + ('}' * max(0, open_braces))
            try:
                json.loads(attempt3)
                return attempt3
            except Exception:
                pass

    return attempt


def _parse_and_validate_payload(
    raw_text: str,
    generation_client: OllamaGenerationClient,
    allow_retry: bool = True,
    fallback_choices: Optional[list[BranchChoice]] = None,
) -> GeneratedStoryPayload:
    """Parse JSON string into GeneratedStoryPayload with normalization and bounded repair."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    data = None
    try:
        data = json.loads(cleaned)
    except Exception:
        repaired = _repair_truncated_json(cleaned)
        try:
            data = json.loads(repaired)
        except Exception:
            data = None

    if data is None or not isinstance(data, dict):
        if not allow_retry:
            raise StoryValidationError(
                f"Generated content could not be parsed into a valid JSON object: {raw_text[:200]}"
            )
        repair_messages = build_repair_prompt(raw_text, "Invalid or unparseable JSON format")
        repaired_text = generation_client.generate_chat_completion(repair_messages, format_json=True)
        return _parse_and_validate_payload(
            repaired_text,
            generation_client,
            allow_retry=False,
            fallback_choices=fallback_choices,
        )

    # Normalize extracted components
    raw_title = data.get("title") or data.get("story_title") or data.get("heading")
    title = str(raw_title).strip() if raw_title else "The Unnamed Manuscript"

    raw_content = (
        data.get("content")
        or data.get("story")
        or data.get("prose")
        or data.get("narrative")
        or data.get("body")
        or data.get("text")
    )
    content = _extract_prose_from_raw(raw_content)

    if not content or content == "None" or len(content) < 10:
        ignored_keys = {"title", "story_title", "heading", "branch_choices", "branchchoices", "choices", "branches", "options"}
        other_paras = []
        for k, v in data.items():
            if k.lower() not in ignored_keys:
                extracted = _extract_prose_from_raw(v)
                if extracted and extracted != "None":
                    other_paras.append(extracted)
                elif isinstance(k, str) and len(k.strip()) > 30:
                    other_paras.append(k.strip())
        if other_paras:
            content = "\n\n".join(other_paras)

    raw_choices = (
        data.get("branch_choices")
        or data.get("branchChoices")
        or data.get("choices")
        or data.get("branches")
        or data.get("options")
    )
    parsed_choices: list[BranchChoice] = []

    if isinstance(raw_choices, dict):
        items = []
        for k, v in raw_choices.items():
            if isinstance(v, dict):
                v_copy = dict(v)
                if "id" not in v_copy:
                    v_copy["id"] = k
                items.append(v_copy)
            elif isinstance(v, str):
                items.append({"id": k, "label": v, "description": v})
        raw_choices = items

    if isinstance(raw_choices, list):
        for idx, item in enumerate(raw_choices, start=1):
            if isinstance(item, str) and item.strip():
                parsed_choices.append(
                    BranchChoice(
                        id=f"choice_{idx}",
                        label=item.strip(),
                        description=f"Pursue {item.strip()}",
                    )
                )
            elif isinstance(item, dict):
                c_id = str(item.get("id") or f"choice_{idx}").strip()
                c_label = str(
                    item.get("label")
                    or item.get("action")
                    or item.get("text")
                    or item.get("title")
                    or item.get("name")
                    or ""
                ).strip()
                c_desc = str(item.get("description") or item.get("desc") or c_label).strip()
                if c_label:
                    parsed_choices.append(BranchChoice(id=c_id, label=c_label, description=c_desc))

    if len(parsed_choices) < 2 and fallback_choices and len(fallback_choices) >= 2:
        parsed_choices = list(fallback_choices)

    if len(parsed_choices) < 2:
        existing_ids = {c.id for c in parsed_choices}
        default_candidates = [
            ("choice_1", "Investigate the mystery further", "Press deeper into the unfamiliar territory."),
            ("choice_2", "Retreat and observe from the shadows", "Step back and assess the dangers before proceeding."),
            ("choice_3", "Examine the nearest artifact", "Inspect the physical clues left in the vicinity."),
        ]
        for c_id, c_lbl, c_dsc in default_candidates:
            if len(parsed_choices) >= 2:
                break
            if c_id not in existing_ids:
                parsed_choices.append(BranchChoice(id=c_id, label=c_lbl, description=c_dsc))
                existing_ids.add(c_id)

    try:
        return GeneratedStoryPayload(
            title=title,
            content=content,
            branch_choices=parsed_choices,
        )
    except Exception as exc:
        if not allow_retry:
            raise StoryValidationError(
                f"Generated content could not be parsed into a valid story structure: {exc}"
            ) from exc

        repair_messages = build_repair_prompt(raw_text, str(exc))
        repaired_text = generation_client.generate_chat_completion(repair_messages, format_json=True)
        return _parse_and_validate_payload(
            repaired_text,
            generation_client,
            allow_retry=False,
            fallback_choices=fallback_choices,
        )


def _generate_long_story_multistage(
    *,
    premise: str,
    atmosphere: str,
    grounding_mode: str,
    sources: Optional[list[SearchResult]],
    gen_client: OllamaGenerationClient,
) -> GeneratedStoryPayload:
    """Multi-stage generation for Long preset stories (1,500–2,000 words).

    1. Generates a structured 3-act outline.
    2. Sequentially generates Act I, Act II, and Act III with narrative context passing.
    3. Seamlessly stitches sections without boundary duplication or repeated headers.
    4. Validates final word count against [1,500, 2,000] and executes bounded correction if needed.
    """
    length_spec = LENGTH_SPECS["long"]

    # 1. Generate outline
    outline_messages = build_long_story_outline_prompt(
        premise=premise,
        atmosphere=atmosphere,
        sources=sources,
    )
    raw_outline = gen_client.generate_chat_completion(outline_messages, format_json=True, max_tokens=900)

    try:
        outline_data = json.loads(_repair_truncated_json(raw_outline))
    except Exception:
        outline_data = {}

    title = str(outline_data.get("title") or "The Midnight Archive").strip()
    raw_sections = outline_data.get("sections")
    if not isinstance(raw_sections, list) or len(raw_sections) < 3:
        raw_sections = [
            {"act": "Act I: Inciting Incident & Discovery", "summary": f"Initial discovery and setting establishment regarding: {premise}"},
            {"act": "Act II: Complication & Rising Dread", "summary": "Investigation into the anomaly and escalating danger."},
            {"act": "Act III: Climactic Revelation & Crossroads", "summary": "Confrontation of the core mystery and arrival at a decisive threshold."},
        ]

    sections_prose: list[str] = []
    final_choices: list[BranchChoice] = []
    preceding_context: Optional[str] = None
    total_sections = len(raw_sections)

    for idx, sec in enumerate(raw_sections, start=1):
        act_name = str(sec.get("act") or f"Act {idx}")
        act_summary = str(sec.get("summary") or premise)

        sec_messages = build_long_story_section_prompt(
            title=title,
            premise=premise,
            atmosphere=atmosphere,
            section_idx=idx,
            total_sections=total_sections,
            act_name=act_name,
            act_summary=act_summary,
            preceding_prose=preceding_context,
            sources=sources,
        )

        raw_sec = gen_client.generate_chat_completion(sec_messages, format_json=True, max_tokens=1100)
        sec_payload = _parse_and_validate_payload(raw_sec, gen_client)

        if idx == 1 and sec_payload.title and sec_payload.title != "The Unnamed Manuscript":
            title = sec_payload.title

        sec_prose = sec_payload.content.strip()
        sections_prose.append(sec_prose)

        if sec_payload.branch_choices and len(sec_payload.branch_choices) >= 2:
            final_choices = sec_payload.branch_choices

        words = sec_prose.split()
        preceding_context = " ".join(words[-300:]) if len(words) > 300 else sec_prose

    # 3. Assemble and stitch sections cleanly
    assembled_prose = stitch_sections(sections_prose)
    word_count = len(assembled_prose.split())

    # 4. Two-sided length boundary validation and bounded corrective passes
    if word_count < length_spec["min_words"]:
        expansion_messages = build_expansion_prompt(
            current_title=title,
            current_content=assembled_prose,
            premise=premise,
            atmosphere=atmosphere,
            length="long",
            current_choices=[c.model_dump() for c in final_choices],
            sources=sources,
        )
        expanded_raw = gen_client.generate_chat_completion(
            expansion_messages,
            format_json=True,
            max_tokens=length_spec["max_tokens"],
        )
        expanded_payload = _parse_and_validate_payload(
            expanded_raw,
            gen_client,
            fallback_choices=final_choices,
        )
        expanded_word_count = len(expanded_payload.content.split())
        if expanded_word_count < length_spec["min_words"]:
            raise InsufficientStoryLengthError(
                actual_words=expanded_word_count,
                min_words=length_spec["min_words"],
                length_preset="long",
                max_words=length_spec["max_words"],
            )
        if expanded_word_count > length_spec["max_words"]:
            raise ExcessiveStoryLengthError(
                actual_words=expanded_word_count,
                max_words=length_spec["max_words"],
                length_preset="long",
                min_words=length_spec["min_words"],
            )
        assembled_prose = expanded_payload.content
        if expanded_payload.branch_choices and len(expanded_payload.branch_choices) >= 2:
            final_choices = expanded_payload.branch_choices

    elif word_count > length_spec["max_words"]:
        compression_messages = build_compression_prompt(
            current_title=title,
            current_content=assembled_prose,
            premise=premise,
            atmosphere=atmosphere,
            length="long",
            current_choices=[c.model_dump() for c in final_choices],
            sources=sources,
        )
        compressed_raw = gen_client.generate_chat_completion(
            compression_messages,
            format_json=True,
            max_tokens=length_spec["max_tokens"],
        )
        compressed_payload = _parse_and_validate_payload(
            compressed_raw,
            gen_client,
            fallback_choices=final_choices,
        )
        compressed_word_count = len(compressed_payload.content.split())
        if compressed_word_count > length_spec["max_words"]:
            raise ExcessiveStoryLengthError(
                actual_words=compressed_word_count,
                max_words=length_spec["max_words"],
                length_preset="long",
                min_words=length_spec["min_words"],
            )
        if compressed_word_count < length_spec["min_words"]:
            raise InsufficientStoryLengthError(
                actual_words=compressed_word_count,
                min_words=length_spec["min_words"],
                length_preset="long",
                max_words=length_spec["max_words"],
            )
        assembled_prose = compressed_payload.content
        if compressed_payload.branch_choices and len(compressed_payload.branch_choices) >= 2:
            final_choices = compressed_payload.branch_choices

    if len(final_choices) < 2:
        final_choices = [
            BranchChoice(id="choice_1", label="Press deeper into the unfamiliar darkness", description="Pursue the unsettling truth."),
            BranchChoice(id="choice_2", label="Seal the iron door and retreat", description="Leave the forbidden archive undisturbed."),
        ]

    return GeneratedStoryPayload(
        title=title,
        content=assembled_prose,
        branch_choices=final_choices,
    )


def _continue_long_story_multistage(
    *,
    parent: Story,
    chosen_choice: BranchChoice,
    ancestor_data: list[dict[str, str]],
    root_sources: list[dict[str, Any]],
    gen_client: OllamaGenerationClient,
) -> GeneratedStoryPayload:
    """Multi-stage continuation generation for Long preset stories (1,500–2,000 words).
    Generates 2 connected sections (~800 words each) exploring the chosen branch.
    """
    length_spec = LENGTH_SPECS["long"]
    title = parent.title

    sections_prose: list[str] = []
    final_choices: list[BranchChoice] = []

    # Section 1
    sec1_system = (
        "You are the master literary narrator of The Midnight Archivist continuing an ongoing literary narrative.\n\n"
        "NARRATIVE CONTINUITY RULES:\n"
        f"1. Write Section 1 of an expansive 2-part continuation chapter (~800 words).\n"
        f"2. Continue directly from the protagonist's chosen action: '{chosen_choice.label}' ({chosen_choice.description}).\n"
        "3. Do NOT restart the story or reintroduce characters. Immerse the reader in immediate consequences and discovery.\n"
        "4. Do NOT include markdown headers, section numbers, or titles.\n"
        '5. Return your response as a valid JSON object: {"content": "Full section 1 narrative prose here (750-850 words)..."}'
    )
    sec1_messages = [
        {"role": "system", "content": sec1_system},
        {
            "role": "user",
            "content": (
                f"ONGOING NARRATIVE: \"{title}\"\n"
                f"ORIGINAL PREMISE: {parent.premise}\n"
                f"ATMOSPHERE: {parent.atmosphere}\n"
                f"CHOSEN BRANCH: {chosen_choice.label}\n"
                "Write Section 1 prose (strictly 750 to 850 words)."
            ),
        },
    ]
    raw_s1 = gen_client.generate_chat_completion(sec1_messages, format_json=True, max_tokens=1400)
    p1 = _parse_and_validate_payload(raw_s1, gen_client)
    sections_prose.append(p1.content.strip())

    # Section 2
    sec2_system = (
        "You are the master literary narrator of The Midnight Archivist concluding an expansive continuing chapter.\n\n"
        "REQUIREMENTS:\n"
        "1. Write Section 2 of the continuation chapter (~800 words), picking up directly from Section 1.\n"
        "2. Escalate the tension and bring the chapter to a critical crossroads.\n"
        "3. Conclude with 2 or 3 distinct branch choices for where the narrative may venture next.\n"
        "4. Do NOT include markdown headers or section numbers in the prose.\n"
        '5. Return valid JSON: {"content": "Full section 2 narrative prose here (750-850 words)...", "branch_choices": [{"id": "choice_1", "label": "...", "description": "..."}, {"id": "choice_2", "label": "...", "description": "..."}]}'
    )
    words1 = p1.content.split()
    context1 = " ".join(words1[-300:]) if len(words1) > 300 else p1.content
    sec2_messages = [
        {"role": "system", "content": sec2_system},
        {
            "role": "user",
            "content": (
                f"ONGOING NARRATIVE: \"{title}\"\n"
                f"ATMOSPHERE: {parent.atmosphere}\n"
                f"PRECEDING SECTION 1 CONCLUSION:\n\"...{context1}\"\n"
                "Write Section 2 prose (strictly 750 to 850 words) and branch choices."
            ),
        },
    ]
    raw_s2 = gen_client.generate_chat_completion(sec2_messages, format_json=True, max_tokens=1500)
    p2 = _parse_and_validate_payload(raw_s2, gen_client)
    sections_prose.append(p2.content.strip())
    if p2.branch_choices and len(p2.branch_choices) >= 2:
        final_choices = p2.branch_choices

    assembled = stitch_sections(sections_prose)
    word_count = len(assembled.split())

    # Boundary validation
    if word_count < length_spec["min_words"]:
        exp_msgs = build_expansion_prompt(
            current_title=title,
            current_content=assembled,
            premise=f"Continuation pursuing '{chosen_choice.label}': {chosen_choice.description}. Original premise: {parent.premise}",
            atmosphere=parent.atmosphere,
            length="long",
            current_choices=[c.model_dump() for c in final_choices],
            sources=root_sources if parent.grounding_mode == "archive" else None,
        )
        exp_raw = gen_client.generate_chat_completion(exp_msgs, format_json=True, max_tokens=length_spec["max_tokens"])
        exp_payload = _parse_and_validate_payload(exp_raw, gen_client, fallback_choices=final_choices)
        if len(exp_payload.content.split()) < length_spec["min_words"]:
            raise InsufficientStoryLengthError(len(exp_payload.content.split()), length_spec["min_words"], "long", length_spec["max_words"])
        assembled = exp_payload.content
        if exp_payload.branch_choices and len(exp_payload.branch_choices) >= 2:
            final_choices = exp_payload.branch_choices
    elif word_count > length_spec["max_words"]:
        comp_msgs = build_compression_prompt(
            current_title=title,
            current_content=assembled,
            premise=f"Continuation pursuing '{chosen_choice.label}': {chosen_choice.description}. Original premise: {parent.premise}",
            atmosphere=parent.atmosphere,
            length="long",
            current_choices=[c.model_dump() for c in final_choices],
            sources=root_sources if parent.grounding_mode == "archive" else None,
        )
        comp_raw = gen_client.generate_chat_completion(comp_msgs, format_json=True, max_tokens=length_spec["max_tokens"])
        comp_payload = _parse_and_validate_payload(comp_raw, gen_client, fallback_choices=final_choices)
        if len(comp_payload.content.split()) > length_spec["max_words"]:
            raise ExcessiveStoryLengthError(len(comp_payload.content.split()), length_spec["max_words"], "long", length_spec["min_words"])
        assembled = comp_payload.content
        if comp_payload.branch_choices and len(comp_payload.branch_choices) >= 2:
            final_choices = comp_payload.branch_choices

    if len(final_choices) < 2:
        final_choices = [
            BranchChoice(id="choice_1", label="Venture into the inner catacombs", description="Pursue the echoes further."),
            BranchChoice(id="choice_2", label="Barricade the entryway", description="Secure the perimeter against the unseen."),
        ]

    return GeneratedStoryPayload(
        title=title,
        content=assembled,
        branch_choices=final_choices,
    )


def generate_story(
    db: Session,
    *,
    premise: str,
    atmosphere: str = "Gothic",
    length: str = "short",
    grounding_mode: str = "freeform",
    document_ids: Optional[list[str]] = None,
    top_k: int = 3,
    generation_client: Optional[OllamaGenerationClient] = None,
    embed_fn: Optional[Any] = None,
) -> Story:
    """Generate an opening story segment in archive-grounded or freeform mode."""
    gen_client = generation_client or get_generation_client()
    embedding_func = embed_fn or embed_texts

    premise_clean = premise.strip()
    if not premise_clean:
        raise StoryValidationError("Story premise cannot be empty.")

    source_refs: list[dict[str, Any]] = []
    search_results: Optional[list[SearchResult]] = None

    if grounding_mode == "archive":
        # 1. Validate requested documents if specified
        if document_ids:
            found_docs = db.query(Document).filter(Document.id.in_(document_ids)).all()
            found_ids = {d.id for d in found_docs}
            missing_ids = set(document_ids) - found_ids
            if missing_ids:
                raise StoryEngineError(
                    f"Selected document(s) not found: {', '.join(sorted(missing_ids))}"
                )
            for doc in found_docs:
                if doc.status != "ready":
                    raise StoryEngineError(
                        f"Document '{doc.title}' ({doc.id}) is not ready for retrieval (status: {doc.status})."
                    )

        # 2. Embed user premise
        try:
            emb_res = embedding_func(
                [premise_clean],
                model=settings.embedding_model,
                base_url=settings.ollama_base_url,
            )
            query_embeddings = emb_res.embeddings
        except Exception as exc:
            raise StoryEngineError(f"Failed to generate embedding for premise: {exc}") from exc

        if not query_embeddings or not query_embeddings[0]:
            raise StoryEngineError("Failed to generate embedding for the story premise.")

        # 3. Retrieve relevant chunks with minimum relevance threshold
        search_results = search_chunks(
            query_embedding=query_embeddings[0],
            db=db,
            query_model=settings.embedding_model,
            top_k=top_k,
            document_ids=document_ids,
            min_similarity=0.30,
        )

        if not search_results:
            raise InsufficientArchiveContextError(
                "No sufficiently relevant passages were found in the selected archive documents. "
                "Try selecting different documents or adjusting your story premise."
            )

        source_refs = [
            {
                "document_id": r.document_id,
                "document_title": r.document_title,
                "chunk_id": r.chunk_id,
                "page_number": r.page_number,
                "section": r.section,
                "similarity_score": round(r.similarity_score, 4),
                "text_preview": r.text[:220].strip() + ("..." if len(r.text) > 220 else ""),
            }
            for r in search_results
        ]

    # 4. Generate story payload (multi-stage for long, single-pass for short/medium)
    if length == "long":
        payload = _generate_long_story_multistage(
            premise=premise_clean,
            atmosphere=atmosphere,
            grounding_mode=grounding_mode,
            sources=search_results,
            gen_client=gen_client,
        )
        word_count = len(payload.content.split())
    else:
        messages = build_initial_story_prompt(
            premise=premise_clean,
            atmosphere=atmosphere,
            length=length,
            grounding_mode=grounding_mode,
            sources=search_results,
        )

        length_spec = LENGTH_SPECS.get(length, LENGTH_SPECS["short"])

        # 5. Generate with local LLM
        raw_response = gen_client.generate_chat_completion(
            messages,
            format_json=True,
            max_tokens=length_spec["max_tokens"],
        )
        payload = _parse_and_validate_payload(raw_response, gen_client)

        word_count = len(payload.content.split())

        # Corrective pass: Check length boundaries (expansion if under, compression if over)
        if word_count < length_spec["min_words"]:
            expansion_messages = build_expansion_prompt(
                current_title=payload.title,
                current_content=payload.content,
                premise=premise_clean,
                atmosphere=atmosphere,
                length=length,
                current_choices=[c.model_dump() for c in payload.branch_choices],
                sources=search_results if grounding_mode == "archive" else None,
            )
            expanded_raw = gen_client.generate_chat_completion(
                expansion_messages,
                format_json=True,
                max_tokens=length_spec["max_tokens"],
            )
            expanded_payload = _parse_and_validate_payload(
                expanded_raw,
                gen_client,
                fallback_choices=payload.branch_choices,
            )
            expanded_word_count = len(expanded_payload.content.split())
            if expanded_word_count < length_spec["min_words"]:
                raise InsufficientStoryLengthError(
                    actual_words=expanded_word_count,
                    min_words=length_spec["min_words"],
                    length_preset=length,
                    max_words=length_spec["max_words"],
                )
            if expanded_word_count > length_spec["max_words"]:
                raise ExcessiveStoryLengthError(
                    actual_words=expanded_word_count,
                    max_words=length_spec["max_words"],
                    length_preset=length,
                    min_words=length_spec["min_words"],
                )
            payload = expanded_payload
            word_count = expanded_word_count

        elif word_count > length_spec["max_words"]:
            compression_messages = build_compression_prompt(
                current_title=payload.title,
                current_content=payload.content,
                premise=premise_clean,
                atmosphere=atmosphere,
                length=length,
                current_choices=[c.model_dump() for c in payload.branch_choices],
                sources=search_results if grounding_mode == "archive" else None,
            )
            compressed_raw = gen_client.generate_chat_completion(
                compression_messages,
                format_json=True,
                max_tokens=length_spec["max_tokens"],
            )
            compressed_payload = _parse_and_validate_payload(
                compressed_raw,
                gen_client,
                fallback_choices=payload.branch_choices,
            )
            compressed_word_count = len(compressed_payload.content.split())
            if compressed_word_count > length_spec["max_words"]:
                raise ExcessiveStoryLengthError(
                    actual_words=compressed_word_count,
                    max_words=length_spec["max_words"],
                    length_preset=length,
                    min_words=length_spec["min_words"],
                )
            if compressed_word_count < length_spec["min_words"]:
                raise InsufficientStoryLengthError(
                    actual_words=compressed_word_count,
                    min_words=length_spec["min_words"],
                    length_preset=length,
                    max_words=length_spec["max_words"],
                )
            payload = compressed_payload
            word_count = compressed_word_count

    # 6. Persist to database
    story = Story(
        title=payload.title.strip(),
        premise=premise_clean,
        atmosphere=atmosphere,
        requested_length=length,
        grounding_mode=grounding_mode,
        body=payload.content.strip(),
        source_references=json.dumps(source_refs),
        parent_story_id=None,
        branch_choice=None,
        branch_choices=json.dumps([c.model_dump() for c in payload.branch_choices]),
        word_count=word_count,
        generation_model=gen_client.default_model,
        status="completed",
    )

    try:
        db.add(story)
        db.commit()
        db.refresh(story)
    except Exception:
        db.rollback()
        raise StoryEngineError("Failed to persist generated story to database.")

    return story


def continue_story(
    story_id: str,
    choice_id: str,
    db: Session,
    *,
    generation_client: Optional[OllamaGenerationClient] = None,
) -> Story:
    """Generate a coherent narrative continuation following a selected branch choice."""
    gen_client = generation_client or get_generation_client()

    parent = db.query(Story).filter(Story.id == story_id).first()
    if not parent:
        raise StoryNotFoundError(f"Story '{story_id}' not found.")

    if parent.status != "completed":
        raise StoryEngineError(f"Cannot branch from story with status '{parent.status}'.")

    # Validate choice_id in parent.branch_choices
    available_choices: list[BranchChoice] = []
    if parent.branch_choices:
        try:
            raw_choices = json.loads(parent.branch_choices)
            available_choices = [BranchChoice.model_validate(c) for c in raw_choices]
        except Exception:
            available_choices = []

    chosen_choice = next((c for c in available_choices if c.id == choice_id), None)
    if not chosen_choice:
        valid_ids = [c.id for c in available_choices]
        raise InvalidBranchChoiceError(
            f"Choice '{choice_id}' is not an available branch choice for story '{story_id}'. "
            f"Available choices: {valid_ids}"
        )

    # Reconstruct ancestor chain (root -> leaf)
    ancestors: list[Story] = []
    curr: Optional[Story] = parent
    while curr:
        ancestors.append(curr)
        if curr.parent_story_id:
            curr = db.query(Story).filter(Story.id == curr.parent_story_id).first()
        else:
            curr = None
    ancestors.reverse()

    ancestor_data = [
        {
            "story_id": s.id,
            "title": s.title,
            "branch_label": s.branch_choice or "",
            "body": s.body,
            "word_count": str(s.word_count or len(s.body.split())),
        }
        for s in ancestors
    ]

    # Extract source references from root
    root_sources: list[dict[str, Any]] = []
    if ancestors[0].source_references:
        try:
            root_sources = json.loads(ancestors[0].source_references)
        except Exception:
            root_sources = []

    if parent.requested_length == "long":
        payload = _continue_long_story_multistage(
            parent=parent,
            chosen_choice=chosen_choice,
            ancestor_data=ancestor_data,
            root_sources=root_sources,
            gen_client=gen_client,
        )
        word_count = len(payload.content.split())
    else:
        # Build continuation prompt
        messages = build_continuation_prompt(
            parent_title=parent.title,
            original_premise=parent.premise,
            atmosphere=parent.atmosphere,
            length=parent.requested_length,
            grounding_mode=parent.grounding_mode,
            ancestor_segments=ancestor_data,
            chosen_label=chosen_choice.label,
            chosen_description=chosen_choice.description,
            sources=root_sources if parent.grounding_mode == "archive" else None,
        )

        length_spec = LENGTH_SPECS.get(parent.requested_length, LENGTH_SPECS["short"])

        raw_response = gen_client.generate_chat_completion(
            messages,
            format_json=True,
            max_tokens=length_spec["max_tokens"],
        )
        payload = _parse_and_validate_payload(raw_response, gen_client)

        word_count = len(payload.content.split())

        # Corrective pass: Check length boundaries (expansion if under, compression if over)
        if word_count < length_spec["min_words"]:
            expansion_messages = build_expansion_prompt(
                current_title=payload.title or parent.title,
                current_content=payload.content,
                premise=f"Continuation pursuing '{chosen_choice.label}': {chosen_choice.description}. Original premise: {parent.premise}",
                atmosphere=parent.atmosphere,
                length=parent.requested_length,
                current_choices=[c.model_dump() for c in payload.branch_choices],
                sources=root_sources if parent.grounding_mode == "archive" else None,
            )
            expanded_raw = gen_client.generate_chat_completion(
                expansion_messages,
                format_json=True,
                max_tokens=length_spec["max_tokens"],
            )
            expanded_payload = _parse_and_validate_payload(
                expanded_raw,
                gen_client,
                fallback_choices=payload.branch_choices,
            )
            expanded_word_count = len(expanded_payload.content.split())
            if expanded_word_count < length_spec["min_words"]:
                raise InsufficientStoryLengthError(
                    actual_words=expanded_word_count,
                    min_words=length_spec["min_words"],
                    length_preset=parent.requested_length,
                    max_words=length_spec["max_words"],
                )
            if expanded_word_count > length_spec["max_words"]:
                raise ExcessiveStoryLengthError(
                    actual_words=expanded_word_count,
                    max_words=length_spec["max_words"],
                    length_preset=parent.requested_length,
                    min_words=length_spec["min_words"],
                )
            payload = expanded_payload
            word_count = expanded_word_count

        elif word_count > length_spec["max_words"]:
            compression_messages = build_compression_prompt(
                current_title=payload.title or parent.title,
                current_content=payload.content,
                premise=f"Continuation pursuing '{chosen_choice.label}': {chosen_choice.description}. Original premise: {parent.premise}",
                atmosphere=parent.atmosphere,
                length=parent.requested_length,
                current_choices=[c.model_dump() for c in payload.branch_choices],
                sources=root_sources if parent.grounding_mode == "archive" else None,
            )
            compressed_raw = gen_client.generate_chat_completion(
                compression_messages,
                format_json=True,
                max_tokens=length_spec["max_tokens"],
            )
            compressed_payload = _parse_and_validate_payload(
                compressed_raw,
                gen_client,
                fallback_choices=payload.branch_choices,
            )
            compressed_word_count = len(compressed_payload.content.split())
            if compressed_word_count > length_spec["max_words"]:
                raise ExcessiveStoryLengthError(
                    actual_words=compressed_word_count,
                    max_words=length_spec["max_words"],
                    length_preset=parent.requested_length,
                    min_words=length_spec["min_words"],
                )
            if compressed_word_count < length_spec["min_words"]:
                raise InsufficientStoryLengthError(
                    actual_words=compressed_word_count,
                    min_words=length_spec["min_words"],
                    length_preset=parent.requested_length,
                    max_words=length_spec["max_words"],
                )
            payload = compressed_payload
            word_count = compressed_word_count

    # Create child story node
    child_title = payload.title.strip() if (payload.title and payload.title.strip()) else parent.title
    child = Story(
        title=child_title,
        premise=parent.premise,
        atmosphere=parent.atmosphere,
        requested_length=parent.requested_length,
        grounding_mode=parent.grounding_mode,
        body=payload.content.strip(),
        source_references=parent.source_references,
        parent_story_id=parent.id,
        branch_choice=chosen_choice.label,
        branch_choices=json.dumps([c.model_dump() for c in payload.branch_choices]),
        word_count=word_count,
        generation_model=gen_client.default_model,
        status="completed",
    )

    try:
        db.add(child)
        db.commit()
        db.refresh(child)
    except Exception:
        db.rollback()
        raise StoryEngineError("Failed to persist continuation story node to database.")

    return child


def get_full_narrative(story_id: str, db: Session) -> FullStoryNarrativeResponse:
    """Reconstruct complete branch narrative from the leaf node up to root."""
    leaf = db.query(Story).filter(Story.id == story_id).first()
    if not leaf:
        raise StoryNotFoundError(f"Story '{story_id}' not found.")

    chain: list[Story] = []
    curr: Optional[Story] = leaf
    while curr:
        chain.append(curr)
        if curr.parent_story_id:
            curr = db.query(Story).filter(Story.id == curr.parent_story_id).first()
        else:
            curr = None
    chain.reverse()

    segments: list[NarrativeSegment] = []
    total_words = 0
    full_paragraphs: list[str] = []

    for idx, node in enumerate(chain):
        w_count = node.word_count or len(node.body.split())
        total_words += w_count
        segments.append(
            NarrativeSegment(
                story_id=node.id,
                title=node.title,
                branch_label=node.branch_choice,
                content=node.body,
                word_count=w_count,
                created_at=node.created_at,
            )
        )
        if idx == 0:
            full_paragraphs.append(node.body)
        else:
            label_header = f"[{node.branch_choice}]" if node.branch_choice else f"[Chapter {idx + 1}]"
            full_paragraphs.append(f"{label_header}\n\n{node.body}")

    # Available choices at current leaf
    available_choices: list[BranchChoice] = []
    if leaf.branch_choices:
        try:
            available_choices = [BranchChoice.model_validate(c) for c in json.loads(leaf.branch_choices)]
        except Exception:
            available_choices = []

    # Sources from root
    sources: list[dict] = []
    if chain[0].source_references:
        try:
            sources = json.loads(chain[0].source_references)
        except Exception:
            sources = []

    return FullStoryNarrativeResponse(
        story_id=leaf.id,
        title=chain[0].title,
        premise=chain[0].premise,
        atmosphere=chain[0].atmosphere,
        grounding_mode=chain[0].grounding_mode,
        full_content="\n\n".join(full_paragraphs),
        total_word_count=total_words,
        segments=segments,
        available_choices=available_choices,
        source_references=sources,
    )


def get_story_branches(story_id: str, db: Session) -> StoryBranchesResponse:
    """Return available choices for this story and all child continuations already created."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise StoryNotFoundError(f"Story '{story_id}' not found.")

    available_choices: list[BranchChoice] = []
    if story.branch_choices:
        try:
            available_choices = [BranchChoice.model_validate(c) for c in json.loads(story.branch_choices)]
        except Exception:
            available_choices = []

    children = (
        db.query(Story)
        .filter(Story.parent_story_id == story_id)
        .order_by(Story.created_at.asc())
        .all()
    )

    child_nodes = [
        ChildBranchNode(
            story_id=c.id,
            branch_label=c.branch_choice,
            title=c.title,
            preview=c.body[:150].strip() + ("..." if len(c.body) > 150 else ""),
            created_at=c.created_at,
        )
        for c in children
    ]

    return StoryBranchesResponse(
        story_id=story.id,
        title=story.title,
        available_choices=available_choices,
        child_branches=child_nodes,
    )

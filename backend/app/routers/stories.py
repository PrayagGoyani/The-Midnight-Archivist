"""Story management and generation endpoints."""
from __future__ import annotations

import json
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..models import Story
from ..schemas import (
    BranchChoice,
    ErrorResponse,
    FullStoryNarrativeResponse,
    StoryBranchesResponse,
    StoryContinueRequest,
    StoryCreate,
    StoryGenerateRequest,
    StoryGenerationResponse,
    StoryListResponse,
    StoryOut,
)
from ..services.ollama_generation import (
    OllamaConnectionError,
    OllamaGenerationError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
)
from ..services.story_engine import (
    ExcessiveStoryLengthError,
    InsufficientArchiveContextError,
    InsufficientStoryLengthError,
    InvalidBranchChoiceError,
    StoryEngineError,
    StoryLengthOutOfBoundsError,
    StoryNotFoundError,
    StoryValidationError,
    continue_story,
    generate_story,
    get_full_narrative,
    get_story_branches,
)

router = APIRouter(prefix="/stories", tags=["stories"])


def _story_to_generation_response(story: Story) -> StoryGenerationResponse:
    """Format a Story ORM model into a rich StoryGenerationResponse."""
    choices = []
    if story.branch_choices:
        try:
            choices = [
                BranchChoice.model_validate(c) for c in json.loads(story.branch_choices)
            ]
        except Exception:
            choices = []

    sources = []
    if story.source_references:
        try:
            sources = json.loads(story.source_references)
        except Exception:
            sources = []

    return StoryGenerationResponse(
        id=story.id,
        title=story.title,
        content=story.body,
        body=story.body,
        premise=story.premise,
        atmosphere=story.atmosphere,
        requested_length=story.requested_length,
        grounding_mode=story.grounding_mode,
        branch_choices=choices,
        source_references=sources,
        parent_story_id=story.parent_story_id,
        branch_choice=story.branch_choice,
        word_count=story.word_count or len(story.body.split()),
        generation_model=story.generation_model or "unknown",
        status=story.status,
        created_at=story.created_at,
    )


# ── Story Generation & Continuation Endpoints (Must precede dynamic /{story_id}) ──

@router.post(
    "/generate",
    response_model=StoryGenerationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
def api_generate_story(
    payload: StoryGenerateRequest, db: Session = Depends(get_db)
) -> StoryGenerationResponse:
    """Generate a new atmospheric story in archive-grounded or freeform mode."""
    try:
        story = generate_story(
            db,
            premise=payload.premise,
            atmosphere=payload.atmosphere,
            length=payload.length,
            grounding_mode=payload.grounding_mode,
            document_ids=payload.document_ids,
            top_k=payload.top_k,
        )
    except InsufficientArchiveContextError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except (InsufficientStoryLengthError, ExcessiveStoryLengthError, StoryLengthOutOfBoundsError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except StoryValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except StoryEngineError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except OllamaConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except OllamaModelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except OllamaTimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc))
    except OllamaGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return _story_to_generation_response(story)


@router.post(
    "/{story_id}/continue",
    response_model=StoryGenerationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
def api_continue_story(
    story_id: str,
    payload: StoryContinueRequest,
    db: Session = Depends(get_db),
) -> StoryGenerationResponse:
    """Generate a coherent narrative continuation from an existing story branch."""
    try:
        child_story = continue_story(story_id, payload.choice_id, db)
    except StoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidBranchChoiceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except (InsufficientStoryLengthError, ExcessiveStoryLengthError, StoryLengthOutOfBoundsError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except StoryValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except StoryEngineError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except OllamaConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except OllamaModelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except OllamaTimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc))
    except OllamaGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return _story_to_generation_response(child_story)


@router.get(
    "/{story_id}/full",
    response_model=FullStoryNarrativeResponse,
    responses={404: {"model": ErrorResponse}},
)
def api_get_full_narrative(
    story_id: str, db: Session = Depends(get_db)
) -> FullStoryNarrativeResponse:
    """Reconstruct the complete narrative branch from the leaf node back to root."""
    try:
        return get_full_narrative(story_id, db)
    except StoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/{story_id}/branches",
    response_model=StoryBranchesResponse,
    responses={404: {"model": ErrorResponse}},
)
def api_get_story_branches(
    story_id: str, db: Session = Depends(get_db)
) -> StoryBranchesResponse:
    """Retrieve available choices and active child branches for this story node."""
    try:
        return get_story_branches(story_id, db)
    except StoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ── Story Management CRUD Endpoints ─────────────────────────────────

@router.get("", response_model=StoryListResponse)
def list_stories(db: Session = Depends(get_db)) -> StoryListResponse:
    """List all saved stories, newest first."""
    stories = db.query(Story).order_by(Story.created_at.desc()).all()
    return StoryListResponse(
        stories=[StoryOut.model_validate(s) for s in stories],
        total=len(stories),
    )


@router.post(
    "",
    response_model=StoryOut,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def create_story(
    payload: StoryCreate, db: Session = Depends(get_db)
) -> StoryOut:
    """Save a completed story manually."""
    # Validate parent reference if provided
    if payload.parent_story_id:
        parent = (
            db.query(Story).filter(Story.id == payload.parent_story_id).first()
        )
        if not parent:
            raise HTTPException(
                status_code=404,
                detail=f"Parent story '{payload.parent_story_id}' not found.",
            )

    w_count = payload.word_count or len(payload.body.split())
    story = Story(
        title=payload.title,
        premise=payload.premise,
        atmosphere=payload.atmosphere,
        requested_length=payload.requested_length,
        grounding_mode=payload.grounding_mode,
        body=payload.body,
        source_references=payload.source_references,
        parent_story_id=payload.parent_story_id,
        branch_choice=payload.branch_choice,
        branch_choices=payload.branch_choices or "[]",
        word_count=w_count,
        generation_model=payload.generation_model or "manual",
        status=payload.status or "completed",
    )
    try:
        db.add(story)
        db.commit()
        db.refresh(story)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save story.")

    return StoryOut.model_validate(story)


@router.get(
    "/{story_id}",
    response_model=StoryOut,
    responses={404: {"model": ErrorResponse}},
)
def get_story(story_id: str, db: Session = Depends(get_db)) -> StoryOut:
    """Retrieve a saved story."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found.")
    return StoryOut.model_validate(story)


@router.delete(
    "/{story_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={404: {"model": ErrorResponse}},
)
def delete_story(story_id: str, db: Session = Depends(get_db)) -> Response:
    """Delete a saved story."""
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found.")
    try:
        db.delete(story)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete story.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


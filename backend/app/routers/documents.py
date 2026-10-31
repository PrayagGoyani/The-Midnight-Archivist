"""Document management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response, status
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..config import settings
from ..models import Chunk, Document
from ..schemas import (
    ChunkListResponse,
    ChunkOut,
    DocumentListResponse,
    DocumentOut,
    ErrorResponse,
    ProcessingResponse,
)
from ..services.file_storage import (
    delete_file,
    generate_stored_filename,
    save_upload,
    validate_extension,
)
from ..services.document_parser import ExtractionError
from ..services.indexing import (
    DocumentFileNotFoundError,
    DocumentNotFoundError,
    process_document,
)
from ..services.ollama_client import (
    OllamaConnectionError,
    OllamaEmbeddingError,
    OllamaModelError,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
def list_documents(db: Session = Depends(get_db)) -> DocumentListResponse:
    """List all documents, newest first."""
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return DocumentListResponse(
        documents=[DocumentOut.model_validate(d) for d in docs],
        total=len(docs),
    )


@router.post(
    "",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentOut:
    """Upload a PDF, TXT, or Markdown document."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    # Validate extension
    try:
        ext, content_type = validate_extension(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Read content and validate size
    content = await file.read()

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    max_bytes = settings.upload_max_bytes
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {settings.upload_max_size_mb} MB.",
        )

    # Generate safe storage name
    stored_name = generate_stored_filename(file.filename, ext)

    # Derive title from filename
    title = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename

    # Write to disk
    try:
        save_upload(content, stored_name)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save uploaded file: {e}",
        )

    # Persist metadata
    doc = Document(
        title=title,
        original_filename=file.filename,
        stored_filename=stored_name,
        file_extension=ext,
        content_type=content_type,
        file_size=len(content),
        status="uploaded",
    )
    try:
        db.add(doc)
        db.commit()
        db.refresh(doc)
    except Exception:
        db.rollback()
        # Clean up the saved file
        delete_file(stored_name)
        raise HTTPException(status_code=500, detail="Failed to save document metadata.")

    return DocumentOut.model_validate(doc)


@router.get(
    "/{document_id}",
    response_model=DocumentOut,
    responses={404: {"model": ErrorResponse}},
)
def get_document(document_id: str, db: Session = Depends(get_db)) -> DocumentOut:
    """Retrieve metadata for a single document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentOut.model_validate(doc)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={404: {"model": ErrorResponse}},
)
def delete_document(document_id: str, db: Session = Depends(get_db)) -> Response:
    """Delete a document, its chunks, and its stored file."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    stored_name = doc.stored_filename

    try:
        db.delete(doc)  # Cascades to chunks
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete document record.")

    # Remove file from disk (best-effort after DB commit)
    try:
        delete_file(stored_name)
    except Exception:
        pass  # File may already be gone; DB record is authoritative

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{document_id}/process",
    response_model=ProcessingResponse,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def process_doc_endpoint(
    document_id: str,
    db: Session = Depends(get_db),
) -> ProcessingResponse:
    """Extract text, create chunks, generate embeddings, and index a document."""
    try:
        result = process_document(document_id, db)
        return ProcessingResponse(
            document_id=result.document_id,
            title=result.title,
            status=result.status,
            chunk_count=result.chunk_count,
            embedding_model=result.embedding_model,
            dimensions=result.dimensions,
            indexed_at=result.indexed_at,
        )
    except (DocumentNotFoundError, DocumentFileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ExtractionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except (OllamaConnectionError, OllamaModelError) as e:
        raise HTTPException(status_code=503, detail=str(e))
    except OllamaEmbeddingError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")


@router.get(
    "/{document_id}/chunks",
    response_model=ChunkListResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_document_chunks(
    document_id: str,
    db: Session = Depends(get_db),
) -> ChunkListResponse:
    """Retrieve all chunks for a document, ordered by reading sequence."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    chunks = (
        db.query(Chunk)
        .filter(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index.asc())
        .all()
    )

    return ChunkListResponse(
        chunks=[ChunkOut.model_validate(c) for c in chunks],
        total=len(chunks),
        document_id=document_id,
    )

"""
Document Raw Content & Offset API
===================================
Endpoints:
  GET  /documents/{document_id}/raw           - stream full doc with line numbers + section headers
  POST /documents/{document_id}/locate-excerpt - find char/line offsets of a cited excerpt
"""

from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Query, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os, shutil
from pathlib import Path
from pydantic import BaseModel, Field

from app.schemas.document import DocumentResponse, DocumentDetailResponse
from app.models.entities import DocTypeEnum, DocStatusEnum, Document
from app.core.database import get_db
from app.services.ingestion import process_document_pipeline
from app.services.offset_locator import (
    annotate_document_lines,
    locate_excerpt_offsets,
    build_line_index,
)
from app.core.logging import logger

router = APIRouter(prefix="/documents", tags=["Documents"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Mock data (kept for compatibility)
# ---------------------------------------------------------------------------

MOCK_DOCUMENTS = [
    DocumentResponse(
        id=str(uuid.uuid4()),
        workspace_id=str(uuid.uuid4()),
        title="Authentication API v2",
        source_filename="auth_v2.md",
        source_url="https://api.example.com/v2/auth",
        doc_type=DocTypeEnum.API_REFERENCE,
        version_tag="v2.0",
        doc_metadata={"tags": ["auth", "v2"]},
        status=DocStatusEnum.INDEXED,
        total_chunks=15,
        file_size_bytes=10240,
        created_at=utc_now(),
        updated_at=utc_now(),
        synced_at=utc_now()
    ),
    DocumentResponse(
        id=str(uuid.uuid4()),
        workspace_id=str(uuid.uuid4()),
        title="Migration Guide to v2",
        source_filename="migration.md",
        source_url=None,
        doc_type=DocTypeEnum.MIGRATION_GUIDE,
        version_tag="v2.0",
        doc_metadata={},
        status=DocStatusEnum.INDEXED,
        total_chunks=8,
        file_size_bytes=4096,
        created_at=utc_now(),
        updated_at=utc_now(),
        synced_at=utc_now()
    )
]


# ---------------------------------------------------------------------------
# Existing list / get / upload endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    version: Optional[str] = Query(None, description="Filter by version tag"),
    doc_type: Optional[DocTypeEnum] = Query(None, description="Filter by document type"),
    workspace_id: Optional[str] = Query(None, description="Filter by workspace ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """List documents with optional filtering by version and type."""
    results = MOCK_DOCUMENTS
    if version:
        results = [d for d in results if d.version_tag == version]
    if doc_type:
        results = [d for d in results if d.doc_type == doc_type]
    if workspace_id:
        results = [d for d in results if d.workspace_id == workspace_id]
    return results[skip: skip + limit]


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(document_id: str):
    """Get a specific document's details."""
    doc = next((d for d in MOCK_DOCUMENTS if d.id == document_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentDetailResponse(**doc.model_dump(), chunks=[], raw_content="Mock content for the document...")


UPLOAD_DIR = Path("data/uploads")


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    workspace_id: str = Form(...),
    doc_type: DocTypeEnum = Form(DocTypeEnum.API_REFERENCE),
    version_tag: str = Form("latest"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Upload a documentation file (.md, .json, .yaml, .pdf)."""
    allowed_extensions = {".md", ".json", ".yaml", ".pdf"}
    file_ext = Path(file.filename).suffix.lower() if file.filename else ""
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{file_ext}'. Allowed: {', '.join(allowed_extensions)}"
        )
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    file_size = os.path.getsize(file_path)
    new_doc = Document(
        id=file_id,
        workspace_id=workspace_id,
        title=file.filename,
        source_filename=file.filename,
        file_path=str(file_path),
        file_size_bytes=file_size,
        doc_type=doc_type,
        version_tag=version_tag,
        status=DocStatusEnum.PENDING,
        total_chunks=0,
        created_at=utc_now(),
        updated_at=utc_now()
    )
    db.add(new_doc)
    await db.commit()
    await db.refresh(new_doc)
    if background_tasks:
        background_tasks.add_task(process_document_pipeline, new_doc.id)
    return new_doc


# ---------------------------------------------------------------------------
# NEW: GET /documents/{document_id}/raw
# ---------------------------------------------------------------------------

@router.get(
    "/{document_id}/raw",
    summary="Stream full raw document content with line numbers and section headers",
    description=(
        "Returns the original document content annotated with line numbers and "
        "Markdown section headers for in-browser inspection. "
        "Supports optional line-range filtering via `start_line` / `end_line`."
    ),
    response_model=Dict[str, Any],
)
async def get_document_raw(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    start_line: Optional[int] = Query(None, ge=1, description="First line to return (1-indexed)"),
    end_line: Optional[int] = Query(None, ge=1, description="Last line to return (inclusive)"),
    include_section_headers: bool = Query(True, description="Annotate each line with the current section heading"),
):
    """
    GET /api/v1/documents/{document_id}/raw

    Returns:
    ```json
    {
      "document_id": "...",
      "title": "...",
      "version_tag": "...",
      "doc_type": "...",
      "total_lines": 412,
      "lines": [
        {"line_number": 1, "content": "# Authentication", "section_header": "Authentication"},
        {"line_number": 2, "content": "", "section_header": "Authentication"},
        ...
      ]
    }
    ```
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc: Optional[Document] = result.scalar_one_or_none()

    raw_content: Optional[str] = None
    title = "Unknown"
    version_tag = "latest"
    doc_type = "API_REFERENCE"

    if doc:
        raw_content = doc.raw_content
        title = doc.title
        version_tag = doc.version_tag
        doc_type = doc.doc_type.value if hasattr(doc.doc_type, "value") else str(doc.doc_type)

        # If raw_content not stored, attempt to read from disk
        if not raw_content and doc.file_path and os.path.exists(doc.file_path):
            try:
                with open(doc.file_path, "r", encoding="utf-8", errors="replace") as f:
                    raw_content = f.read()
            except Exception as e:
                logger.warning(f"Could not read file for doc {document_id}: {e}")
    else:
        # Fallback: look for mock
        mock = next((d for d in MOCK_DOCUMENTS if d.id == document_id), None)
        if not mock:
            raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
        raw_content = "# Mock Document\n\nThis is a mock document used for demonstration.\n\n## Section 1\n\nContent here."
        title = mock.title
        version_tag = mock.version_tag
        doc_type = mock.doc_type.value

    if not raw_content:
        raw_content = ""

    annotated = await run_in_threadpool(annotate_document_lines, raw_content)
    total_lines = len(annotated)

    # Apply line range filter
    sl = (start_line or 1) - 1
    el = (end_line or total_lines)
    annotated = annotated[sl:el]

    if not include_section_headers:
        for line in annotated:
            line.pop("section_header", None)

    return {
        "document_id": document_id,
        "title": title,
        "version_tag": version_tag,
        "doc_type": doc_type,
        "total_lines": total_lines,
        "returned_lines": len(annotated),
        "start_line": sl + 1,
        "end_line": min(el, total_lines),
        "lines": annotated,
    }


# ---------------------------------------------------------------------------
# NEW: POST /documents/{document_id}/locate-excerpt
# ---------------------------------------------------------------------------

class LocateExcerptRequest(BaseModel):
    excerpt: str = Field(..., min_length=1, description="The cited chunk text or excerpt to locate")
    min_fuzzy_ratio: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Minimum similarity ratio for fuzzy matching (0.0-1.0)"
    )


@router.post(
    "/{document_id}/locate-excerpt",
    summary="Find exact character and line offsets of a cited excerpt",
    description=(
        "Given a chunk excerpt (as cited in an LLM response), locates its exact character "
        "start/end positions and line numbers within the raw source document. "
        "Tries exact substring match first, then falls back to fuzzy matching."
    ),
    response_model=Dict[str, Any],
)
async def locate_excerpt(
    document_id: str,
    request: LocateExcerptRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    POST /api/v1/documents/{document_id}/locate-excerpt

    Request body:
    ```json
    { "excerpt": "Bearer token in the Authorization header", "min_fuzzy_ratio": 0.75 }
    ```

    Response:
    ```json
    {
      "found": true,
      "method": "exact",
      "start_char": 142,
      "end_char": 185,
      "start_line": 8,
      "end_line": 8,
      "match_ratio": 1.0,
      "matched_text": "Bearer token in the Authorization header"
    }
    ```
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc: Optional[Document] = result.scalar_one_or_none()

    raw_content: Optional[str] = None
    if doc:
        raw_content = doc.raw_content
        if not raw_content and doc.file_path and os.path.exists(doc.file_path):
            try:
                with open(doc.file_path, "r", encoding="utf-8", errors="replace") as f:
                    raw_content = f.read()
            except Exception:
                pass
    else:
        mock = next((d for d in MOCK_DOCUMENTS if d.id == document_id), None)
        if not mock:
            raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
        raw_content = "# Mock Document\n\nThis is a mock document used for demonstration.\n\n## Section 1\n\nContent here."

    if not raw_content:
        raise HTTPException(status_code=422, detail="Document has no raw content stored")

    location = await run_in_threadpool(
        locate_excerpt_offsets,
        raw_content,
        request.excerpt,
        request.min_fuzzy_ratio,
    )
    location["document_id"] = document_id
    location["excerpt_queried"] = request.excerpt
    return location

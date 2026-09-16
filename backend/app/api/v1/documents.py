from typing import List, Optional
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Query, HTTPException

from app.schemas.document import DocumentResponse, DocumentDetailResponse
from app.models.entities import DocTypeEnum, DocStatusEnum

router = APIRouter(prefix="/documents", tags=["Documents"])

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

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

@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    version: Optional[str] = Query(None, description="Filter by version tag"),
    doc_type: Optional[DocTypeEnum] = Query(None, description="Filter by document type"),
    workspace_id: Optional[str] = Query(None, description="Filter by workspace ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """
    List documents with optional filtering by version and type.
    """
    results = MOCK_DOCUMENTS
    if version:
        results = [d for d in results if d.version_tag == version]
    if doc_type:
        results = [d for d in results if d.doc_type == doc_type]
    if workspace_id:
        results = [d for d in results if d.workspace_id == workspace_id]
        
    return results[skip:skip+limit]

@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(document_id: str):
    """
    Get a specific document's details.
    """
    doc = next((d for d in MOCK_DOCUMENTS if d.id == document_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return DocumentDetailResponse(
        **doc.model_dump(),
        chunks=[],
        raw_content="Mock content for the document..."
    )

from typing import List, Optional
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Query, HTTPException, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
import os
import shutil
from pathlib import Path

from app.schemas.document import DocumentResponse, DocumentDetailResponse
from app.models.entities import DocTypeEnum, DocStatusEnum, Document
from app.core.database import get_db

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

UPLOAD_DIR = Path("data/uploads")

@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    workspace_id: str = Form(...),
    doc_type: DocTypeEnum = Form(DocTypeEnum.API_REFERENCE),
    version_tag: str = Form("latest"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a documentation file (.md, .json, .yaml, .pdf), save locally,
    and create a PENDING record in the database.
    """
    allowed_extensions = {".md", ".json", ".yaml", ".pdf"}
    file_ext = Path(file.filename).suffix.lower() if file.filename else ""
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file extension '{file_ext}'. Allowed: {', '.join(allowed_extensions)}"
        )

    # Ensure upload directory exists
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save file
    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    file_size = os.path.getsize(file_path)

    # Create pending record in database
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
    
    return new_doc

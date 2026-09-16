from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.models.entities import DocTypeEnum, DocStatusEnum
from app.schemas.chunk import ChunkResponse


class DocumentBase(BaseModel):
    title: str = Field(..., max_length=255, example="Authentication API Reference")
    source_filename: str = Field(..., max_length=255, example="auth_api_v2.md")
    source_url: Optional[str] = Field(None, example="https://docs.example.com/v2/auth")
    doc_type: DocTypeEnum = Field(DocTypeEnum.API_REFERENCE, example=DocTypeEnum.API_REFERENCE)
    version_tag: str = Field("latest", max_length=50, example="v2.0")
    doc_metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentCreate(DocumentBase):
    workspace_id: str
    raw_content: Optional[str] = None
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = 0


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    doc_type: Optional[DocTypeEnum] = None
    version_tag: Optional[str] = Field(None, max_length=50)
    status: Optional[DocStatusEnum] = None
    error_message: Optional[str] = None
    doc_metadata: Optional[Dict[str, Any]] = None


class DocumentResponse(DocumentBase):
    id: str
    workspace_id: str
    status: DocStatusEnum
    error_message: Optional[str] = None
    total_chunks: int
    file_size_bytes: Optional[int] = 0
    created_at: datetime
    updated_at: datetime
    synced_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentResponse):
    chunks: List[ChunkResponse] = []
    raw_content: Optional[str] = None

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.models.entities import DocTypeEnum


class ChunkBase(BaseModel):
    chunk_index: int
    content: str
    embedding_id: str
    section_header: Optional[str] = None
    section_level: Optional[int] = 1
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    start_char_offset: Optional[int] = None
    end_char_offset: Optional[int] = None
    token_count: Optional[int] = 0
    version_tag: str
    doc_type: DocTypeEnum
    chunk_metadata: Dict[str, Any] = Field(default_factory=dict)


class ChunkCreate(ChunkBase):
    document_id: str


class ChunkResponse(ChunkBase):
    id: str
    document_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CitationDetail(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    version: str
    doc_type: DocTypeEnum
    section_header: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    excerpt: str
    full_chunk_text: Optional[str] = None
    surrounding_context: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)

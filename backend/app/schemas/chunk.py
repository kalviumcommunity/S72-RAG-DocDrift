from datetime import datetime
from typing import Optional, Dict, Any, List
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


class SurroundingChunk(BaseModel):
    """Lightweight descriptor for a neighbouring chunk (±N lines of context)."""
    chunk_id: str
    chunk_index: Optional[int] = None
    section_header: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    version_tag: Optional[str] = None
    content: str = Field(..., description="Full text of the neighbouring chunk")


class ChunkContextResponse(BaseModel):
    """
    Full context payload returned by GET /api/v1/citations/{chunk_id}.
    Carries the chunk's own text plus ±window surrounding chunks and
    parent document provenance.
    """
    chunk_id: str = Field(..., description="Unique ID of the requested chunk")
    content: str = Field(..., description="Full raw text of the chunk")
    section_header: Optional[str] = Field(None, description="Section heading this chunk belongs to")
    section_level: Optional[int] = Field(None, description="Heading depth (1 = top-level)")
    start_line: Optional[int] = Field(None, description="First line of the chunk in the source file")
    end_line: Optional[int] = Field(None, description="Last line of the chunk in the source file")
    chunk_index: Optional[int] = Field(None, description="Zero-based ordinal position within the document")
    token_count: Optional[int] = Field(None, description="Approximate token count")

    # Parent document details
    document_id: str = Field(..., description="ID of the parent document")
    document_title: str = Field(..., description="Human-readable document title / filename")
    version: str = Field(..., description="API/doc version tag (e.g. 'v2.0')")
    doc_type: str = Field(..., description="Document category (e.g. 'API_REFERENCE')")
    source_url: Optional[str] = Field(None, description="Canonical URL of the source document")
    is_deprecated: bool = Field(False, description="Whether this chunk's version is deprecated")

    # Surrounding context (±window chunks from the same document)
    surrounding_chunks_before: List[SurroundingChunk] = Field(
        default_factory=list,
        description="Up to N chunks immediately preceding this one in the document",
    )
    surrounding_chunks_after: List[SurroundingChunk] = Field(
        default_factory=list,
        description="Up to N chunks immediately following this one in the document",
    )

    # Raw metadata passthrough
    raw_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="All stored ChromaDB metadata fields for this chunk",
    )

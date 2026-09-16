import enum
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import (
    String, Text, Integer, Boolean, ForeignKey, DateTime, Enum as SQLEnum, JSON, Float
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class DocTypeEnum(str, enum.Enum):
    API_REFERENCE = "API_REFERENCE"
    CHANGELOG = "CHANGELOG"
    MIGRATION_GUIDE = "MIGRATION_GUIDE"
    TUTORIAL = "TUTORIAL"
    CONCEPT_GUIDE = "CONCEPT_GUIDE"
    OTHER = "OTHER"


class DocStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    PARSING = "PARSING"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class MessageRoleEnum(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_version: Mapped[str] = mapped_column(String(50), default="latest", nullable=False)
    
    # Store settings like LLM provider, custom embedding dimensions, etc.
    settings: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="workspace", cascade="all, delete-orphan")
    chat_sessions: Mapped[List["ChatSession"]] = relationship("ChatSession", back_populates="workspace", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False)
    
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    
    # Versioning & Categorization
    doc_type: Mapped[DocTypeEnum] = mapped_column(SQLEnum(DocTypeEnum), default=DocTypeEnum.API_REFERENCE, index=True, nullable=False)
    version_tag: Mapped[str] = mapped_column(String(50), default="latest", index=True, nullable=False)
    
    # Ingestion Status
    status: Mapped[DocStatusEnum] = mapped_column(SQLEnum(DocStatusEnum), default=DocStatusEnum.PENDING, index=True, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Extra metadata (OpenAPI endpoints, tags, etc.)
    doc_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="documents")
    chunks: Mapped[List["DocumentChunk"]] = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    
    # Section hierarchy & line offsets for exact Citation Inspector highlighting
    section_header: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    section_level: Mapped[Optional[int]] = mapped_column(Integer, default=1)
    start_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_char_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_char_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    
    # Version and Type duplicate for fast SQL filtering without joins
    version_tag: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    doc_type: Mapped[DocTypeEnum] = mapped_column(SQLEnum(DocTypeEnum), index=True, nullable=False)
    
    chunk_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Relationship
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False)
    
    title: Mapped[str] = mapped_column(String(255), default="New Documentation Session", nullable=False)
    selected_version: Mapped[str] = mapped_column(String(50), default="latest", nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="chat_sessions")
    messages: Mapped[List["ChatMessage"]] = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    
    role: Mapped[MessageRoleEnum] = mapped_column(SQLEnum(MessageRoleEnum), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Grounded citations list: [{ "chunk_id": "...", "doc_title": "...", "version": "...", "section": "...", "excerpt": "...", "confidence": 0.95 }]
    citations: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    
    # Query intent analysis: { "target_versions": ["v1.0", "v2.0"], "is_comparison": true, "detected_endpoints": [] }
    query_analysis: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    
    # Optional feedback (1 for positive, -1 for negative)
    feedback_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Relationship
    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.models.entities import MessageRoleEnum
from app.schemas.chunk import CitationDetail


class ChatMessageCreate(BaseModel):
    content: str = Field(..., examples=["How do I authenticate with Bearer tokens in v2?"])
    selected_version: Optional[str] = Field(None, examples=["v2.0"])


class ChatMessageResponse(BaseModel):
    id: str
    session_id: str
    role: MessageRoleEnum
    content: str
    citations: List[Dict[str, Any]] = Field(default_factory=list, description="Array of grounded citation objects")
    query_analysis: Dict[str, Any] = Field(default_factory=dict)
    feedback_score: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionCreate(BaseModel):
    workspace_id: str
    title: Optional[str] = Field("New Session", examples=["OAuth Flow Question"])
    selected_version: str = Field("latest", examples=["v2.0"])


class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None
    selected_version: Optional[str] = None


class ChatSessionResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    selected_version: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageResponse] = []

    model_config = ConfigDict(from_attributes=True)


class StreamTokenChunk(BaseModel):
    token: Optional[str] = None
    citation: Optional[CitationDetail] = None
    finish_reason: Optional[str] = None


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The developer question or prompt")
    selected_version: Optional[str] = Field(None, description="Active API version tag (e.g. v2.0)")
    context_chunks: Optional[List[Dict[str, Any]]] = Field(None, description="Optional pre-retrieved context chunks")
    top_k: int = Field(5, ge=1, le=20, description="Number of vector chunks to retrieve if not provided")
    score_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Similarity threshold for vector retrieval")
    use_langchain: bool = Field(True, description="Whether to use LangChain pipeline if available")


class RAGQueryResponse(BaseModel):
    query: str = Field(..., description="The original user query")
    answer: str = Field(..., description="Generated answer with inline [^chunk_id] citation tags")
    citations: List[CitationDetail] = Field(default_factory=list, description="Extracted citation metadata objects")
    cited_chunk_ids: List[str] = Field(default_factory=list, description="List of chunk IDs referenced in the response")
    query_analysis: Dict[str, Any] = Field(default_factory=dict, description="Query intent analysis results")
    is_grounded: bool = Field(True, description="Whether all citations correspond to provided context chunks")
    faithfulness_score: Optional[float] = Field(None, ge=0.0, le=100.0, description="Faithfulness percentage score (0.0 - 100.0%)")
    pipeline_mode: str = Field("gemini", description="Pipeline executed: 'langchain', 'gemini', or 'fallback'")


from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.models.entities import MessageRoleEnum
from app.schemas.chunk import CitationDetail


class ChatMessageCreate(BaseModel):
    content: str = Field(..., example="How do I authenticate with Bearer tokens in v2?")
    selected_version: Optional[str] = Field(None, example="v2.0")


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
    title: Optional[str] = Field("New Session", example="OAuth Flow Question")
    selected_version: str = Field("latest", example="v2.0")


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

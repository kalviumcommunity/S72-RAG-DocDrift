from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class WorkspaceBase(BaseModel):
    name: str = Field(..., max_length=100, example="My API Documentation")
    slug: str = Field(..., max_length=100, example="my-api-docs")
    description: Optional[str] = Field(None, example="Documentation workspace for v1 and v2 APIs")
    default_version: str = Field("latest", max_length=50, example="v2.0")
    settings: Dict[str, Any] = Field(default_factory=dict)


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    slug: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    default_version: Optional[str] = Field(None, max_length=50)
    settings: Optional[Dict[str, Any]] = None


class WorkspaceResponse(WorkspaceBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

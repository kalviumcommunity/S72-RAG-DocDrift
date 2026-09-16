from typing import List
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, HTTPException

from app.schemas.workspace import WorkspaceResponse, WorkspaceCreate, WorkspaceUpdate

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

MOCK_WORKSPACES = [
    WorkspaceResponse(
        id=str(uuid.uuid4()),
        name="Developer Portal Docs",
        slug="dev-portal-docs",
        description="Main workspace for all API documentation",
        default_version="v2.0",
        settings={"llm_provider": "openai", "embedding_model": "text-embedding-3-small"},
        created_at=utc_now(),
        updated_at=utc_now()
    )
]

@router.get("", response_model=List[WorkspaceResponse])
async def list_workspaces():
    """
    List all workspaces.
    """
    return MOCK_WORKSPACES

@router.post("", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(workspace_in: WorkspaceCreate):
    """
    Create a new workspace with settings.
    """
    new_workspace = WorkspaceResponse(
        id=str(uuid.uuid4()),
        name=workspace_in.name,
        slug=workspace_in.slug,
        description=workspace_in.description,
        default_version=workspace_in.default_version,
        settings=workspace_in.settings,
        created_at=utc_now(),
        updated_at=utc_now()
    )
    MOCK_WORKSPACES.append(new_workspace)
    return new_workspace

@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str):
    """
    Get a specific workspace by ID.
    """
    workspace = next((w for w in MOCK_WORKSPACES if w.id == workspace_id), None)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace

@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(workspace_id: str, workspace_in: WorkspaceUpdate):
    """
    Update workspace settings management.
    """
    workspace = next((w for w in MOCK_WORKSPACES if w.id == workspace_id), None)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
        
    update_data = workspace_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(workspace, key, value)
        
    workspace.updated_at = utc_now()
    return workspace

@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(workspace_id: str):
    """
    Delete a workspace.
    """
    global MOCK_WORKSPACES
    workspace = next((w for w in MOCK_WORKSPACES if w.id == workspace_id), None)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
        
    MOCK_WORKSPACES = [w for w in MOCK_WORKSPACES if w.id != workspace_id]

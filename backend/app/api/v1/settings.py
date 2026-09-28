"""
Settings API
=============
GET  /settings                          — get global application settings
PUT  /settings                          — update global settings (admin)
GET  /settings/workspaces/{id}          — get workspace-specific settings
PUT  /settings/workspaces/{id}          — update workspace settings
POST /settings/workspaces/{id}/members  — add/remove workspace members
"""

from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Body
from app.schemas.settings import (
    WorkspaceSettings,
    WorkspaceSettingsUpdate,
    WorkspaceSettingsResponse,
    GlobalSettingsUpdate,
    GlobalSettingsResponse,
    LLMProviderConfig,
    EmbeddingConfig,
    ChunkingConfig,
)
from app.core.config import settings as app_settings
from app.core.logging import logger

router = APIRouter(prefix="/settings", tags=["Settings"])

# ---------------------------------------------------------------------------
# In-memory store (replace with DB persistence when ready)
# ---------------------------------------------------------------------------
_global_settings: Dict[str, Any] = {
    "default_llm_provider":        app_settings.EMBEDDING_PROVIDER,
    "default_embedding_provider":  app_settings.EMBEDDING_PROVIDER,
    "gemini_api_key":              app_settings.GEMINI_API_KEY or "",
    "openai_api_key":              app_settings.OPENAI_API_KEY or "",
    "rate_limit_per_minute":       60,
}

_workspace_settings: Dict[str, WorkspaceSettings] = {}


def _redact_key(key: str) -> bool:
    return bool(key and key.strip())


# ---------------------------------------------------------------------------
# Global settings endpoints
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=GlobalSettingsResponse,
    summary="Get global application settings",
)
async def get_global_settings() -> GlobalSettingsResponse:
    """Returns global server-level settings with API keys redacted."""
    return GlobalSettingsResponse(
        default_llm_provider=_global_settings["default_llm_provider"],
        default_embedding_provider=_global_settings["default_embedding_provider"],
        gemini_api_key_set=_redact_key(_global_settings.get("gemini_api_key", "")),
        openai_api_key_set=_redact_key(_global_settings.get("openai_api_key", "")),
        rate_limit_per_minute=_global_settings.get("rate_limit_per_minute", 60),
    )


@router.put(
    "",
    response_model=GlobalSettingsResponse,
    summary="Update global application settings (admin)",
)
async def update_global_settings(update: GlobalSettingsUpdate) -> GlobalSettingsResponse:
    """
    Updates global server settings. API keys are stored but never returned.
    Validates that provider values are supported before saving.
    """
    valid_providers = {"gemini", "openai", "anthropic", "local"}

    if update.default_llm_provider and update.default_llm_provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported LLM provider '{update.default_llm_provider}'. Choose from: {valid_providers}",
        )
    if update.default_embedding_provider and update.default_embedding_provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported embedding provider. Choose from: {valid_providers}",
        )

    patch = update.model_dump(exclude_none=True)
    _global_settings.update(patch)
    logger.info(f"Global settings updated: {list(patch.keys())}")
    return await get_global_settings()


# ---------------------------------------------------------------------------
# Workspace-level settings endpoints
# ---------------------------------------------------------------------------

def _get_or_create_workspace_settings(workspace_id: str) -> WorkspaceSettings:
    if workspace_id not in _workspace_settings:
        _workspace_settings[workspace_id] = WorkspaceSettings()
    return _workspace_settings[workspace_id]


@router.get(
    "/workspaces/{workspace_id}",
    response_model=WorkspaceSettingsResponse,
    summary="Get workspace-specific settings",
)
async def get_workspace_settings(workspace_id: str) -> WorkspaceSettingsResponse:
    """
    Returns all configuration for the specified workspace.
    LLM and embedding API keys are redacted (shows only whether a key has been set).
    """
    ws = _get_or_create_workspace_settings(workspace_id)
    return WorkspaceSettingsResponse(
        workspace_id=workspace_id,
        llm_provider=ws.llm.provider,
        llm_model=ws.llm.model_name,
        llm_api_key_set=_redact_key(ws.llm.api_key or ""),
        embedding_provider=ws.embedding.provider,
        embedding_model=ws.embedding.model_name,
        embedding_api_key_set=_redact_key(ws.embedding.api_key or ""),
        default_version=ws.default_version,
        max_chunk_size=ws.chunking.max_chunk_size,
        chunk_overlap=ws.chunking.chunk_overlap,
        split_on_headings=ws.chunking.split_on_headings,
        members=ws.members,
        metadata=ws.metadata,
    )


@router.put(
    "/workspaces/{workspace_id}",
    response_model=WorkspaceSettingsResponse,
    summary="Update workspace settings (LLM, embedding, chunking, version)",
)
async def update_workspace_settings(
    workspace_id: str,
    update: WorkspaceSettingsUpdate,
) -> WorkspaceSettingsResponse:
    """
    Partially updates workspace-level configuration.
    Supports:
    - **LLM provider** (provider, model_name, api_key, temperature, max_tokens)
    - **Embedding provider** (provider, model_name, api_key, dimensions)
    - **Chunking parameters** (max_chunk_size, chunk_overlap, split_on_headings)
    - **default_version** — fallback API version for this workspace
    - **members** — list of workspace member user IDs
    """
    ws = _get_or_create_workspace_settings(workspace_id)

    if update.llm:
        ws.llm = update.llm
    if update.embedding:
        ws.embedding = update.embedding
    if update.chunking:
        ws.chunking = update.chunking
    if update.default_version is not None:
        ws.default_version = update.default_version
    if update.members is not None:
        ws.members = update.members
    if update.metadata is not None:
        ws.metadata = {**ws.metadata, **update.metadata}

    _workspace_settings[workspace_id] = ws
    logger.info(f"Workspace '{workspace_id}' settings updated.")
    return await get_workspace_settings(workspace_id)


@router.post(
    "/workspaces/{workspace_id}/members",
    response_model=WorkspaceSettingsResponse,
    summary="Add or remove workspace members",
)
async def manage_workspace_members(
    workspace_id: str,
    add: List[str] = Body(default=[], description="User IDs to add"),
    remove: List[str] = Body(default=[], description="User IDs to remove"),
) -> WorkspaceSettingsResponse:
    """
    Adds and/or removes member user IDs from the workspace member list.
    POST body: `{"add": ["user_a", "user_b"], "remove": ["user_c"]}`
    """
    ws = _get_or_create_workspace_settings(workspace_id)
    current = set(ws.members)
    current.update(add)
    current.difference_update(remove)
    ws.members = sorted(current)
    _workspace_settings[workspace_id] = ws
    logger.info(
        f"Workspace '{workspace_id}' members: +{len(add)} added, -{len(remove)} removed."
    )
    return await get_workspace_settings(workspace_id)

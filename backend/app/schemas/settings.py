"""
Settings & Dynamic LLM Configuration Schemas
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# LLM Provider Configuration
# ---------------------------------------------------------------------------

class LLMProviderConfig(BaseModel):
    """Workspace-level LLM provider and model preferences."""
    provider: str = Field(
        default="ollama",
        description="LLM provider: 'ollama' | 'gemini' | 'anthropic' | 'local'",
    )
    model_name: str = Field(
        default="llama3.2",
        description="Model identifier (e.g. 'llama3.2', 'mistral', 'gemini-1.5-flash')",
    )
    base_url: Optional[str] = Field(
        default="http://localhost:11434",
        description="Base URL for self-hosted LLM (e.g. Ollama host)",
    )
    api_key: Optional[str] = Field(
        None,
        description="User-supplied API key (stored securely; never returned in GET responses)",
    )
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="Generation temperature")
    max_tokens: Optional[int] = Field(None, ge=1, description="Max completion tokens")


class EmbeddingConfig(BaseModel):
    """Workspace-level embedding provider preferences."""
    provider: str = Field(
        default="ollama",
        description="Embedding provider: 'ollama' | 'gemini' | 'local'",
    )
    model_name: str = Field(
        default="nomic-embed-text",
        description="Embedding model identifier",
    )
    base_url: Optional[str] = Field(
        default="http://localhost:11434",
        description="Base URL for Ollama embeddings",
    )
    api_key: Optional[str] = Field(None, description="User-supplied API key for embedding")
    dimensions: Optional[int] = Field(None, ge=64, description="Custom embedding vector dimensions")


class ChunkingConfig(BaseModel):
    """Document chunking parameters tunable per workspace."""
    max_chunk_size: int = Field(default=512, ge=64, le=4096, description="Max tokens per chunk")
    chunk_overlap: int = Field(default=64, ge=0, le=512, description="Token overlap between chunks")
    split_on_headings: bool = Field(default=True, description="Always split on Markdown headings")
    min_chunk_size: int = Field(default=32, ge=1, description="Minimum chunk size (tokens)")


# ---------------------------------------------------------------------------
# Workspace Settings
# ---------------------------------------------------------------------------

class WorkspaceSettings(BaseModel):
    """Full workspace-level settings object stored in Workspace.settings JSON."""
    llm: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    default_version: str = Field(default="latest", description="Fallback version when none specified")
    members: List[str] = Field(default_factory=list, description="List of member user IDs")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary workspace metadata")


class WorkspaceSettingsUpdate(BaseModel):
    """Partial update for workspace settings (all fields optional)."""
    llm: Optional[LLMProviderConfig] = None
    embedding: Optional[EmbeddingConfig] = None
    chunking: Optional[ChunkingConfig] = None
    default_version: Optional[str] = None
    members: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class WorkspaceSettingsResponse(BaseModel):
    """Settings response — api_keys are redacted."""
    workspace_id: str
    llm_provider: str
    llm_model: str
    llm_base_url: Optional[str] = None
    llm_api_key_set: bool = Field(description="True if a custom LLM API key has been set")
    embedding_provider: str
    embedding_model: str
    embedding_base_url: Optional[str] = None
    embedding_api_key_set: bool
    default_version: str
    max_chunk_size: int
    chunk_overlap: int
    split_on_headings: bool
    members: List[str]
    metadata: Dict[str, Any]


# ---------------------------------------------------------------------------
# Global application settings (server-level, admin-only)
# ---------------------------------------------------------------------------

class GlobalSettingsUpdate(BaseModel):
    """Global server settings update (admin use)."""
    default_llm_provider: Optional[str] = None
    default_embedding_provider: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, le=10000)


class GlobalSettingsResponse(BaseModel):
    """Global settings response — keys redacted."""
    default_llm_provider: str
    default_embedding_provider: str
    ollama_base_url: str
    ollama_api_key_set: bool
    gemini_api_key_set: bool
    rate_limit_per_minute: int


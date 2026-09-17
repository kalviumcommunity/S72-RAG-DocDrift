import enum
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class QueryIntentEnum(str, enum.Enum):
    SINGLE_VERSION = "single_version"
    COMPARISON = "comparison"
    MIGRATION = "migration"
    TROUBLESHOOTING = "troubleshooting"
    FEATURE_USAGE = "feature_usage"
    GENERAL = "general"


class QueryIntentRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The user question or search prompt")
    selected_version: Optional[str] = Field(None, description="Currently selected or active version in UI context (e.g. 'v2.0')")
    available_versions: Optional[List[str]] = Field(None, description="Known workspace versions to resolve against (e.g. ['v1.0', 'v2.0'])")
    mode: Optional[str] = Field("hybrid", description="Analysis strategy: 'hybrid', 'regex', or 'llm'")


class QueryIntentResponse(BaseModel):
    query: str = Field(..., description="The original user query text")
    is_comparison: bool = Field(..., description="True if query compares multiple versions or describes a transition/diff")
    target_versions: List[str] = Field(default_factory=list, description="List of targeted versions (e.g. ['v1.0', 'v2.0'] or ['v2.0'])")
    intent: str = Field(..., description="Categorized query intent: comparison, migration, feature_usage, troubleshooting, etc.")
    detected_endpoints: List[str] = Field(default_factory=list, description="API endpoints detected in the query (e.g. ['/charges', '/payments'])")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score of the intent classification")
    analysis_mode: str = Field("regex", description="Strategy executed: 'regex', 'llm', or 'fallback'")
    explanation: Optional[str] = Field(None, description="Reasoning or description of how intent and versions were extracted")

    model_config = ConfigDict(from_attributes=True)

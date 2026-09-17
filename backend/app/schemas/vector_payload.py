from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict
from app.models.entities import DocTypeEnum


class VectorChunkMetadata(BaseModel):
    """
    Schema for the metadata payload stored alongside each vector chunk in the vector database.
    Ensures strict typing, line offset tracking for citation highlighting, and version awareness.
    """
    doc_id: str = Field(..., description="Unique ID of the parent document")
    version: str = Field(..., description="API Version tag (e.g. v1.0, v2.1, latest)")
    doc_type: str = Field(default=DocTypeEnum.API_REFERENCE.value, description="Type of documentation")
    section_header: str = Field(..., description="Heading or endpoint path for the chunk")
    section_level: int = Field(default=1, ge=1, le=6, description="Markdown header level (# = 1, ## = 2)")
    start_line: int = Field(..., ge=1, description="Starting line number in source file")
    end_line: int = Field(..., ge=1, description="Ending line number in source file")
    start_char_offset: Optional[int] = Field(default=None, ge=0, description="Start character offset")
    end_char_offset: Optional[int] = Field(default=None, ge=0, description="End character offset")
    file_name: str = Field(..., description="Source file name (e.g., auth_v2.md)")
    endpoint_path: Optional[str] = Field(default=None, description="API endpoint path if applicable (e.g., /api/v2/auth)")
    http_method: Optional[str] = Field(default=None, description="HTTP Method (GET, POST, PUT, DELETE)")
    is_deprecated: bool = Field(default=False, description="Whether this section contains deprecated API info")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")

    model_config = ConfigDict(extra="allow")

    def to_chroma_dict(self) -> Dict[str, Union[str, int, float, bool]]:
        """
        Flattens complex types into ChromaDB-compatible primitive types (str, int, float, bool).
        """
        payload = {}
        for key, value in self.model_dump().items():
            if value is None:
                continue
            elif isinstance(value, (str, int, float, bool)):
                payload[key] = value
            elif isinstance(value, list):
                # ChromaDB requires primitive metadata; serialize list to comma-separated string
                payload[key] = ",".join(str(v) for v in value)
            else:
                payload[key] = str(value)
        return payload


class VectorFilterQuery(BaseModel):
    """
    Query parameters for filtering vector search results.
    """
    version: Optional[Union[str, List[str]]] = Field(None, description="Target version or list of versions")
    doc_type: Optional[Union[str, List[str]]] = Field(None, description="Document type filter")
    doc_id: Optional[str] = Field(None, description="Filter to a specific parent document")
    is_deprecated: Optional[bool] = Field(None, description="Filter by deprecation status")
    endpoint_path: Optional[str] = Field(None, description="Filter by API endpoint path")
    http_method: Optional[str] = Field(None, description="Filter by HTTP method")

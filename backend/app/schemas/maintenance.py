from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Response schemas (used by both service layer and HTTP API)
# ---------------------------------------------------------------------------

class DeleteChunksResult(BaseModel):
    doc_id: str = Field(..., description="Document ID whose chunks were targeted")
    deleted_count: int = Field(..., description="Number of chunks cleanly removed")
    success: bool = Field(default=True, description="Whether deletion was successful")
    remaining_count: int = Field(default=0, description="Number of residual chunks remaining in collection")
    duration_ms: float = Field(default=0.0, description="Execution time in milliseconds")


class BatchInsertResult(BaseModel):
    total_chunks: int = Field(..., description="Total chunks submitted for insertion")
    inserted_count: int = Field(..., description="Number of chunks successfully indexed")
    batches_processed: int = Field(..., description="Number of batch iterations executed")
    batch_size: int = Field(default=100, description="Batch chunk size limit utilized")
    duration_ms: float = Field(..., description="Total batch insertion latency in milliseconds")
    errors: List[str] = Field(default_factory=list, description="Any warnings or batch-level errors encountered")


class DocumentZeroDowntimeUpdateResult(BaseModel):
    doc_id: str = Field(..., description="Target document ID")
    status: str = Field(default="success", description="Status of update: 'success', 'partial', or 'failed'")
    inserted_count: int = Field(..., description="Number of new chunks staged and indexed")
    deleted_stale_count: int = Field(..., description="Number of obsolete previous chunks pruned")
    active_chunk_count: int = Field(..., description="Current count of active chunks for doc_id")
    duration_ms: float = Field(..., description="Total duration in milliseconds")
    error_message: Optional[str] = Field(default=None, description="Error detail if operation failed or rolled back")


# ---------------------------------------------------------------------------
# Request schemas for the maintenance HTTP API
# ---------------------------------------------------------------------------

class VectorChunkInput(BaseModel):
    """A single chunk payload for batch insertion."""
    id: str = Field(..., description="Unique chunk ID")
    document: str = Field(..., description="Raw chunk text content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata (doc_id, version, etc.)")
    embedding: Optional[List[float]] = Field(None, description="Pre-computed embedding vector (optional)")


class DeleteChunksRequest(BaseModel):
    """Request body for DELETE /maintenance/vectors/{doc_id}."""
    batch_size: int = Field(default=200, ge=1, le=1000, description="Number of chunk IDs to delete per batch")


class BatchInsertRequest(BaseModel):
    """Request body for POST /maintenance/vectors/batch-insert."""
    chunks: List[VectorChunkInput] = Field(..., min_length=1, description="List of chunks to index")
    batch_size: int = Field(default=100, ge=1, le=500, description="Upsert batch size")


class ZeroDowntimeUpdateRequest(BaseModel):
    """Request body for PUT /maintenance/vectors/{doc_id}."""
    chunks: List[VectorChunkInput] = Field(..., min_length=1, description="Complete new chunk set for the document")
    batch_size: int = Field(default=100, ge=1, le=500, description="Upsert batch size")


class BlueGreenReindexRequest(BaseModel):
    """Request body for POST /maintenance/vectors/blue-green-reindex."""
    chunks: List[VectorChunkInput] = Field(..., min_length=1, description="Full dataset for staging collection")
    batch_size: int = Field(default=100, ge=1, le=500, description="Upsert batch size")
    temp_collection_prefix: str = Field(default="staging", description="Prefix for the shadow staging collection name")

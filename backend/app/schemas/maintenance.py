from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


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


class VectorChunkInput(BaseModel):
    id: str = Field(..., description="Unique ID for chunk")
    document: str = Field(..., description="Text content of chunk")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary")
    embedding: Optional[List[float]] = Field(default=None, description="Optional pre-computed embedding vector")


class BatchInsertRequest(BaseModel):
    chunks: List[VectorChunkInput] = Field(..., description="Chunks to batch insert")
    batch_size: int = Field(default=100, ge=1, le=1000, description="Chunk batch size")


class DeleteChunksRequest(BaseModel):
    doc_id: str = Field(..., description="Document ID to delete chunks for")
    batch_size: int = Field(default=200, ge=1, le=1000)


class ZeroDowntimeUpdateRequest(BaseModel):
    chunks: List[VectorChunkInput] = Field(..., description="New chunks for the document")
    batch_size: int = Field(default=100, ge=1, le=1000)


class BlueGreenReindexRequest(BaseModel):
    chunks: List[VectorChunkInput] = Field(..., description="Full dataset of chunks")
    batch_size: int = Field(default=100, ge=1, le=1000)
    temp_collection_prefix: str = Field(default="staging", description="Prefix for staging collection")


class SyncVectorsRequest(BaseModel):
    chunks: List[Dict[str, Any]] = Field(default_factory=list, description="List of chunk dicts with id, content, metadata")
    batch_size: int = Field(default=100, ge=1, le=1000)


class ZeroDowntimeSyncRequest(BaseModel):
    document_id: str
    new_chunks: List[Dict[str, Any]]
    batch_size: int = Field(default=100, ge=1, le=1000)

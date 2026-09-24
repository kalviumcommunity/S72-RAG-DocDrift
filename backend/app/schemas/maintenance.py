from typing import Optional, List
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

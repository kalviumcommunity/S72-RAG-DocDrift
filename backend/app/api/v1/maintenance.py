"""
Vector Store Maintenance API
=============================
Endpoints:
  POST /maintenance/sync-vectors       — Sync and batch-insert embeddings cleanly
  DELETE /maintenance/docs/{doc_id}    — Cleanly delete all vector chunks for a document
  POST /maintenance/zero-downtime-sync — Zero-downtime document update
  GET  /maintenance/status             — Vector store maintenance status & collection stats
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Body
from pydantic import BaseModel, Field

from app.services.vector_maintenance import (
    vector_maintenance,
    clean_delete_chunks_by_doc_id,
    batch_insert_embeddings,
    zero_downtime_update_document,
)
from app.schemas.maintenance import (
    DeleteChunksResult,
    BatchInsertResult,
    DocumentZeroDowntimeUpdateResult,
)
from app.services.vector_store import vector_store
from app.core.logging import logger

router = APIRouter(prefix="/maintenance", tags=["Vector Maintenance"])


class SyncVectorsRequest(BaseModel):
    chunks: List[Dict[str, Any]] = Field(default_factory=list, description="List of chunk dicts with id, content, metadata")
    batch_size: int = Field(default=100, ge=1, le=1000)


class ZeroDowntimeSyncRequest(BaseModel):
    document_id: str
    new_chunks: List[Dict[str, Any]]
    batch_size: int = Field(default=100, ge=1, le=1000)


@router.get("/status", summary="Get vector store maintenance status")
async def get_maintenance_status():
    """Returns vector store collection status, persistence directory, and count."""
    try:
        col = getattr(vector_store, "collection", None)
        count = col.count() if col else 0
        return {
            "status": "healthy" if col else "degraded",
            "collection_name": getattr(vector_store, "collection_name", "docdrift_chunks"),
            "total_chunks_indexed": count,
            "persistence_dir": getattr(vector_store, "persist_directory", "./chroma_db_data"),
        }
    except Exception as e:
        logger.warning(f"Error retrieving maintenance status: {e}")
        return {
            "status": "degraded",
            "error": str(e),
            "total_chunks_indexed": 0
        }


@router.post("/sync-vectors", response_model=BatchInsertResult, summary="Batch insert embeddings into vector store")
async def sync_vectors(request: SyncVectorsRequest):
    """
    Inserts chunks into the vector store in manageable batches with automatic embedding generation.
    """
    try:
        result = batch_insert_embeddings(
            chunks=request.chunks,
            batch_size=request.batch_size
        )
        return result
    except Exception as e:
        logger.error(f"Sync vectors error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/docs/{document_id}", response_model=DeleteChunksResult, summary="Delete obsolete vector chunks by doc_id")
async def delete_doc_vectors(document_id: str, batch_size: int = 200):
    """
    Cleanly deletes all vector chunks associated with a document ID.
    """
    try:
        result = clean_delete_chunks_by_doc_id(doc_id=document_id, batch_size=batch_size)
        return result
    except Exception as e:
        logger.error(f"Delete doc vectors error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/zero-downtime-sync", response_model=DocumentZeroDowntimeUpdateResult, summary="Zero-downtime document update")
async def zero_downtime_sync(request: ZeroDowntimeSyncRequest):
    """
    Updates a document's vector representation with zero query downtime.
    Stages new chunks first, then deletes obsolete chunks.
    """
    try:
        result = zero_downtime_update_document(
            document_id=request.document_id,
            new_chunks=request.new_chunks,
            batch_size=request.batch_size
        )
        return result
    except Exception as e:
        logger.error(f"Zero downtime sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

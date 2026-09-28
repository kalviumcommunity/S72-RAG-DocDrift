"""
Vector Store Maintenance API
=============================
REST endpoints for managing the ChromaDB vector collection lifecycle:
  GET    /maintenance/status                    — vector store maintenance status & collection stats
  GET    /maintenance/vectors/{doc_id}/stats    — fetch chunk count and IDs for a document
  POST   /maintenance/sync-vectors              — sync and batch-insert embeddings cleanly
  POST   /maintenance/vectors/batch-insert      — batch-insert/upsert new chunks
  DELETE /maintenance/docs/{document_id}        — clean delete all vector chunks for a document
  DELETE /maintenance/vectors/{doc_id}          — clean delete all chunks for a document
  POST   /maintenance/zero-downtime-sync        — zero-downtime document update
  PUT    /maintenance/vectors/{doc_id}          — zero-downtime document re-embedding
  POST   /maintenance/vectors/blue-green-reindex — stage full re-index in shadow collection
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from app.schemas.maintenance import (
    DeleteChunksResult,
    BatchInsertResult,
    DocumentZeroDowntimeUpdateResult,
    DeleteChunksRequest,
    BatchInsertRequest,
    ZeroDowntimeUpdateRequest,
    BlueGreenReindexRequest,
    VectorChunkInput,
    SyncVectorsRequest,
    ZeroDowntimeSyncRequest,
)
from app.services.vector_maintenance import (
    vector_maintenance,
    clean_delete_chunks_by_doc_id,
    batch_insert_embeddings,
    zero_downtime_update_document,
)
from app.services.vector_store import vector_store
from app.core.logging import logger

router = APIRouter(prefix="/maintenance", tags=["Vector Maintenance"])


# ---------------------------------------------------------------------------
# Helper: convert VectorChunkInput list to the dict format expected by service
# ---------------------------------------------------------------------------

def _to_chunk_dicts(inputs: List[VectorChunkInput]) -> List[Dict[str, Any]]:
    result = []
    for inp in inputs:
        chunk: Dict[str, Any] = {
            "id":       inp.id,
            "chunk_id": inp.id,
            "document": inp.document,
            "content":  inp.document,
            "metadata": inp.metadata,
        }
        if inp.embedding is not None:
            chunk["embedding"] = inp.embedding
        result.append(chunk)
    return result


# ---------------------------------------------------------------------------
# GET /maintenance/status
# ---------------------------------------------------------------------------

@router.get("/status", summary="Get vector store maintenance status")
async def get_maintenance_status() -> Dict[str, Any]:
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
            "total_chunks_indexed": 0,
        }


# ---------------------------------------------------------------------------
# GET /maintenance/vectors/{doc_id}/stats
# ---------------------------------------------------------------------------

@router.get(
    "/vectors/{doc_id}/stats",
    summary="Get vector chunk statistics for a document",
    response_model=Dict[str, Any],
)
async def get_vector_stats(doc_id: str) -> Dict[str, Any]:
    """
    Returns the number of indexed chunks currently stored for the given document ID.
    Useful for health-checking or pre-flight verification before an update.
    """
    if not doc_id.strip():
        raise HTTPException(status_code=400, detail="doc_id cannot be empty")

    chunk_ids: List[str] = await run_in_threadpool(
        vector_maintenance.get_chunk_ids_by_doc_id, doc_id
    )
    return {
        "doc_id":      doc_id,
        "chunk_count": len(chunk_ids),
        "chunk_ids":   chunk_ids,
    }


# ---------------------------------------------------------------------------
# POST /maintenance/sync-vectors
# ---------------------------------------------------------------------------

@router.post("/sync-vectors", response_model=BatchInsertResult, summary="Batch insert embeddings into vector store")
async def sync_vectors(request: SyncVectorsRequest) -> BatchInsertResult:
    """
    Inserts chunks into the vector store in manageable batches with automatic embedding generation.
    """
    try:
        result = await run_in_threadpool(
            batch_insert_embeddings,
            chunks=request.chunks,
            batch_size=request.batch_size,
        )
        return result
    except Exception as e:
        logger.error(f"Sync vectors error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# POST /maintenance/vectors/batch-insert
# ---------------------------------------------------------------------------

@router.post(
    "/vectors/batch-insert",
    response_model=BatchInsertResult,
    status_code=201,
    summary="Batch-insert new chunk embeddings",
    description=(
        "Batch-inserts (upserts) one or more document chunks into the ChromaDB "
        "collection. Embeddings are auto-computed if not provided. "
        "Each batch is processed atomically to avoid memory spikes."
    ),
)
async def batch_insert_vectors(request: BatchInsertRequest) -> BatchInsertResult:
    """
    Upserts chunks into ChromaDB in bounded batches.
    - If `embedding` is provided in the chunk payload it is used directly.
    - Otherwise embeddings are generated by the configured embedding service.
    - Metadata must include `doc_id` so that future deletes/updates can target it.
    """
    chunk_dicts = _to_chunk_dicts(request.chunks)

    # Separate out pre-computed embeddings (None means auto-compute)
    pre_embeddings = None
    if all(c.embedding is not None for c in request.chunks):
        pre_embeddings = [c.embedding for c in request.chunks]

    logger.info(
        f"[Maintenance API] Batch insert: {len(chunk_dicts)} chunks, "
        f"batch_size={request.batch_size}, pre-embedded={pre_embeddings is not None}"
    )
    try:
        result = await run_in_threadpool(
            vector_maintenance.batch_insert_embeddings,
            chunks=chunk_dicts,
            embeddings=pre_embeddings,
            batch_size=request.batch_size,
        )
        return result
    except Exception as exc:
        logger.error(f"[Maintenance API] Batch insert failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Batch insertion failed: {exc}")


# ---------------------------------------------------------------------------
# DELETE /maintenance/docs/{document_id}
# ---------------------------------------------------------------------------

@router.delete("/docs/{document_id}", response_model=DeleteChunksResult, summary="Delete obsolete vector chunks by doc_id")
async def delete_doc_vectors(document_id: str, batch_size: int = 200) -> DeleteChunksResult:
    """
    Cleanly deletes all vector chunks associated with a document ID.
    """
    if not document_id.strip():
        raise HTTPException(status_code=400, detail="document_id cannot be empty")
    try:
        result = await run_in_threadpool(
            clean_delete_chunks_by_doc_id,
            doc_id=document_id,
            batch_size=batch_size,
        )
        return result
    except Exception as e:
        logger.error(f"Delete doc vectors error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# DELETE /maintenance/vectors/{doc_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/vectors/{doc_id}",
    response_model=DeleteChunksResult,
    summary="Delete all vector chunks for a document",
    description=(
        "Cleanly removes all ChromaDB vector chunks associated with `doc_id` "
        "in bounded batches. Verifies deletion on completion and returns statistics."
    ),
)
async def delete_document_vectors(
    doc_id: str,
    batch_size: int = Query(default=200, ge=1, le=1000, description="Chunks to delete per batch"),
) -> DeleteChunksResult:
    """
    Deletes all indexed chunks for the given `doc_id` from the vector store.
    Use before re-embedding an updated document to avoid stale vector contamination.
    """
    if not doc_id.strip():
        raise HTTPException(status_code=400, detail="doc_id cannot be empty")

    logger.info(f"[Maintenance API] DELETE vectors for doc_id='{doc_id}', batch_size={batch_size}")
    try:
        result = await run_in_threadpool(
            vector_maintenance.clean_delete_chunks_by_doc_id,
            doc_id=doc_id,
            batch_size=batch_size,
        )
        return result
    except Exception as exc:
        logger.error(f"[Maintenance API] Delete failed for doc_id='{doc_id}': {exc}")
        raise HTTPException(status_code=500, detail=f"Vector deletion failed: {exc}")


# ---------------------------------------------------------------------------
# POST /maintenance/zero-downtime-sync
# ---------------------------------------------------------------------------

@router.post("/zero-downtime-sync", response_model=DocumentZeroDowntimeUpdateResult, summary="Zero-downtime document update")
async def zero_downtime_sync(request: ZeroDowntimeSyncRequest) -> DocumentZeroDowntimeUpdateResult:
    """
    Updates a document's vector representation with zero query downtime.
    Stages new chunks first, then deletes obsolete chunks.
    """
    try:
        result = await run_in_threadpool(
            zero_downtime_update_document,
            doc_id=request.document_id,
            new_chunks=request.new_chunks,
            batch_size=request.batch_size,
        )
        return result
    except Exception as e:
        logger.error(f"Zero downtime sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# PUT /maintenance/vectors/{doc_id}
# ---------------------------------------------------------------------------

@router.put(
    "/vectors/{doc_id}",
    response_model=DocumentZeroDowntimeUpdateResult,
    summary="Zero-downtime re-embedding of a document",
    description=(
        "Updates all vector chunks for a document without search downtime:\n"
        "1. Inserts new chunks first (old chunks still serve queries).\n"
        "2. Prunes only the stale chunk IDs absent from the new set.\n"
        "3. Rolls back on insertion failure to protect existing chunks."
    ),
)
async def zero_downtime_update_vectors(
    doc_id: str,
    request: ZeroDowntimeUpdateRequest,
) -> DocumentZeroDowntimeUpdateResult:
    """
    Performs a zero-downtime hot-swap of a document's vector chunks.
    The update is safe to call against a live production collection.
    """
    if not doc_id.strip():
        raise HTTPException(status_code=400, detail="doc_id cannot be empty")

    chunk_dicts = _to_chunk_dicts(request.chunks)
    # Enforce doc_id in all metadata entries
    for c in chunk_dicts:
        c.setdefault("metadata", {})["doc_id"] = doc_id

    logger.info(
        f"[Maintenance API] Zero-downtime update: doc_id='{doc_id}', "
        f"{len(chunk_dicts)} new chunks, batch_size={request.batch_size}"
    )
    try:
        result = await run_in_threadpool(
            vector_maintenance.zero_downtime_update_document,
            doc_id=doc_id,
            new_chunks=chunk_dicts,
            batch_size=request.batch_size,
        )
        if result.status == "failed":
            raise HTTPException(
                status_code=500,
                detail=f"Zero-downtime update failed: {result.error_message}",
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[Maintenance API] Zero-downtime update error for doc_id='{doc_id}': {exc}")
        raise HTTPException(status_code=500, detail=f"Update failed: {exc}")


# ---------------------------------------------------------------------------
# POST /maintenance/vectors/blue-green-reindex
# ---------------------------------------------------------------------------

@router.post(
    "/vectors/blue-green-reindex",
    response_model=Dict[str, Any],
    summary="Stage a full re-index in a shadow collection (Blue-Green)",
    description=(
        "Indexes the complete dataset into a temporary shadow ChromaDB collection "
        "without touching the live collection. The staging collection name is returned "
        "for manual atomic pointer swap after verification."
    ),
)
async def blue_green_reindex(request: BlueGreenReindexRequest) -> Dict[str, Any]:
    """
    Blue-Green re-index: writes all chunks to a `staging_<timestamp>` collection.
    The caller is responsible for promoting the staging collection to live after
    verifying the indexed count matches expectations.
    """
    chunk_dicts = _to_chunk_dicts(request.chunks)
    logger.info(
        f"[Maintenance API] Blue-Green reindex: {len(chunk_dicts)} chunks, "
        f"prefix='{request.temp_collection_prefix}', batch_size={request.batch_size}"
    )
    try:
        result = await run_in_threadpool(
            vector_maintenance.blue_green_reindex,
            new_chunks=chunk_dicts,
            batch_size=request.batch_size,
            temp_collection_prefix=request.temp_collection_prefix,
        )
        return result
    except Exception as exc:
        logger.error(f"[Maintenance API] Blue-Green reindex failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Blue-Green reindex failed: {exc}")

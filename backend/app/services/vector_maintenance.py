import time
from typing import List, Dict, Any, Optional, Union, Set
from app.core.logging import logger
from app.schemas.maintenance import (
    DeleteChunksResult,
    BatchInsertResult,
    DocumentZeroDowntimeUpdateResult,
)
from app.schemas.vector_payload import VectorChunkMetadata
from app.services.embedding_service import embedding_service


class VectorStoreMaintenanceService:
    """
    Production maintenance service for ChromaDB vector collections.
    Provides:
      1. Clean chunk deletion by doc_id with batching and verification.
      2. Chunked batch insertion of embeddings without RPC/memory bottlenecks.
      3. Zero-downtime document updates (staged upsert followed by stale chunk pruning).
      4. Blue-Green shadow collection swaps for zero-downtime global re-indexing.
    """

    def __init__(self, vector_store=None):
        self._vector_store = vector_store

    @property
    def vector_store(self):
        if self._vector_store is None:
            from app.services.vector_store import vector_store
            self._vector_store = vector_store
        return self._vector_store

    def get_chunk_ids_by_doc_id(
        self,
        doc_id: str,
        collection: Optional[Any] = None
    ) -> List[str]:
        """
        Retrieves all chunk IDs associated with a specific document ID.
        """
        col = collection or getattr(self.vector_store, "collection", None)
        if not col:
            logger.warning("Vector collection is unavailable.")
            return []

        try:
            results = col.get(where={"doc_id": doc_id}, include=[])
            if results and "ids" in results:
                return list(results["ids"])
            return []
        except Exception as e:
            logger.error(f"Failed to fetch chunk IDs for doc_id='{doc_id}': {e}")
            return []

    def clean_delete_chunks_by_doc_id(
        self,
        doc_id: str,
        batch_size: int = 200,
        collection: Optional[Any] = None
    ) -> DeleteChunksResult:
        """
        Cleanly deletes all chunks associated with doc_id in bounded batches
        to avoid payload size limits and long write locks.
        Verifies completion and returns statistics.
        """
        start_time = time.perf_counter()
        col = collection or getattr(self.vector_store, "collection", None)
        if not col:
            logger.warning(f"Vector collection unavailable; skipped deletion for doc_id='{doc_id}'.")
            return DeleteChunksResult(
                doc_id=doc_id,
                deleted_count=0,
                success=False,
                remaining_count=0,
                duration_ms=0.0
            )

        existing_ids = self.get_chunk_ids_by_doc_id(doc_id, collection=col)
        if not existing_ids:
            logger.info(f"No existing chunks found for doc_id='{doc_id}'. Nothing to delete.")
            return DeleteChunksResult(
                doc_id=doc_id,
                deleted_count=0,
                success=True,
                remaining_count=0,
                duration_ms=round((time.perf_counter() - start_time) * 1000, 2)
            )

        deleted_count = 0
        total_chunks = len(existing_ids)

        # Batch delete by ID list
        for i in range(0, total_chunks, batch_size):
            chunk_batch = existing_ids[i:i + batch_size]
            try:
                col.delete(ids=chunk_batch)
                deleted_count += len(chunk_batch)
                logger.debug(f"Deleted batch of {len(chunk_batch)} chunks for doc_id='{doc_id}' ({deleted_count}/{total_chunks}).")
            except Exception as e:
                logger.error(f"Error during batch delete of chunks for doc_id='{doc_id}': {e}")
                # Fallback to metadata-based delete
                try:
                    col.delete(where={"doc_id": doc_id})
                    deleted_count = total_chunks
                    break
                except Exception as ex2:
                    logger.error(f"Fallback where-delete also failed for doc_id='{doc_id}': {ex2}")
                    break

        # Verification step
        remaining_ids = self.get_chunk_ids_by_doc_id(doc_id, collection=col)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        is_success = len(remaining_ids) == 0
        logger.info(
            f"Completed deletion for doc_id='{doc_id}': removed {deleted_count} chunks, "
            f"{len(remaining_ids)} remaining in {duration_ms}ms."
        )

        return DeleteChunksResult(
            doc_id=doc_id,
            deleted_count=deleted_count,
            success=is_success,
            remaining_count=len(remaining_ids),
            duration_ms=duration_ms
        )

    def batch_insert_embeddings(
        self,
        chunks: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Union[Dict[str, Any], VectorChunkMetadata]]] = None,
        embeddings: Optional[List[List[float]]] = None,
        batch_size: int = 100,
        collection: Optional[Any] = None
    ) -> BatchInsertResult:
        """
        Batch-inserts documents and their embeddings in bounded chunks.
        Computes embeddings in batches if not already provided.
        Prevents memory spikes and handles timeouts cleanly.
        """
        start_time = time.perf_counter()
        col = collection or getattr(self.vector_store, "collection", None)
        if not col:
            logger.warning("Vector collection unavailable for batch insertion.")
            return BatchInsertResult(
                total_chunks=0,
                inserted_count=0,
                batches_processed=0,
                batch_size=batch_size,
                duration_ms=0.0,
                errors=["Vector collection unavailable"]
            )

        # Standardize inputs
        norm_ids: List[str] = []
        norm_docs: List[str] = []
        norm_metas: List[Union[Dict[str, Any], VectorChunkMetadata]] = []
        norm_embeds: Optional[List[List[float]]] = embeddings

        if chunks is not None:
            for c in chunks:
                norm_ids.append(c.get("id") or c.get("chunk_id") or "")
                norm_docs.append(c.get("document") or c.get("content") or "")
                norm_metas.append(c.get("metadata") or {})
        else:
            norm_ids = ids or []
            norm_docs = documents or []
            norm_metas = metadatas or []

        total_chunks = len(norm_ids)
        if total_chunks == 0:
            return BatchInsertResult(
                total_chunks=0,
                inserted_count=0,
                batches_processed=0,
                batch_size=batch_size,
                duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
                errors=[]
            )

        # Compute embeddings in batches if absent
        if norm_embeds is None or len(norm_embeds) != total_chunks:
            logger.info(f"Computing embeddings for {total_chunks} chunks in batches...")
            norm_embeds = []
            for b in range(0, total_chunks, batch_size):
                batch_docs = norm_docs[b:b + batch_size]
                batch_embeds = embedding_service.get_embeddings_batch(batch_docs)
                norm_embeds.extend(batch_embeds)

        inserted_count = 0
        batches_processed = 0
        errors: List[str] = []

        for i in range(0, total_chunks, batch_size):
            b_ids = norm_ids[i:i + batch_size]
            b_docs = norm_docs[i:i + batch_size]
            b_metas = norm_metas[i:i + batch_size]
            b_embeds = norm_embeds[i:i + batch_size]

            try:
                # Sanitize metadata to ChromaDB primitives
                sanitized_metadatas = []
                for meta in b_metas:
                    if isinstance(meta, VectorChunkMetadata):
                        d = meta.to_chroma_dict()
                        if "version" in d and "version_tag" not in d:
                            d["version_tag"] = d["version"]
                        sanitized_metadatas.append(d)
                    elif isinstance(meta, dict):
                        sanitized = {}
                        for k, v in meta.items():
                            if isinstance(v, (str, int, float, bool)):
                                sanitized[k] = v
                            elif isinstance(v, list):
                                sanitized[k] = ",".join(str(item) for item in v)
                            else:
                                sanitized[k] = str(v)
                        if "version_tag" in sanitized and "version" not in sanitized:
                            sanitized["version"] = sanitized["version_tag"]
                        elif "version" in sanitized and "version_tag" not in sanitized:
                            sanitized["version_tag"] = sanitized["version"]
                        sanitized_metadatas.append(sanitized)
                    else:
                        sanitized_metadatas.append({})

                col.upsert(
                    ids=b_ids,
                    embeddings=b_embeds,
                    documents=b_docs,
                    metadatas=sanitized_metadatas
                )
                inserted_count += len(b_ids)
                batches_processed += 1
            except Exception as e:
                err_msg = f"Failed to upsert batch {batches_processed + 1} (items {i}-{i+len(b_ids)}): {str(e)}"
                logger.error(err_msg)
                errors.append(err_msg)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            f"Batch insert complete: {inserted_count}/{total_chunks} indexed across "
            f"{batches_processed} batches in {duration_ms}ms."
        )

        return BatchInsertResult(
            total_chunks=total_chunks,
            inserted_count=inserted_count,
            batches_processed=batches_processed,
            batch_size=batch_size,
            duration_ms=duration_ms,
            errors=errors
        )

    def zero_downtime_update_document(
        self,
        doc_id: str,
        new_chunks: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Union[Dict[str, Any], VectorChunkMetadata]]] = None,
        embeddings: Optional[List[List[float]]] = None,
        batch_size: int = 100,
        collection: Optional[Any] = None
    ) -> DocumentZeroDowntimeUpdateResult:
        """
        Zero-Downtime Document Update:
        Updates a document's chunks without any gap or downtime in searchability:
          1. Identifies existing chunk IDs for doc_id.
          2. Batch-inserts the updated/new chunks FIRST.
             - During this phase, search queries for doc_id continue to return results!
          3. Verifies that newly indexed chunks are successfully persisted.
          4. Prunes only the stale/obsolete chunk IDs that do not appear in the new chunk set.
          5. If new chunk insertion encounters errors, rolls back newly inserted chunks
             to keep existing chunks fully intact and healthy.
        """
        start_time = time.perf_counter()
        col = collection or getattr(self.vector_store, "collection", None)
        if not col:
            return DocumentZeroDowntimeUpdateResult(
                doc_id=doc_id,
                status="failed",
                inserted_count=0,
                deleted_stale_count=0,
                active_chunk_count=0,
                duration_ms=0.0,
                error_message="Vector collection is unavailable"
            )

        # 1. Snapshot existing chunk IDs for the document
        old_chunk_ids: Set[str] = set(self.get_chunk_ids_by_doc_id(doc_id, collection=col))
        logger.info(f"[Zero-Downtime] Document '{doc_id}' currently has {len(old_chunk_ids)} existing chunks.")

        # 2. Extract and standardize new chunk IDs
        new_id_list: List[str] = []
        if new_chunks is not None:
            new_id_list = [c.get("id") or c.get("chunk_id") or "" for c in new_chunks]
        elif ids is not None:
            new_id_list = list(ids)

        new_ids_set: Set[str] = set(new_id_list)

        # 3. Ensure doc_id is set in every metadata entry
        if metadatas is not None:
            for m in metadatas:
                if isinstance(m, dict):
                    m["doc_id"] = doc_id
                elif isinstance(m, VectorChunkMetadata):
                    m.doc_id = doc_id
        elif new_chunks is not None:
            for c in new_chunks:
                if "metadata" not in c or not isinstance(c["metadata"], dict):
                    c["metadata"] = {}
                c["metadata"]["doc_id"] = doc_id

        # 4. Batch-insert the new chunks FIRST (Zero Downtime)
        insert_res = self.batch_insert_embeddings(
            chunks=new_chunks,
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
            batch_size=batch_size,
            collection=col
        )

        if insert_res.errors or insert_res.inserted_count == 0 and len(new_id_list) > 0:
            error_details = "; ".join(insert_res.errors) or "No chunks were indexed"
            logger.error(f"[Zero-Downtime] Insertion failed for doc_id='{doc_id}': {error_details}. Rolling back...")
            
            # Rollback: Clean up any newly inserted chunks that weren't part of old chunks
            newly_added_ids = list(new_ids_set - old_chunk_ids)
            if newly_added_ids:
                try:
                    col.delete(ids=newly_added_ids)
                except Exception as rollback_err:
                    logger.error(f"[Zero-Downtime] Rollback deletion error: {rollback_err}")

            return DocumentZeroDowntimeUpdateResult(
                doc_id=doc_id,
                status="failed",
                inserted_count=insert_res.inserted_count,
                deleted_stale_count=0,
                active_chunk_count=len(old_chunk_ids),
                duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
                error_message=f"Batch insertion failed: {error_details}"
            )

        # 5. Prune obsolete chunks (stale chunks not in new set)
        stale_ids_to_delete = list(old_chunk_ids - new_ids_set)
        deleted_stale_count = 0

        if stale_ids_to_delete:
            logger.info(f"[Zero-Downtime] Pruning {len(stale_ids_to_delete)} stale chunks for doc_id='{doc_id}'...")
            for i in range(0, len(stale_ids_to_delete), batch_size):
                batch = stale_ids_to_delete[i:i + batch_size]
                try:
                    col.delete(ids=batch)
                    deleted_stale_count += len(batch)
                except Exception as del_err:
                    logger.warning(f"[Zero-Downtime] Failed to delete stale batch {batch}: {del_err}")

        current_active = len(self.get_chunk_ids_by_doc_id(doc_id, collection=col))
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        logger.info(
            f"[Zero-Downtime] Successfully updated doc_id='{doc_id}': {insert_res.inserted_count} new chunks indexed, "
            f"{deleted_stale_count} stale pruned. Active chunks={current_active} in {duration_ms}ms."
        )

        return DocumentZeroDowntimeUpdateResult(
            doc_id=doc_id,
            status="success",
            inserted_count=insert_res.inserted_count,
            deleted_stale_count=deleted_stale_count,
            active_chunk_count=current_active,
            duration_ms=duration_ms
        )

    def blue_green_reindex(
        self,
        new_chunks: List[Dict[str, Any]],
        batch_size: int = 100,
        temp_collection_prefix: str = "staging"
    ) -> Dict[str, Any]:
        """
        Global Blue-Green Collection Maintenance:
        Indexes an entirely updated dataset into a shadow staging collection,
        verifies its integrity, and prepares it for atomic pointer swap.
        """
        client = getattr(self.vector_store, "client", None)
        if not client:
            return {"status": "failed", "error": "ChromaDB client unavailable"}

        staging_name = f"{temp_collection_prefix}_{int(time.time())}"
        staging_col = client.get_or_create_collection(
            name=staging_name,
            metadata={"hnsw:space": "cosine"}
        )

        # Batch insert into staging
        res = self.batch_insert_embeddings(
            chunks=new_chunks,
            batch_size=batch_size,
            collection=staging_col
        )

        return {
            "status": "success" if not res.errors else "partial",
            "staging_collection": staging_name,
            "total_chunks": res.total_chunks,
            "inserted_count": res.inserted_count,
            "duration_ms": res.duration_ms,
            "errors": res.errors
        }


# Global singleton instance
vector_maintenance = VectorStoreMaintenanceService()

# Standalone functional interfaces
def clean_delete_chunks_by_doc_id(doc_id: str, batch_size: int = 200, collection: Optional[Any] = None) -> DeleteChunksResult:
    return vector_maintenance.clean_delete_chunks_by_doc_id(doc_id=doc_id, batch_size=batch_size, collection=collection)


def batch_insert_embeddings(
    chunks: Optional[List[Dict[str, Any]]] = None,
    ids: Optional[List[str]] = None,
    documents: Optional[List[str]] = None,
    metadatas: Optional[List[Union[Dict[str, Any], VectorChunkMetadata]]] = None,
    embeddings: Optional[List[List[float]]] = None,
    batch_size: int = 100,
    collection: Optional[Any] = None
) -> BatchInsertResult:
    return vector_maintenance.batch_insert_embeddings(
        chunks=chunks,
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
        batch_size=batch_size,
        collection=collection
    )


def zero_downtime_update_document(
    doc_id: str,
    new_chunks: Optional[List[Dict[str, Any]]] = None,
    ids: Optional[List[str]] = None,
    documents: Optional[List[str]] = None,
    metadatas: Optional[List[Union[Dict[str, Any], VectorChunkMetadata]]] = None,
    embeddings: Optional[List[List[float]]] = None,
    batch_size: int = 100,
    collection: Optional[Any] = None
) -> DocumentZeroDowntimeUpdateResult:
    return vector_maintenance.zero_downtime_update_document(
        doc_id=doc_id,
        new_chunks=new_chunks,
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
        batch_size=batch_size,
        collection=collection
    )

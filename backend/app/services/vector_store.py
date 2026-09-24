import os
import importlib
from typing import List, Dict, Any, Optional, Union

# ChromaDB vector store client with graceful offline fallback
try:
    chromadb = importlib.import_module("chromadb")
    _chroma_config = importlib.import_module("chromadb.config")
    ChromaSettings = getattr(_chroma_config, "Settings", None)
except ImportError:
    chromadb = None
    ChromaSettings = None

from app.core.config import settings
from app.core.logging import logger
from app.services.embedding_service import embedding_service, cosine_similarity
from app.services.vector_filter import build_composite_filter
from app.schemas.vector_payload import VectorChunkMetadata, VectorFilterQuery


class VectorStoreService:
    def __init__(
        self,
        collection_name: Optional[str] = None,
        persist_directory: Optional[str] = None
    ):
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        self.persist_directory = persist_directory or settings.CHROMA_PERSIST_DIRECTORY
        self.client = self._init_client()
        self.collection = self._get_or_create_collection()

    def _init_client(self):
        """Initializes ChromaDB client (HTTP or Persistent local storage)."""
        if chromadb is None:
            logger.warning("chromadb package is not installed. Vector store operations will be unavailable.")
            return None

        try:
            if settings.CHROMA_HOST and settings.CHROMA_PORT:
                logger.info(f"Connecting to ChromaDB HTTP Server at {settings.chroma_base_url}...")
                client = chromadb.HttpClient(
                    host=settings.CHROMA_HOST,
                    port=settings.CHROMA_PORT,
                    ssl=settings.CHROMA_SSL
                )
                client.heartbeat()
                logger.info("ChromaDB HTTP Client connected successfully.")
                return client
        except Exception as e:
            logger.warning(f"ChromaDB HTTP server unavailable ({e}). Falling back to PersistentClient at {self.persist_directory}.")

        os.makedirs(self.persist_directory, exist_ok=True)
        if ChromaSettings is not None:
            return chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
        return chromadb.PersistentClient(path=self.persist_directory)

    def _get_or_create_collection(self):
        """Gets or creates the vector collection configured with cosine distance."""
        if not self.client:
            return None
        return self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )


    def add_chunks(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: List[Union[Dict[str, Any], VectorChunkMetadata]],
        embeddings: Optional[List[List[float]]] = None
    ) -> int:
        """
        Adds or updates chunks in the ChromaDB collection.
        Accepts either raw dicts or VectorChunkMetadata model instances.
        """
        if not ids:
            return 0

        if embeddings is None:
            logger.info(f"Generating embeddings for {len(documents)} chunks...")
            embeddings = embedding_service.get_embeddings_batch(documents)

        # Sanitize metadatas to ChromaDB primitive types
        sanitized_metadatas = []
        for meta in metadatas:
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

        if not self.collection:
            logger.warning("Vector collection is not initialized. Skipping chunk indexing.")
            return 0

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=sanitized_metadatas
        )
        logger.info(f"Successfully indexed {len(ids)} chunks into collection '{self.collection_name}'.")
        return len(ids)

    def query(
        self,
        query_text: str,
        version_tag: Optional[Union[str, List[str]]] = None,
        doc_type: Optional[Union[str, List[str]]] = None,
        doc_id: Optional[str] = None,
        is_deprecated: Optional[bool] = None,
        top_k: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Searches the collection using semantic embedding with flexible metadata filters.
        """
        where_filter = build_composite_filter(
            version=version_tag,
            doc_type=doc_type,
            doc_id=doc_id,
            is_deprecated=is_deprecated
        )
        query_embedding = embedding_service.get_embedding(query_text)
        return self.query_by_vector(
            query_vector=query_embedding,
            where_filter=where_filter,
            top_k=top_k,
            score_threshold=score_threshold
        )

    def search_with_filter(
        self,
        query_text: str,
        filter_query: Optional[VectorFilterQuery] = None,
        top_k: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Searches using a strongly typed VectorFilterQuery model.
        """
        where_filter = build_composite_filter(query=filter_query)
        query_embedding = embedding_service.get_embedding(query_text)
        return self.query_by_vector(
            query_vector=query_embedding,
            where_filter=where_filter,
            top_k=top_k,
            score_threshold=score_threshold
        )

    def query_by_vector(
        self,
        query_vector: List[float],
        where_filter: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs vector similarity search with a pre-built ChromaDB where-filter.
        """
        if not self.collection:
            logger.warning("Vector collection is not initialized. Returning empty search results.")
            return []

        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where_filter if where_filter else None,
            include=["documents", "metadatas", "distances", "embeddings"]
        )


        formatted_results = []
        if results and results["ids"] and len(results["ids"][0]) > 0:
            for i in range(len(results["ids"][0])):
                chunk_id = results["ids"][0][i]
                doc_text = results["documents"][0][i]
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0.0
                
                # Cosine similarity = 1 - cosine distance
                similarity_score = max(0.0, min(1.0, 1.0 - distance))

                if score_threshold is not None and similarity_score < score_threshold:
                    continue

                formatted_results.append({
                    "chunk_id": chunk_id,
                    "content": doc_text,
                    "metadata": metadata,
                    "distance": round(distance, 4),
                    "similarity_score": round(similarity_score, 4),
                    "version": metadata.get("version", metadata.get("version_tag", "latest")),
                    "version_tag": metadata.get("version_tag", metadata.get("version", "latest")),
                    "doc_type": metadata.get("doc_type", "API_REFERENCE"),
                    "section_header": metadata.get("section_header", ""),
                    "start_line": metadata.get("start_line"),
                    "end_line": metadata.get("end_line"),
                    "file_name": metadata.get("file_name", ""),
                    "is_deprecated": metadata.get("is_deprecated", False)
                })

        return formatted_results

    def delete_by_document_id(self, document_id: str) -> None:
        """Deletes all chunks associated with a specific document."""
        if not self.collection:
            logger.warning("Vector collection is not initialized. Skipping delete.")
            return
        self.collection.delete(where={"doc_id": document_id})
        logger.info(f"Deleted all vector chunks for doc_id={document_id}")

    def count(self) -> int:
        """Returns total number of chunks in the collection."""
        if not self.collection:
            return 0
        return self.collection.count()

    def clean_delete_by_doc_id(self, doc_id: str, batch_size: int = 200):
        """Cleanly deletes all chunks belonging to doc_id with batching and verification."""
        from app.services.vector_maintenance import vector_maintenance
        return vector_maintenance.clean_delete_chunks_by_doc_id(
            doc_id=doc_id,
            batch_size=batch_size,
            collection=self.collection
        )

    def batch_insert(
        self,
        chunks: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Union[Dict[str, Any], VectorChunkMetadata]]] = None,
        embeddings: Optional[List[List[float]]] = None,
        batch_size: int = 100
    ):
        """Batch-inserts chunks and embeddings with batching and retry logic."""
        from app.services.vector_maintenance import vector_maintenance
        return vector_maintenance.batch_insert_embeddings(
            chunks=chunks,
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
            batch_size=batch_size,
            collection=self.collection
        )

    def update_document_zero_downtime(
        self,
        doc_id: str,
        new_chunks: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Union[Dict[str, Any], VectorChunkMetadata]]] = None,
        embeddings: Optional[List[List[float]]] = None,
        batch_size: int = 100
    ):
        """Updates a document's chunks with zero downtime and automatic rollback on failure."""
        from app.services.vector_maintenance import vector_maintenance
        return vector_maintenance.zero_downtime_update_document(
            doc_id=doc_id,
            new_chunks=new_chunks,
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
            batch_size=batch_size,
            collection=self.collection
        )


vector_store = VectorStoreService()

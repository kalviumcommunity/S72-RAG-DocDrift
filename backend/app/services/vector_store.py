import os
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings
from app.core.logging import logger
from app.services.embedding_service import embedding_service, cosine_similarity


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
        try:
            # Try HTTP Client first if configured
            if settings.CHROMA_HOST and settings.CHROMA_PORT:
                logger.info(f"Connecting to ChromaDB HTTP Server at {settings.chroma_base_url}...")
                client = chromadb.HttpClient(
                    host=settings.CHROMA_HOST,
                    port=settings.CHROMA_PORT,
                    ssl=settings.CHROMA_SSL
                )
                # Verify connection
                client.heartbeat()
                logger.info("ChromaDB HTTP Client connected successfully.")
                return client
        except Exception as e:
            logger.warning(f"ChromaDB HTTP server unavailable ({e}). Falling back to PersistentClient at {self.persist_directory}.")

        # Fallback to local persistent directory client
        os.makedirs(self.persist_directory, exist_ok=True)
        return chromadb.PersistentClient(
            path=self.persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False)
        )

    def _get_or_create_collection(self):
        """Gets or creates the vector collection configured with cosine distance."""
        return self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None
    ) -> int:
        """
        Adds or updates chunks in the ChromaDB collection.
        If embeddings are not provided, generates them using EmbeddingService.
        """
        if not ids:
            return 0

        if embeddings is None:
            logger.info(f"Generating embeddings for {len(documents)} chunks...")
            embeddings = embedding_service.get_embeddings_batch(documents)

        # ChromaDB metadata values must be primitive types (str, int, float, bool)
        sanitized_metadatas = []
        for meta in metadatas:
            sanitized = {}
            for k, v in meta.items():
                if isinstance(v, (str, int, float, bool)):
                    sanitized[k] = v
                else:
                    sanitized[k] = str(v)
            sanitized_metadatas.append(sanitized)

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
        version_tag: Optional[str] = None,
        doc_type: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Searches the collection using semantic embedding with version and doc_type filters.
        """
        query_embedding = embedding_service.get_embedding(query_text)
        return self.query_by_vector(
            query_vector=query_embedding,
            version_tag=version_tag,
            doc_type=doc_type,
            top_k=top_k
        )

    def query_by_vector(
        self,
        query_vector: List[float],
        version_tag: Optional[str] = None,
        doc_type: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Performs vector similarity search with optional metadata where-filter.
        """
        where_filter = {}
        filters = []
        if version_tag and version_tag.lower() != "all":
            filters.append({"version_tag": version_tag})
        if doc_type:
            filters.append({"doc_type": doc_type})

        if len(filters) == 1:
            where_filter = filters[0]
        elif len(filters) > 1:
            where_filter = {"$and": filters}

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
                
                # ChromaDB cosine distance: cosine_dist = 1 - cosine_similarity
                # Cosine similarity = 1 - distance
                similarity_score = max(0.0, min(1.0, 1.0 - distance))

                formatted_results.append({
                    "chunk_id": chunk_id,
                    "content": doc_text,
                    "metadata": metadata,
                    "distance": round(distance, 4),
                    "similarity_score": round(similarity_score, 4),
                    "version_tag": metadata.get("version_tag", "latest"),
                    "doc_type": metadata.get("doc_type", "API_REFERENCE"),
                    "section_header": metadata.get("section_header", "")
                })

        return formatted_results

    def delete_by_document_id(self, document_id: str) -> None:
        """Deletes all chunks associated with a specific document."""
        self.collection.delete(where={"document_id": document_id})
        logger.info(f"Deleted all vector chunks for document_id={document_id}")

    def count(self) -> int:
        """Returns total number of chunks in the collection."""
        return self.collection.count()


vector_store = VectorStoreService()

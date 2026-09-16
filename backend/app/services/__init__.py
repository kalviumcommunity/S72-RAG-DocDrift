# DocDrift Services Package
from app.services.embedding_service import EmbeddingService, embedding_service, cosine_similarity
from app.services.vector_store import VectorStoreService, vector_store
from app.services.vector_filter import (
    build_version_filter,
    build_composite_filter,
    build_version_diff_filter,
    normalize_version_tag,
)

__all__ = [
    "EmbeddingService",
    "embedding_service",
    "cosine_similarity",
    "VectorStoreService",
    "vector_store",
    "build_version_filter",
    "build_composite_filter",
    "build_version_diff_filter",
    "normalize_version_tag",
]

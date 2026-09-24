# DocDrift Services Package
from app.services.embedding_service import EmbeddingService, embedding_service, cosine_similarity
from app.services.vector_store import VectorStoreService, vector_store
from app.services.vector_filter import (
    build_version_filter,
    build_composite_filter,
    build_version_diff_filter,
    normalize_version_tag,
)
from app.services.query_intent import (
    QueryIntentAnalyzer,
    query_intent_analyzer,
)
from app.services.rag_pipeline import (
    DocDriftRAGPipeline,
    rag_pipeline,
)
from app.services.faithfulness_evaluator import (
    FaithfulnessEvaluator,
    faithfulness_evaluator,
    compute_faithfulness_score,
)

from app.services.vector_maintenance import (
    VectorStoreMaintenanceService,
    vector_maintenance,
    clean_delete_chunks_by_doc_id,
    batch_insert_embeddings,
    zero_downtime_update_document,
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
    "QueryIntentAnalyzer",
    "query_intent_analyzer",
    "DocDriftRAGPipeline",
    "rag_pipeline",
    "FaithfulnessEvaluator",
    "faithfulness_evaluator",
    "compute_faithfulness_score",
    "VectorStoreMaintenanceService",
    "vector_maintenance",
    "clean_delete_chunks_by_doc_id",
    "batch_insert_embeddings",
    "zero_downtime_update_document",
]



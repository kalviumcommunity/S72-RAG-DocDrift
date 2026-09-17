"""
DocDrift AI-RAG Vector Store Maintenance Utilities
Provides zero-downtime reindexing, batch embedding upsert, and clean deletion by doc_id.
"""
from typing import List, Dict, Any, Optional, Union

try:
    from app.services.vector_maintenance import (
        VectorStoreMaintenanceService,
        vector_maintenance,
        clean_delete_chunks_by_doc_id,
        batch_insert_embeddings,
        zero_downtime_update_document,
    )
except ImportError:
    # Standalone fallback when backend is not installed as app
    import sys
    from pathlib import Path
    backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from app.services.vector_maintenance import (
        VectorStoreMaintenanceService,
        vector_maintenance,
        clean_delete_chunks_by_doc_id,
        batch_insert_embeddings,
        zero_downtime_update_document,
    )

__all__ = [
    "VectorStoreMaintenanceService",
    "vector_maintenance",
    "clean_delete_chunks_by_doc_id",
    "batch_insert_embeddings",
    "zero_downtime_update_document",
]

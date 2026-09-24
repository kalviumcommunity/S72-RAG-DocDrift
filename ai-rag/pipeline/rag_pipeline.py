import os
import sys

# Ensure backend directory is in path for ai-rag standalone scripts
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
backend_dir = os.path.join(root_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.prompts import (
    DOCDRIFT_SYSTEM_PROMPT,
    format_chunks_for_context,
    build_rag_user_prompt,
    extract_citation_tags,
)
from app.services.rag_pipeline import (
    DocDriftRAGPipeline,
    rag_pipeline,
)

__all__ = [
    "DOCDRIFT_SYSTEM_PROMPT",
    "format_chunks_for_context",
    "build_rag_user_prompt",
    "extract_citation_tags",
    "DocDriftRAGPipeline",
    "rag_pipeline",
]

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from app.schemas.chunk import ChunkContextResponse, SurroundingChunk
from app.services.vector_store import vector_store
from app.core.logging import logger

router = APIRouter(prefix="/citations", tags=["Citations"])


@router.get(
    "/{chunk_id}",
    response_model=ChunkContextResponse,
    summary="Fetch full chunk context by chunk ID",
    description=(
        "Returns the complete raw text of a cited chunk, its line range within "
        "the source document, parent document metadata (version, type, source URL), "
        "and up to ±`context_window` surrounding chunks from the same document."
    ),
)
async def get_chunk_context(
    chunk_id: str,
    context_window: int = Query(
        default=3,
        ge=1,
        le=10,
        description="Number of neighbouring chunks to include before and after the target chunk",
    ),
):
    """
    GET /api/v1/citations/{chunk_id}

    Path parameter:
    - **chunk_id**: The unique chunk identifier (as embedded in `[^chunk_id]` citation tags).

    Query parameter:
    - **context_window** (default 3): How many sibling chunks to include on each side.

    Response fields:
    - `content` — full raw chunk text
    - `start_line` / `end_line` — line range in the original source file
    - `section_header` / `section_level` — document section provenance
    - `document_id`, `document_title`, `version`, `doc_type` — parent document details
    - `source_url` — canonical URL of the source document (if stored)
    - `surrounding_chunks_before` / `surrounding_chunks_after` — neighbouring chunks
    - `raw_metadata` — all raw ChromaDB metadata fields
    """
    if not chunk_id or not chunk_id.strip():
        raise HTTPException(status_code=400, detail="chunk_id cannot be empty")

    # Fetch the primary chunk from the vector store
    chunk_data = await run_in_threadpool(vector_store.get_chunk_by_id, chunk_id)

    if chunk_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Chunk '{chunk_id}' not found in the vector store.",
        )

    doc_id: str = chunk_data.get("doc_id") or ""
    chunk_index: Optional[int] = chunk_data.get("chunk_index")

    # Fetch surrounding chunks (±context_window siblings from the same document)
    surrounding: dict = {"before": [], "after": []}
    if doc_id and chunk_index is not None:
        surrounding = await run_in_threadpool(
            vector_store.get_surrounding_chunks,
            doc_id=doc_id,
            chunk_index=chunk_index,
            window=context_window,
        )

    def _to_surrounding(raw: dict) -> SurroundingChunk:
        return SurroundingChunk(
            chunk_id=raw.get("chunk_id", ""),
            chunk_index=raw.get("chunk_index"),
            section_header=raw.get("section_header"),
            start_line=raw.get("start_line"),
            end_line=raw.get("end_line"),
            version_tag=raw.get("version_tag"),
            content=raw.get("content", ""),
        )

    before_chunks = [_to_surrounding(c) for c in surrounding.get("before", [])]
    after_chunks  = [_to_surrounding(c) for c in surrounding.get("after", [])]

    # Build document title from available metadata fields
    file_name: str = chunk_data.get("file_name") or ""
    document_title: str = (
        chunk_data.get("metadata", {}).get("document_title")
        or chunk_data.get("metadata", {}).get("title")
        or file_name
        or doc_id
        or "Unknown Document"
    )

    return ChunkContextResponse(
        # Chunk identity
        chunk_id=chunk_id,
        content=chunk_data.get("content", ""),
        section_header=chunk_data.get("section_header") or None,
        section_level=chunk_data.get("section_level"),
        start_line=chunk_data.get("start_line"),
        end_line=chunk_data.get("end_line"),
        chunk_index=chunk_index,
        token_count=chunk_data.get("token_count"),

        # Parent document provenance
        document_id=doc_id,
        document_title=document_title,
        version=chunk_data.get("version") or chunk_data.get("version_tag") or "latest",
        doc_type=chunk_data.get("doc_type") or "API_REFERENCE",
        source_url=chunk_data.get("source_url") or None,
        is_deprecated=bool(chunk_data.get("is_deprecated", False)),

        # Surrounding context
        surrounding_chunks_before=before_chunks,
        surrounding_chunks_after=after_chunks,

        # Raw metadata passthrough
        raw_metadata=chunk_data.get("metadata", {}),
    )

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException
from fastapi.concurrency import run_in_threadpool
from app.services.vector_store import vector_store
from app.core.logging import logger

router = APIRouter(prefix="/search", tags=["Search"])

@router.get("", response_model=List[Dict[str, Any]])
async def search_documents(
    query_string: str = Query(..., description="The search query text"),
    selected_version: Optional[str] = Query(None, description="Filter by API version tag"),
    doc_type: Optional[str] = Query(None, description="Filter by document type (e.g. API_REFERENCE)"),
    top_k: int = Query(5, ge=1, le=20, description="Number of results to return"),
    score_threshold: Optional[float] = Query(None, description="Minimum similarity score threshold")
):
    """
    Search endpoint that retrieves semantically scored document chunks 
    based on a user query and optional metadata filters (version, doc_type).
    """
    if not query_string.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty")
        
    try:
        # Offload the synchronous vector store query to a threadpool
        results = await run_in_threadpool(
            vector_store.query,
            query_text=query_string,
            version_tag=selected_version,
            doc_type=doc_type,
            top_k=top_k,
            score_threshold=score_threshold
        )
        return results
    except Exception as e:
        logger.error(f"Error during vector search: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while performing the search")

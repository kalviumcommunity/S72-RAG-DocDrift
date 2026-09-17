from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from fastapi.concurrency import run_in_threadpool
from app.schemas.intent import QueryIntentRequest, QueryIntentResponse
from app.services.query_intent import query_intent_analyzer
from app.core.logging import logger

router = APIRouter(prefix="/intent", tags=["Query Intent"])


@router.post("/analyze", response_model=QueryIntentResponse)
async def analyze_query_post(request: QueryIntentRequest):
    """
    Analyzes developer query to determine if it asks about a single version
    or compares versions, returning the targeted version list and intent classification.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty")

    try:
        # Offload analysis to threadpool in case LLM or external calls are invoked
        result = await run_in_threadpool(
            query_intent_analyzer.analyze,
            query=request.query,
            selected_version=request.selected_version,
            available_versions=request.available_versions,
            mode=request.mode or "hybrid"
        )
        return result
    except Exception as e:
        logger.error(f"Error during query intent analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze query intent: {str(e)}")


@router.get("/analyze", response_model=QueryIntentResponse)
async def analyze_query_get(
    q: str = Query(..., description="Developer question or search text"),
    selected_version: Optional[str] = Query(None, description="Active API version tag (e.g. v2.0)"),
    mode: str = Query("hybrid", description="Strategy: 'hybrid', 'regex', or 'llm'")
):
    """
    Quick GET endpoint for query intent analysis.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' cannot be empty")

    try:
        result = await run_in_threadpool(
            query_intent_analyzer.analyze,
            query=q,
            selected_version=selected_version,
            mode=mode
        )
        return result
    except Exception as e:
        logger.error(f"Error during query intent analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze query intent: {str(e)}")

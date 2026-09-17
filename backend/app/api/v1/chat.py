from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from fastapi.concurrency import run_in_threadpool
from app.schemas.chat import RAGQueryRequest, RAGQueryResponse
from app.schemas.faithfulness import (
    ClaimVerificationRequest,
    ClaimVerificationResult,
    AnswerFaithfulnessRequest,
    AnswerFaithfulnessReport,
)
from app.services.rag_pipeline import rag_pipeline
from app.services.query_intent import query_intent_analyzer
from app.services.vector_store import vector_store
from app.services.faithfulness_evaluator import faithfulness_evaluator
from app.core.logging import logger

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


@router.post("/rag", response_model=RAGQueryResponse)
async def generate_rag_answer(request: RAGQueryRequest):
    """
    Executes a fully grounded, version-aware RAG query.
    1. Analyzes intent to determine single-version vs multi-version comparison.
    2. Retrieves semantically relevant document chunks filtered by version.
    3. Generates an answer strictly grounded in the context with mandatory [^chunk_id] citations.
    4. Returns grounded answer, structured citation objects, and grounding validation.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty")

    try:
        # Step 1: Analyze query intent and extract target versions
        intent_res = await run_in_threadpool(
            query_intent_analyzer.analyze,
            query=request.query,
            selected_version=request.selected_version
        )

        # Step 2: Retrieve chunks if not provided in request
        target_versions: List[str] = (
            intent_res.target_versions
            if intent_res.target_versions
            else ([request.selected_version] if request.selected_version else [])
        )
        context_chunks = request.context_chunks
        if context_chunks is None:
            # Query vector store with targeted version filter
            context_chunks = await run_in_threadpool(
                vector_store.query,
                query_text=request.query,
                version_tag=target_versions if target_versions else None,
                top_k=request.top_k,
                score_threshold=request.score_threshold
            )

        chosen_version: Optional[str] = request.selected_version or (target_versions[0] if target_versions else None)

        # Step 3: Generate grounded response using LangChain / Gemini
        result = await run_in_threadpool(
            rag_pipeline.generate,
            query=request.query,
            context_chunks=context_chunks,
            selected_version=chosen_version,
            is_comparison=intent_res.is_comparison,
            use_langchain=request.use_langchain
        )

        # Merge intent analysis into query_analysis response
        result.query_analysis.update({
            "intent": intent_res.intent,
            "target_versions": intent_res.target_versions,
            "detected_endpoints": intent_res.detected_endpoints,
            "intent_confidence": intent_res.confidence,
        })

        return result

    except Exception as e:
        logger.error(f"Error in RAG generation pipeline: {str(e)}")
        raise HTTPException(status_code=500, detail=f"RAG generation failed: {str(e)}")


@router.get("/rag", response_model=RAGQueryResponse)
async def generate_rag_answer_get(
    q: str = Query(..., description="Developer query or question"),
    selected_version: Optional[str] = Query(None, description="Active API version (e.g. v2.0)"),
    top_k: int = Query(5, ge=1, le=20, description="Top K vector chunks to retrieve")
):
    """
    Quick GET endpoint for grounded RAG generation.
    """
    req = RAGQueryRequest(
        query=q,
        selected_version=selected_version,
        top_k=top_k
    )
    return await generate_rag_answer(req)


@router.post("/verify-claim", response_model=ClaimVerificationResult)
async def verify_claim_endpoint(request: ClaimVerificationRequest):
    """
    Compares an individual LLM-generated claim against a cited source chunk
    and returns a faithfulness score (0.0% - 100.0%) with grounding reasoning.
    """
    if not request.claim or not request.claim.strip():
        raise HTTPException(status_code=400, detail="Claim text cannot be empty")

    return await run_in_threadpool(
        faithfulness_evaluator.verify_claim,
        claim=request.claim,
        source_chunk=request.source_chunk,
        chunk_id=request.chunk_id
    )


@router.post("/verify-answer", response_model=AnswerFaithfulnessReport)
async def verify_answer_endpoint(request: AnswerFaithfulnessRequest):
    """
    Verifies all claims in a complete generated answer against the cited context chunks,
    returning an aggregate faithfulness percentage score and per-claim audit trail.
    """
    if not request.answer or not request.answer.strip():
        raise HTTPException(status_code=400, detail="Answer text cannot be empty")

    return await run_in_threadpool(
        faithfulness_evaluator.verify_answer,
        answer=request.answer,
        context_chunks=request.context_chunks,
        threshold=request.threshold
    )

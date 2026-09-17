import pytest
from app.core.prompts import (
    DOCDRIFT_SYSTEM_PROMPT,
    format_chunks_for_context,
    build_rag_user_prompt,
    extract_citation_tags,
)
from app.services.rag_pipeline import DocDriftRAGPipeline
from app.schemas.chat import RAGQueryResponse, RAGQueryRequest
from app.models.entities import DocTypeEnum


def test_system_prompt_rules():
    """Verify that the system prompt strictly specifies zero hallucination and [^chunk_id] tags."""
    assert "[^chunk_id]" in DOCDRIFT_SYSTEM_PROMPT
    assert "STRICT CONTEXT BOUNDARIES" in DOCDRIFT_SYSTEM_PROMPT
    assert "MANDATORY CITATION TAGS" in DOCDRIFT_SYSTEM_PROMPT
    assert "VERSION AWARENESS" in DOCDRIFT_SYSTEM_PROMPT


def test_format_chunks_for_context():
    chunks = [
        {
            "chunk_id": "chunk_auth_v2",
            "file_name": "auth_v2.md",
            "version": "v2.0",
            "section_header": "Authentication",
            "start_line": 1,
            "end_line": 15,
            "content": "In v2.0, use Authorization: Bearer <token>."
        },
        {
            "chunk_id": "chunk_auth_v1",
            "file_name": "auth_v1.md",
            "version": "v1.0",
            "section_header": "Authentication",
            "start_line": 1,
            "end_line": 8,
            "content": "In v1.0, use api_key in query string."
        }
    ]

    formatted = format_chunks_for_context(chunks)
    assert "Chunk ID: chunk_auth_v2" in formatted
    assert "Document: auth_v2.md" in formatted
    assert "Version: v2.0" in formatted
    assert "Section: Authentication (Lines: 1-15)" in formatted
    assert "In v2.0, use Authorization: Bearer <token>." in formatted

    assert "Chunk ID: chunk_auth_v1" in formatted
    assert "Version: v1.0" in formatted


def test_extract_citation_tags():
    text = (
        "In v2.0, authentication uses Bearer tokens[^chunk_123]. "
        "The api_key parameter from v1.0 is deprecated[^chunk_456][^chunk_789]."
    )
    tags = extract_citation_tags(text)
    assert tags == ["chunk_123", "chunk_456", "chunk_789"]

    # Deduplication check
    text_dup = "Claim one[^c1]. Claim two[^c1]."
    assert extract_citation_tags(text_dup) == ["c1"]


def test_extract_citations_metadata():
    pipeline = DocDriftRAGPipeline()
    context_chunks = [
        {
            "chunk_id": "chk_101",
            "doc_id": "doc_v2",
            "file_name": "api_v2.md",
            "version": "v2.0",
            "doc_type": "API_REFERENCE",
            "section_header": "Bearer Auth",
            "start_line": 10,
            "end_line": 25,
            "content": "Bearer authentication is required for all v2 endpoints.",
            "similarity_score": 0.98
        }
    ]

    answer = "All v2 endpoints require Bearer authentication[^chk_101]."
    citations = pipeline.extract_citations(answer, context_chunks)

    assert len(citations) == 1
    cit = citations[0]
    assert cit.chunk_id == "chk_101"
    assert cit.document_title == "api_v2.md"
    assert cit.version == "v2.0"
    assert cit.doc_type == DocTypeEnum.API_REFERENCE
    assert cit.section_header == "Bearer Auth"
    assert cit.start_line == 10
    assert cit.end_line == 25
    assert "Bearer authentication" in cit.excerpt


def test_validate_grounding():
    pipeline = DocDriftRAGPipeline()
    context_chunks = [
        {"chunk_id": "c1", "content": "Info 1"},
        {"chunk_id": "c2", "content": "Info 2"}
    ]

    # Valid grounded text
    valid_text = "Statement A[^c1] and Statement B[^c2]."
    v_res = pipeline.validate_grounding(valid_text, context_chunks)
    assert v_res["is_grounded"] is True
    assert v_res["fabricated_ids"] == []

    # Fabricated / hallucinated chunk tag
    hallucinated_text = "Statement C[^c1] and Unbacked claim[^fake_chunk_999]."
    h_res = pipeline.validate_grounding(hallucinated_text, context_chunks)
    assert h_res["is_grounded"] is False
    assert "fake_chunk_999" in h_res["fabricated_ids"]


def test_strict_context_refusal_on_empty_chunks():
    pipeline = DocDriftRAGPipeline()
    res = pipeline.generate(
        query="How do I use webhooks in v3?",
        context_chunks=[],
        selected_version="v3.0"
    )
    assert "does not contain sufficient information" in res.answer
    assert "v3.0" in res.answer
    assert len(res.citations) == 0


def test_rag_generation_single_version():
    pipeline = DocDriftRAGPipeline()
    context_chunks = [
        {
            "chunk_id": "chunk_v2_auth",
            "file_name": "auth.md",
            "version": "v2.0",
            "section_header": "Authentication",
            "start_line": 1,
            "end_line": 10,
            "content": "In v2.0, authentication is handled via Bearer tokens in the Authorization header."
        }
    ]

    res = pipeline.generate(
        query="How do I authenticate with the API in v2?",
        context_chunks=context_chunks,
        selected_version="v2.0",
        is_comparison=False
    )

    assert isinstance(res, RAGQueryResponse)
    assert "[^chunk_v2_auth]" in res.answer
    assert len(res.citations) == 1
    assert res.citations[0].chunk_id == "chunk_v2_auth"
    assert res.is_grounded is True


def test_rag_generation_version_comparison():
    pipeline = DocDriftRAGPipeline()
    context_chunks = [
        {
            "chunk_id": "chunk_v1_limit",
            "file_name": "v1_charges.md",
            "version": "v1.0",
            "section_header": "List Charges",
            "content": "The default limit for listing charges is 10."
        },
        {
            "chunk_id": "chunk_v2_limit",
            "file_name": "v2_payments.md",
            "version": "v2.0",
            "section_header": "List Payments",
            "content": "The default limit for listing payments is 20."
        }
    ]

    res = pipeline.generate(
        query="What is the default limit for charges in v1 vs v2?",
        context_chunks=context_chunks,
        is_comparison=True
    )

    assert isinstance(res, RAGQueryResponse)
    assert "[^chunk_v1_limit]" in res.answer
    assert "[^chunk_v2_limit]" in res.answer
    assert len(res.citations) == 2
    cited_ids = {c.chunk_id for c in res.citations}
    assert cited_ids == {"chunk_v1_limit", "chunk_v2_limit"}
    assert res.is_grounded is True


def test_api_chat_rag_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # Test POST /api/v1/chat/rag with explicit context chunks
    payload = {
        "query": "How do I authenticate with Bearer tokens in v2?",
        "selected_version": "v2.0",
        "context_chunks": [
            {
                "chunk_id": "chk_auth",
                "file_name": "auth.md",
                "version": "v2.0",
                "section_header": "Bearer Auth",
                "content": "Pass Bearer token in the Authorization header."
            }
        ]
    }

    resp = client.post("/api/v1/chat/rag", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert "answer" in data
    assert "[^chk_auth]" in data["answer"]
    assert len(data["citations"]) == 1
    assert data["citations"][0]["chunk_id"] == "chk_auth"
    assert data["is_grounded"] is True

    # Test GET /api/v1/chat/rag endpoint
    resp_get = client.get("/api/v1/chat/rag?q=How+to+authenticate+in+v2%3F")
    assert resp_get.status_code == 200
    get_data = resp_get.json()
    assert "answer" in get_data

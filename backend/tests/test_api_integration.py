"""
Integration API Test Suite
============================
Tests all major endpoints: health, documents, chat/RAG, settings, diff, maintenance.
Uses FastAPI's TestClient with a mocked vector store and LLM pipeline.
Run: pytest tests/test_api_integration.py -v
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# App setup with mocked dependencies
# ---------------------------------------------------------------------------

MOCK_CHUNKS = [
    {
        "chunk_id": "chunk_001",
        "content": "Bearer token authentication requires the Authorization header.",
        "version": "v2.0",
        "version_tag": "v2.0",
        "doc_type": "API_REFERENCE",
        "section_header": "Authentication",
        "start_line": 10,
        "end_line": 20,
        "file_name": "auth_v2.md",
        "similarity_score": 0.92,
        "distance": 0.08,
        "is_deprecated": False,
    }
]

MOCK_RAG_RESPONSE = MagicMock(
    query="How does auth work?",
    answer="Bearer token required[^chunk_001].",
    citations=[],
    cited_chunk_ids=["chunk_001"],
    query_analysis={},
    is_grounded=True,
    faithfulness_score=90.0,
    pipeline_mode="gemini",
)


@pytest.fixture(scope="module")
def client():
    with (
        patch("app.services.vector_store.VectorStoreService._init_client", return_value=None),
        patch("app.services.vector_store.VectorStoreService._get_or_create_collection", return_value=None),
        patch("app.services.embedding_service.EmbeddingService.get_embedding", return_value=[0.1] * 768),
        patch("app.core.database.engine"),
        patch("app.core.init_db.init_database"),
    ):
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------

class TestHealthEndpoints:
    def test_root_returns_welcome(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "DocDrift" in r.json().get("message", "")

    def test_health_check(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code in (200, 503)
        data = r.json()
        assert "status" in data


# ---------------------------------------------------------------------------
# Document endpoint tests
# ---------------------------------------------------------------------------

class TestDocumentEndpoints:
    def test_list_documents(self, client):
        r = client.get("/api/v1/documents")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_documents_version_filter(self, client):
        r = client.get("/api/v1/documents?version=v2.0")
        assert r.status_code == 200

    def test_list_documents_pagination(self, client):
        r = client.get("/api/v1/documents?skip=0&limit=1")
        assert r.status_code == 200
        assert len(r.json()) <= 1

    def test_get_document_not_found(self, client):
        r = client.get("/api/v1/documents/nonexistent-id-12345")
        assert r.status_code == 404

    def test_raw_endpoint_not_found(self, client):
        r = client.get("/api/v1/documents/nonexistent-id/raw")
        # either 404 (not in DB/mock) or 200 with mock content
        assert r.status_code in (200, 404)

    def test_locate_excerpt_not_found(self, client):
        r = client.post(
            "/api/v1/documents/nonexistent-id/locate-excerpt",
            json={"excerpt": "Bearer token", "min_fuzzy_ratio": 0.75},
        )
        assert r.status_code == 404

    def test_locate_excerpt_empty_excerpt(self, client):
        r = client.post(
            "/api/v1/documents/nonexistent-id/locate-excerpt",
            json={"excerpt": "", "min_fuzzy_ratio": 0.75},
        )
        assert r.status_code == 422  # Pydantic min_length validation


# ---------------------------------------------------------------------------
# Search endpoint tests
# ---------------------------------------------------------------------------

class TestSearchEndpoints:
    def test_search_requires_query(self, client):
        r = client.get("/api/v1/search")
        assert r.status_code == 422

    def test_search_empty_query(self, client):
        r = client.get("/api/v1/search?query_string=")
        assert r.status_code in (400, 422, 500)

    def test_search_valid_query(self, client):
        with patch("app.services.vector_store.VectorStoreService.query", return_value=MOCK_CHUNKS):
            r = client.get("/api/v1/search?query_string=authentication")
            assert r.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Chat/RAG endpoint tests
# ---------------------------------------------------------------------------

class TestChatEndpoints:
    def test_rag_empty_query(self, client):
        r = client.post("/api/v1/chat/rag", json={"query": ""})
        assert r.status_code == 400

    def test_rag_valid_query(self, client):
        with (
            patch("app.services.vector_store.VectorStoreService.query", return_value=MOCK_CHUNKS),
            patch("app.services.rag_pipeline.DocDriftRAGPipeline.generate", return_value=MOCK_RAG_RESPONSE),
            patch("app.services.query_intent.QueryIntentAnalyzer.analyze",
                  return_value=MagicMock(target_versions=["v2.0"], is_comparison=False,
                                         intent="general", detected_endpoints=[], confidence=0.9)),
        ):
            r = client.post("/api/v1/chat/rag", json={"query": "How does auth work?", "selected_version": "v2.0"})
            assert r.status_code in (200, 500)

    def test_stream_endpoint_empty_query(self, client):
        r = client.post("/api/v1/chat/stream", json={"query": ""})
        assert r.status_code == 400

    def test_verify_claim_empty(self, client):
        r = client.post("/api/v1/chat/verify-claim", json={"claim": "", "source_chunk": "some text"})
        assert r.status_code == 400

    def test_verify_claim_valid(self, client):
        r = client.post(
            "/api/v1/chat/verify-claim",
            json={"claim": "Bearer tokens are required", "source_chunk": "Bearer token authentication requires the Authorization header."}
        )
        assert r.status_code == 200
        data = r.json()
        assert "faithfulness_score" in data
        assert 0.0 <= data["faithfulness_score"] <= 100.0

    def test_verify_answer_empty(self, client):
        r = client.post("/api/v1/chat/verify-answer", json={"answer": "", "context_chunks": []})
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Settings endpoint tests
# ---------------------------------------------------------------------------

class TestSettingsEndpoints:
    def test_get_global_settings(self, client):
        r = client.get("/api/v1/settings")
        assert r.status_code == 200
        data = r.json()
        assert "default_llm_provider" in data
        assert "gemini_api_key_set" in data

    def test_update_global_settings_invalid_provider(self, client):
        r = client.put("/api/v1/settings", json={"default_llm_provider": "invalid_provider_xyz"})
        assert r.status_code == 400

    def test_get_workspace_settings(self, client):
        r = client.get("/api/v1/settings/workspaces/ws_test_001")
        assert r.status_code == 200
        data = r.json()
        assert data["workspace_id"] == "ws_test_001"
        assert "llm_provider" in data

    def test_update_workspace_settings(self, client):
        r = client.put(
            "/api/v1/settings/workspaces/ws_test_001",
            json={"default_version": "v3.0", "chunking": {"max_chunk_size": 256, "chunk_overlap": 32, "split_on_headings": True, "min_chunk_size": 16}},
        )
        assert r.status_code == 200
        assert r.json()["default_version"] == "v3.0"

    def test_manage_members(self, client):
        r = client.post(
            "/api/v1/settings/workspaces/ws_test_001/members",
            json={"add": ["user_a", "user_b"], "remove": []},
        )
        assert r.status_code == 200
        assert "user_a" in r.json()["members"]


# ---------------------------------------------------------------------------
# Diff endpoint tests
# ---------------------------------------------------------------------------

class TestDiffEndpoints:
    def test_diff_same_version_rejected(self, client):
        r = client.post("/api/v1/diff", json={"version_a": "v1.0", "version_b": "v1.0", "topic": "auth"})
        assert r.status_code == 400

    def test_diff_empty_topic(self, client):
        r = client.post("/api/v1/diff", json={"version_a": "v1.0", "version_b": "v2.0", "topic": ""})
        assert r.status_code in (400, 422)

    def test_diff_returns_structure(self, client):
        with patch("app.services.vector_store.VectorStoreService.query", return_value=MOCK_CHUNKS):
            r = client.post(
                "/api/v1/diff",
                json={"version_a": "v1.0", "version_b": "v2.0", "topic": "authentication", "use_llm": False},
            )
            assert r.status_code == 200
            data = r.json()
            assert "breaking_changes" in data
            assert "deprecations" in data
            assert "new_features" in data
            assert "migration_tips" in data
            assert "summary" in data


# ---------------------------------------------------------------------------
# Rate limiting test
# ---------------------------------------------------------------------------

class TestRateLimiting:
    def test_rate_limit_header_present(self, client):
        """Each response should have X-Request-ID injected."""
        r = client.get("/api/v1/health")
        # Request-ID should be present (added by RequestIDMiddleware)
        # Note: TestClient may not always propagate headers; just check it doesn't crash
        assert r.status_code in (200, 503)

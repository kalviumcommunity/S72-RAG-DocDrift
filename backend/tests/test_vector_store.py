import pytest
from app.services.embedding_service import embedding_service, cosine_similarity
from app.services.vector_store import VectorStoreService


def test_embedding_generation():
    text = "API v2 Authentication using OAuth2"
    emb = embedding_service.get_embedding(text)
    assert isinstance(emb, list)
    assert len(emb) > 0


def test_cosine_similarity_calculation():
    vec_a = [1.0, 0.0, 0.0]
    vec_b = [1.0, 0.0, 0.0]
    vec_c = [0.0, 1.0, 0.0]

    assert cosine_similarity(vec_a, vec_b) == pytest.approx(1.0)
    assert cosine_similarity(vec_a, vec_c) == pytest.approx(0.0)


def test_vector_store_indexing_and_filtering(tmp_path):
    persist_dir = str(tmp_path / "chroma_test")
    vs = VectorStoreService(collection_name="test_collection", persist_directory=persist_dir)

    ids = ["c1", "c2"]
    docs = [
        "v1 endpoint GET /users offset pagination",
        "v2 endpoint GET /users cursor pagination"
    ]
    metas = [
        {"version_tag": "v1.0", "doc_type": "API_REFERENCE"},
        {"version_tag": "v2.0", "doc_type": "API_REFERENCE"}
    ]

    count = vs.add_chunks(ids=ids, documents=docs, metadatas=metas)
    assert count == 2

    # Query with v1.0 filter
    results_v1 = vs.query(query_text="users pagination", version_tag="v1.0", top_k=1)
    assert len(results_v1) == 1
    assert results_v1[0]["version_tag"] == "v1.0"
    assert "offset" in results_v1[0]["content"]

    # Query with v2.0 filter
    results_v2 = vs.query(query_text="users pagination", version_tag="v2.0", top_k=1)
    assert len(results_v2) == 1
    assert results_v2[0]["version_tag"] == "v2.0"
    assert "cursor" in results_v2[0]["content"]

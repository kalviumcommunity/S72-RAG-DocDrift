import sys
import os

# Add backend directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.embedding_service import embedding_service, cosine_similarity
from app.services.vector_store import VectorStoreService


def run_embedding_vector_test():
    print("=" * 60)
    print("🚀 DOCDRIFT: TESTING EMBEDDINGS & VECTOR STORE (BHUMIT DAY 1)")
    print("=" * 60)

    # 1. Test Single Embedding & Cosine Similarity
    text_a = "In v1.0, authenticate using HTTP Basic Auth with api_key and secret."
    text_b = "In v2.0, authenticate using OAuth 2.0 Bearer JWT tokens in Authorization header."
    text_c = "To send a request with basic credentials in v1, pass the username in Authorization."

    print("\n[Step 1] Generating Embeddings...")
    emb_a = embedding_service.get_embedding(text_a)
    emb_b = embedding_service.get_embedding(text_b)
    emb_c = embedding_service.get_embedding(text_c)

    print(f"✓ Embedding vector dimension: {len(emb_a)}")

    sim_a_c = cosine_similarity(emb_a, emb_c)
    sim_a_b = cosine_similarity(emb_a, emb_b)

    print(f"✓ Cosine Similarity (v1 Auth vs v1 Credentials): {sim_a_c:.4f}")
    print(f"✓ Cosine Similarity (v1 Auth vs v2 Bearer Auth):  {sim_a_b:.4f}")
    assert sim_a_c > sim_a_b, "Related documentation should have higher cosine similarity!"

    # 2. Test Storing in Vector Store (ChromaDB)
    print("\n[Step 2] Initializing Vector Store...")
    vs = VectorStoreService(collection_name="test_docdrift_chunks", persist_directory="./test_chroma_data")

    sample_chunks = [
        {
            "id": "chunk-v1-auth",
            "text": "POST /v1/auth/login - Requires username and password. Returns session cookie.",
            "meta": {"document_id": "doc-1", "version_tag": "v1.0", "doc_type": "API_REFERENCE", "section_header": "Authentication"}
        },
        {
            "id": "chunk-v1-users",
            "text": "GET /v1/users - List all users. Pagination is offset-based using 'page' query param.",
            "meta": {"document_id": "doc-1", "version_tag": "v1.0", "doc_type": "API_REFERENCE", "section_header": "Users API"}
        },
        {
            "id": "chunk-v2-auth",
            "text": "POST /v2/oauth/token - Requires client_id, client_secret, grant_type. Returns Bearer token.",
            "meta": {"document_id": "doc-2", "version_tag": "v2.0", "doc_type": "API_REFERENCE", "section_header": "OAuth 2.0 Token"}
        },
        {
            "id": "chunk-v2-users",
            "text": "GET /v2/users - List users. Pagination is cursor-based using 'starting_after' parameter.",
            "meta": {"document_id": "doc-2", "version_tag": "v2.0", "doc_type": "API_REFERENCE", "section_header": "Users API"}
        },
        {
            "id": "chunk-migration-guide",
            "text": "Migration Guide from v1 to v2: Basic auth is deprecated. Switch to Bearer tokens in /v2/oauth/token.",
            "meta": {"document_id": "doc-3", "version_tag": "v2.0", "doc_type": "MIGRATION_GUIDE", "section_header": "Auth Migration"}
        }
    ]

    ids = [c["id"] for c in sample_chunks]
    texts = [c["text"] for c in sample_chunks]
    metadatas = [c["meta"] for c in sample_chunks]

    indexed_count = vs.add_chunks(ids=ids, documents=texts, metadatas=metadatas)
    print(f"✓ Indexed {indexed_count} chunks into ChromaDB collection '{vs.collection_name}'. Total: {vs.count()}")

    # 3. Test Version-Filtered Search
    print("\n[Step 3] Testing Version-Filtered Retrieval...")
    query = "How to authenticate user credentials?"

    print(f"\nQuery: '{query}' -> Filter: version_tag='v1.0'")
    results_v1 = vs.query(query_text=query, version_tag="v1.0", top_k=2)
    for r in results_v1:
        print(f"  [{r['version_tag']}] (Score: {r['similarity_score']}) {r['section_header']}: {r['content']}")
        assert r["version_tag"] == "v1.0", f"Expected v1.0 result, got {r['version_tag']}"

    print(f"\nQuery: '{query}' -> Filter: version_tag='v2.0'")
    results_v2 = vs.query(query_text=query, version_tag="v2.0", top_k=2)
    for r in results_v2:
        print(f"  [{r['version_tag']}] (Score: {r['similarity_score']}) {r['section_header']}: {r['content']}")
        assert r["version_tag"] == "v2.0", f"Expected v2.0 result, got {r['version_tag']}"

    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED! Embedding & Vector Store Pipeline is 100% Operational.")
    print("=" * 60)


if __name__ == "__main__":
    run_embedding_vector_test()

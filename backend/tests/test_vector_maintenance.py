import pytest
from app.services.vector_store import vector_store
from app.services.vector_maintenance import (
    vector_maintenance,
    clean_delete_chunks_by_doc_id,
    batch_insert_embeddings,
    zero_downtime_update_document,
)
from app.schemas.vector_payload import VectorChunkMetadata


@pytest.fixture(autouse=True)
def clean_test_collections():
    """Cleanup test documents before and after each test."""
    test_docs = ["doc_test_101", "doc_test_102", "doc_zero_dt_1", "doc_zero_dt_2"]
    for d in test_docs:
        vector_maintenance.clean_delete_chunks_by_doc_id(d)
    yield
    for d in test_docs:
        vector_maintenance.clean_delete_chunks_by_doc_id(d)


def test_batch_insert_embeddings():
    """Tests chunked batch insertion with automatic embedding generation."""
    chunks = [
        {
            "id": f"chunk_m_{i}",
            "content": f"Documentation text chunk number {i} for maintenance testing.",
            "metadata": {"doc_id": "doc_test_101", "version": "v1.0", "section_header": f"Header {i}"}
        }
        for i in range(12)
    ]

    # Batch size 5 should process in ceil(12/5) = 3 batches
    res = batch_insert_embeddings(chunks=chunks, batch_size=5)

    assert res.total_chunks == 12
    assert res.inserted_count == 12
    assert res.batches_processed == 3
    assert res.batch_size == 5
    assert len(res.errors) == 0

    # Verify chunks are present in vector store
    found_ids = vector_maintenance.get_chunk_ids_by_doc_id("doc_test_101")
    assert len(found_ids) == 12
    assert "chunk_m_0" in found_ids
    assert "chunk_m_11" in found_ids


def test_clean_delete_chunks_by_doc_id():
    """Tests clean deletion of chunks by doc_id in batches with verification."""
    # Setup chunks across two different documents
    chunks_a = [
        {
            "id": f"docA_c{i}",
            "content": f"Document A content chunk {i}",
            "metadata": {"doc_id": "doc_test_101", "version": "v1.0"}
        }
        for i in range(8)
    ]
    chunks_b = [
        {
            "id": f"docB_c{i}",
            "content": f"Document B content chunk {i}",
            "metadata": {"doc_id": "doc_test_102", "version": "v1.0"}
        }
        for i in range(4)
    ]

    batch_insert_embeddings(chunks=chunks_a + chunks_b, batch_size=10)

    assert len(vector_maintenance.get_chunk_ids_by_doc_id("doc_test_101")) == 8
    assert len(vector_maintenance.get_chunk_ids_by_doc_id("doc_test_102")) == 4

    # Clean delete doc_test_101 with batch size 3 (tests multi-batch deletion)
    del_res = clean_delete_chunks_by_doc_id("doc_test_101", batch_size=3)

    assert del_res.success is True
    assert del_res.deleted_count == 8
    assert del_res.remaining_count == 0

    # Verify doc_test_101 is gone but doc_test_102 is untouched
    assert len(vector_maintenance.get_chunk_ids_by_doc_id("doc_test_101")) == 0
    assert len(vector_maintenance.get_chunk_ids_by_doc_id("doc_test_102")) == 4


def test_delete_nonexistent_doc_id():
    """Deleting a document ID with no chunks returns 0 deleted and success."""
    del_res = clean_delete_chunks_by_doc_id("non_existent_doc_999")
    assert del_res.success is True
    assert del_res.deleted_count == 0
    assert del_res.remaining_count == 0


def test_zero_downtime_update_document():
    """
    Simulates zero-downtime document update:
    1. Initial version has chunks [c1, c2, c3]
    2. Updated version has chunks [c2_updated, c4, c5]
    3. Update must stage new chunks, ensure queries never see empty results,
       and prune obsolete chunks [c1, c3].
    """
    doc_id = "doc_zero_dt_1"

    # Step 1: Initial chunks
    initial_chunks = [
        {
            "id": f"{doc_id}_c1",
            "content": "Initial chunk 1 description for API endpoint /auth/login.",
            "metadata": {"doc_id": doc_id, "version": "v1.0"}
        },
        {
            "id": f"{doc_id}_c2",
            "content": "Initial chunk 2 description for API endpoint /users/me.",
            "metadata": {"doc_id": doc_id, "version": "v1.0"}
        },
        {
            "id": f"{doc_id}_c3",
            "content": "Initial chunk 3 description for deprecated endpoint /auth/legacy.",
            "metadata": {"doc_id": doc_id, "version": "v1.0"}
        }
    ]
    batch_insert_embeddings(chunks=initial_chunks)

    # Confirm initial count is 3
    existing_ids = vector_maintenance.get_chunk_ids_by_doc_id(doc_id)
    assert set(existing_ids) == {f"{doc_id}_c1", f"{doc_id}_c2", f"{doc_id}_c3"}

    # Step 2: New revision replaces c1 & c3 with c4 & c5, and retains/updates c2
    new_chunks = [
        {
            "id": f"{doc_id}_c2",
            "content": "Updated chunk 2 description for API endpoint /users/me with new OAuth fields.",
            "metadata": {"doc_id": doc_id, "version": "v2.0"}
        },
        {
            "id": f"{doc_id}_c4",
            "content": "New chunk 4 description for OAuth2 refresh token endpoint /auth/refresh.",
            "metadata": {"doc_id": doc_id, "version": "v2.0"}
        },
        {
            "id": f"{doc_id}_c5",
            "content": "New chunk 5 description for rate limiting headers in v2.0.",
            "metadata": {"doc_id": doc_id, "version": "v2.0"}
        }
    ]

    # Perform zero downtime update
    update_res = zero_downtime_update_document(doc_id=doc_id, new_chunks=new_chunks, batch_size=2)

    assert update_res.status == "success"
    assert update_res.inserted_count == 3
    assert update_res.deleted_stale_count == 2  # c1 and c3 pruned
    assert update_res.active_chunk_count == 3

    # Verify active chunks now contain only c2, c4, c5
    current_ids = set(vector_maintenance.get_chunk_ids_by_doc_id(doc_id))
    assert current_ids == {f"{doc_id}_c2", f"{doc_id}_c4", f"{doc_id}_c5"}
    assert f"{doc_id}_c1" not in current_ids
    assert f"{doc_id}_c3" not in current_ids


def test_vector_store_service_delegates():
    """Tests that vector_store convenience maintenance methods delegate correctly."""
    doc_id = "doc_zero_dt_2"

    chunks = [
        {
            "id": f"{doc_id}_chunk_0",
            "content": "Sample content indexed via vector_store convenience wrapper.",
            "metadata": {"doc_id": doc_id, "version": "v1.0"}
        }
    ]

    # Test batch_insert delegate
    ins = vector_store.batch_insert(chunks=chunks)
    assert ins.inserted_count == 1

    # Test update_document_zero_downtime delegate
    updated_chunks = [
        {
            "id": f"{doc_id}_chunk_1",
            "content": "Updated content indexed via vector_store zero-downtime wrapper.",
            "metadata": {"doc_id": doc_id, "version": "v2.0"}
        }
    ]
    upd = vector_store.update_document_zero_downtime(doc_id=doc_id, new_chunks=updated_chunks)
    assert upd.status == "success"
    assert upd.inserted_count == 1
    assert upd.deleted_stale_count == 1

    # Test clean_delete_by_doc_id delegate
    d_res = vector_store.clean_delete_by_doc_id(doc_id=doc_id)
    assert d_res.success is True
    assert d_res.deleted_count == 1
    assert d_res.remaining_count == 0


def test_blue_green_reindex():
    """Tests shadow staging collection creation for blue-green maintenance."""
    chunks = [
        {
            "id": f"bg_chunk_{i}",
            "content": f"Blue-green dataset item {i}",
            "metadata": {"doc_id": "doc_bg_1", "version": "v1.0"}
        }
        for i in range(5)
    ]
    bg_res = vector_maintenance.blue_green_reindex(new_chunks=chunks, batch_size=2)
    assert bg_res["status"] == "success"
    assert bg_res["inserted_count"] == 5
    assert "staging_" in bg_res["staging_collection"]

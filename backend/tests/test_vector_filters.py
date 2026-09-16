import pytest
from app.schemas.vector_payload import VectorChunkMetadata, VectorFilterQuery
from app.services.vector_filter import (
    build_version_filter,
    build_composite_filter,
    build_version_diff_filter,
    normalize_version_tag
)


def test_normalize_version():
    assert normalize_version_tag("1.0") == "v1.0"
    assert normalize_version_tag("v2.1") == "v2.1"
    assert normalize_version_tag("latest") == "latest"


def test_single_version_filter():
    f = build_version_filter("v2.1")
    assert f == {"version": "v2.1"}


def test_multi_version_filter():
    f = build_version_filter(["v1.0", "v2.0"])
    assert f == {"version": {"$in": ["v1.0", "v2.0"]}}


def test_version_diff_filter():
    f = build_version_diff_filter("1.0", "2.0")
    assert f == {"version": {"$in": ["v1.0", "v2.0"]}}


def test_composite_filter():
    q = VectorFilterQuery(version="v2.1", doc_type="API_REFERENCE", is_deprecated=False)
    f = build_composite_filter(query=q)
    assert "$and" in f
    assert len(f["$and"]) == 3


def test_vector_chunk_metadata_serialization():
    meta = VectorChunkMetadata(
        doc_id="doc-1",
        version="v2.1",
        doc_type="API_REFERENCE",
        section_header="Auth",
        start_line=1,
        end_line=10,
        file_name="auth.md"
    )
    d = meta.to_chroma_dict()
    assert d["version"] == "v2.1"
    assert d["start_line"] == 1
    assert d["end_line"] == 10

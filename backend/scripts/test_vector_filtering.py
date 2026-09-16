import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.vector_payload import VectorChunkMetadata, VectorFilterQuery
from app.services.vector_filter import (
    build_version_filter,
    build_composite_filter,
    build_version_diff_filter,
    normalize_version_tag
)


def run_filter_syntax_tests():
    print("=" * 65)
    print("🚀 DOCDRIFT: TESTING VECTOR METADATA FILTER SYNTAX (BHUMIT DAY 2)")
    print("=" * 65)

    # 1. Version Normalization
    print("\n[Test 1] Version Normalization:")
    assert normalize_version_tag("2.1") == "v2.1"
    assert normalize_version_tag("v2.1") == "v2.1"
    assert normalize_version_tag("v3.0.0-beta") == "v3.0.0-beta"
    assert normalize_version_tag("latest") == "latest"
    assert normalize_version_tag("all") == "all"
    print("  ✓ All version normalization rules passed!")

    # 2. Single Version Filter Syntax
    print("\n[Test 2] Single Version Filter Syntax:")
    f_single = build_version_filter("v2.1")
    print(f"  Input: 'v2.1' -> ChromaDB where-clause: {f_single}")
    assert f_single == {"version": "v2.1"}

    # 3. Multi-Version Filter Syntax (for cross-version queries)
    print("\n[Test 3] Multi-Version ($in) Filter Syntax:")
    f_multi = build_version_filter(["v1.0", "v2.0"])
    print(f"  Input: ['v1.0', 'v2.0'] -> ChromaDB where-clause: {f_multi}")
    assert f_multi == {"version": {"$in": ["v1.0", "v2.0"]}}

    # 4. Version Diff Filter
    print("\n[Test 4] Version Diff Filter:")
    f_diff = build_version_diff_filter("1.0", "2.0")
    print(f"  Input: '1.0' vs '2.0' -> ChromaDB where-clause: {f_diff}")
    assert f_diff == {"version": {"$in": ["v1.0", "v2.0"]}}

    # 5. Composite Filter (Version + DocType + Deprecation)
    print("\n[Test 5] Composite Filter ($and):")
    query_params = VectorFilterQuery(
        version="v2.1",
        doc_type="API_REFERENCE",
        is_deprecated=False
    )
    f_comp = build_composite_filter(query=query_params)
    print(f"  Input: {query_params.model_dump(exclude_none=True)}")
    print(f"  -> Generated ChromaDB where-clause:\n     {f_comp}")
    
    assert "$and" in f_comp
    assert {"version": "v2.1"} in f_comp["$and"]
    assert {"doc_type": "API_REFERENCE"} in f_comp["$and"]
    assert {"is_deprecated": False} in f_comp["$and"]

    # 6. VectorChunkMetadata Serialization
    print("\n[Test 6] VectorChunkMetadata Serialization & Flattening:")
    meta = VectorChunkMetadata(
        doc_id="doc-12345",
        version="v2.1",
        doc_type="API_REFERENCE",
        section_header="Authentication > Bearer Tokens",
        section_level=2,
        start_line=45,
        end_line=78,
        start_char_offset=1200,
        end_char_offset=2150,
        file_name="auth_v2.md",
        endpoint_path="/api/v2/oauth/token",
        http_method="POST",
        is_deprecated=False,
        tags=["auth", "oauth2", "security"]
    )
    chroma_dict = meta.to_chroma_dict()
    print("  ✓ Flattened ChromaDB payload:")
    for k, v in chroma_dict.items():
        print(f"    - {k}: {v} ({type(v).__name__})")
        assert isinstance(v, (str, int, float, bool)), f"Non-primitive type found for {k}: {type(v)}"

    print("\n" + "=" * 65)
    print("🎉 ALL FILTER SYNTAX TESTS PASSED! Ready for Vector DB Integration.")
    print("=" * 65)


if __name__ == "__main__":
    run_filter_syntax_tests()

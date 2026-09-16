from typing import Dict, Any, Optional, List, Union
from app.schemas.vector_payload import VectorFilterQuery
from app.core.logging import logger


def normalize_version_tag(version: str) -> str:
    """
    Normalizes version string representation (e.g., '2.1' -> 'v2.1', 'latest' -> 'latest').
    """
    if not version:
        return "latest"
    v = version.strip().lower()
    if v in ["latest", "all"]:
        return v
    if not v.startswith("v") and v[0].isdigit():
        return f"v{v}"
    return v


def build_version_filter(version: Union[str, List[str]]) -> Optional[Dict[str, Any]]:
    """
    Constructs a ChromaDB-compatible where-clause filter for a specific version or list of versions.
    Examples:
      - Single: {"version": "v2.1"}
      - Multiple: {"version": {"$in": ["v1.0", "v2.0"]}}
    """
    if not version:
        return None

    if isinstance(version, str):
        normalized = normalize_version_tag(version)
        if normalized == "all":
            return None
        return {"version": normalized}

    elif isinstance(version, (list, tuple, set)):
        normalized_list = [normalize_version_tag(v) for v in version if v and normalize_version_tag(v) != "all"]
        if not normalized_list:
            return None
        if len(normalized_list) == 1:
            return {"version": normalized_list[0]}
        return {"version": {"$in": normalized_list}}

    return None


def build_version_diff_filter(version_a: str, version_b: str) -> Dict[str, Any]:
    """
    Constructs a filter that matches documentation from either of two versions for side-by-side comparison.
    """
    norm_a = normalize_version_tag(version_a)
    norm_b = normalize_version_tag(version_b)
    return {"version": {"$in": [norm_a, norm_b]}}


def build_composite_filter(
    query: Optional[VectorFilterQuery] = None,
    version: Optional[Union[str, List[str]]] = None,
    doc_type: Optional[Union[str, List[str]]] = None,
    doc_id: Optional[str] = None,
    is_deprecated: Optional[bool] = None,
    endpoint_path: Optional[str] = None,
    http_method: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Builds a composite ChromaDB where-clause with multiple conditions combined using '$and'.
    ChromaDB syntax rule: If more than 1 top-level condition exists, they MUST be wrapped in {"$and": [...]}.
    """
    conditions: List[Dict[str, Any]] = []

    # Merge query object if provided
    if query:
        version = version or query.version
        doc_type = doc_type or query.doc_type
        doc_id = doc_id or query.doc_id
        is_deprecated = is_deprecated if is_deprecated is not None else query.is_deprecated
        endpoint_path = endpoint_path or query.endpoint_path
        http_method = http_method or query.http_method

    # 1. Version Condition
    if version:
        v_filter = build_version_filter(version)
        if v_filter:
            conditions.append(v_filter)

    # 2. Doc Type Condition
    if doc_type:
        if isinstance(doc_type, str):
            conditions.append({"doc_type": doc_type.upper()})
        elif isinstance(doc_type, (list, tuple, set)):
            types = [t.upper() for t in doc_type if t]
            if len(types) == 1:
                conditions.append({"doc_type": types[0]})
            elif len(types) > 1:
                conditions.append({"doc_type": {"$in": types}})

    # 3. Doc ID Condition
    if doc_id:
        conditions.append({"doc_id": str(doc_id)})

    # 4. Deprecation Condition
    if is_deprecated is not None:
        conditions.append({"is_deprecated": bool(is_deprecated)})

    # 5. Endpoint Path Condition
    if endpoint_path:
        conditions.append({"endpoint_path": str(endpoint_path)})

    # 6. HTTP Method Condition
    if http_method:
        conditions.append({"http_method": str(http_method).upper()})

    # Assemble ChromaDB Filter Clause
    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    
    return {"$and": conditions}

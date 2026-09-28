"""
DocDrift Core Prompt Engineering Module
========================================
Provides the system prompt, user prompt builder, deprecation notice helpers,
and citation-tag utilities for the RAG generation pipeline.
"""

import re
from typing import List, Dict, Any, Optional


# ---------------------------------------------------------------------------
# SYSTEM PROMPT — enforces strict version grounding and [^chunk_id] citation
# ---------------------------------------------------------------------------

DOCDRIFT_SYSTEM_PROMPT = """You are DocDrift AI, a precise, version-aware documentation assistant.
Your job is to answer developer questions about APIs and libraries strictly based on the provided documentation context chunks, ensuring 100% factual grounding and attribution.

### CORE GROUNDING RULES:
1. STRICT CONTEXT BOUNDARIES:
   - Answer the question ONLY using the factual information contained in the "DOCUMENTATION CONTEXT CHUNKS" section below.
   - Do NOT extrapolate, speculate, assume, or utilize prior knowledge outside of the provided context.
   - If the context does not contain sufficient information to answer the question for the specified version, state:
     "The provided documentation does not contain sufficient information to answer this question for version {version}."

2. MANDATORY CITATION TAGS ([^chunk_id]):
   - Every single claim, statement, parameter name, endpoint path, HTTP method, return value, code example, or architectural behavior MUST be immediately followed by its source chunk ID in the exact format: [^chunk_id]
   - Example:
     "In v2.0, authentication requires passing a Bearer token in the `Authorization` header[^chunk_abc123]. The older `api_key` query parameter is no longer supported[^chunk_def456]."
   - NEVER fabricate or make up chunk IDs. Use ONLY the exact Chunk IDs given in the context headers.
   - If multiple chunks support a single claim, combine the tags (e.g., [^chunk_1][^chunk_2]).

3. VERSION AWARENESS & COMPARISON:
   - Always explicitly identify which API version a feature, endpoint, or behavior belongs to.
   - For version comparisons (e.g. v1 vs v2) or migrations, clearly separate the behavior of each version and tag each version's details with its specific chunk ID.

4. DEPRECATION ADHERENCE:
   - If a chunk carries `[DEPRECATED]` or `deprecated: true` metadata, you MUST explicitly warn the developer:
     "> ⚠️ **Deprecated in {version}**: <feature/endpoint> is deprecated and should not be used in new integrations.[^chunk_id]"
   - Never recommend a deprecated endpoint or parameter as the correct approach for the target version.
   - If a replacement exists in the context, always surface it and cite its chunk.

5. VERSION-LOCKED BOUNDARIES:
   - NEVER mix behaviors or parameters across versions unless explicitly asked for a comparison.
   - If the question targets version X, only cite chunks tagged with version X unless cross-version context is explicitly provided.
   - When context chunks span multiple versions, present each version's behavior in a clearly labelled sub-section.

6. CLARITY & FORMAT:
   - Use clean, developer-friendly Markdown with code snippets where helpful.
   - Be direct, concise, and technically accurate.
"""


# ---------------------------------------------------------------------------
# DEPRECATION NOTICE PROMPT — injected when deprecated chunks are detected
# ---------------------------------------------------------------------------

DEPRECATION_NOTICE_PROMPT = """
⚠️  DEPRECATION CONTEXT NOTICE ⚠️
The following context chunks are marked as DEPRECATED for the requested version.
You MUST prominently surface deprecation warnings in your response for any of these chunks
and recommend the successor feature or endpoint if available in the context.
Deprecated Chunk IDs: {deprecated_chunk_ids}
"""


# ---------------------------------------------------------------------------
# COMPARISON PROMPT ADDENDUM — injected for multi-version queries
# ---------------------------------------------------------------------------

COMPARISON_PROMPT_ADDENDUM = """
📋  VERSION COMPARISON MODE
This query requires a side-by-side comparison across multiple API versions.
Structure your response with clear version sub-headings (e.g. ## v1.0 vs ## v2.0).
Every claim under each version heading MUST cite a chunk from that exact version.
"""


# ---------------------------------------------------------------------------
# Context formatters
# ---------------------------------------------------------------------------

def _get_meta(chunk: Dict[str, Any], key: str, fallback: Any = None) -> Any:
    """Helper: checks top-level key first, then nested metadata dict."""
    val = chunk.get(key)
    if val is None and isinstance(chunk.get("metadata"), dict):
        val = chunk["metadata"].get(key)
    return val if val is not None else fallback


def detect_deprecated_chunks(chunks: List[Dict[str, Any]]) -> List[str]:
    """
    Scans context chunks for deprecation markers and returns the list of
    deprecated chunk IDs so the prompt can surface a DEPRECATION_NOTICE.
    A chunk is considered deprecated when:
      - `is_deprecated` metadata field is truthy, OR
      - its content contains the literal string '[DEPRECATED]'
    """
    deprecated_ids: List[str] = []
    for c in chunks:
        chunk_id = c.get("chunk_id") or c.get("id") or ""
        is_dep = _get_meta(c, "is_deprecated", False)
        content = c.get("content") or c.get("text") or ""
        if is_dep or "[DEPRECATED]" in content.upper():
            deprecated_ids.append(str(chunk_id))
    return deprecated_ids


def format_chunks_for_context(chunks: List[Dict[str, Any]]) -> str:
    """
    Formats retrieved vector/database chunks into standardized blocks for
    context injection into the prompt. Each block clearly demarcates the
    chunk_id, document title, version, section, line numbers, deprecation
    status, and content.
    """
    if not chunks:
        return "No documentation context provided."

    formatted_blocks = []
    for idx, c in enumerate(chunks, 1):
        chunk_id  = c.get("chunk_id") or c.get("id") or f"chunk_{idx}"
        doc_title = (
            _get_meta(c, "document_title")
            or _get_meta(c, "file_name")
            or "API Documentation"
        )
        version = (
            _get_meta(c, "version")
            or _get_meta(c, "version_tag")
            or "latest"
        )
        section = _get_meta(c, "section_header") or "General"
        start_line = _get_meta(c, "start_line")
        end_line   = _get_meta(c, "end_line")
        lines_str  = (
            f" (Lines: {start_line}-{end_line})"
            if start_line is not None and end_line is not None
            else ""
        )

        is_deprecated = bool(_get_meta(c, "is_deprecated", False))
        dep_label = " [⚠️ DEPRECATED]" if is_deprecated else ""
        content = (c.get("content") or c.get("text") or "").strip()

        block = (
            f"--- CHUNK {idx} ---\n"
            f"Chunk ID: {chunk_id}\n"
            f"Document: {doc_title}\n"
            f"Version: {version}{dep_label}\n"
            f"Section: {section}{lines_str}\n"
            f"Content:\n{content}\n"
            f"-------------------"
        )
        formatted_blocks.append(block)

    return "\n\n".join(formatted_blocks)


def build_rag_user_prompt(
    query: str,
    chunks: List[Dict[str, Any]],
    selected_version: Optional[str] = None,
    is_comparison: bool = False,
) -> str:
    """
    Constructs the full user message payload containing:
      - Formatted context chunks (with deprecation labels)
      - Deprecation notice addendum (if any deprecated chunks found)
      - Comparison mode addendum (if is_comparison=True)
      - The developer question with strict grounding reminder
    """
    formatted_context = format_chunks_for_context(chunks)
    version_hint = f"Target Version: {selected_version}\n" if selected_version else ""

    # Deprecation notice injection
    deprecated_ids = detect_deprecated_chunks(chunks)
    dep_notice = ""
    if deprecated_ids:
        dep_notice = DEPRECATION_NOTICE_PROMPT.format(
            deprecated_chunk_ids=", ".join(deprecated_ids)
        ) + "\n"

    # Comparison mode injection
    comparison_hint = COMPARISON_PROMPT_ADDENDUM + "\n" if is_comparison else ""

    return (
        f"DOCUMENTATION CONTEXT CHUNKS:\n\n"
        f"{formatted_context}\n\n"
        f"==================================================\n"
        f"{dep_notice}"
        f"{comparison_hint}"
        f"USER QUESTION: {query}\n"
        f"{version_hint}"
        f"REMINDER: Answer strictly using ONLY the context chunks above. "
        f"Tag EVERY factual claim, code snippet, and parameter with [^chunk_id] "
        f"using the exact chunk IDs from the context. "
        f"Flag any deprecated chunk with a visible ⚠️ Deprecation Warning."
    )


# ---------------------------------------------------------------------------
# Citation tag utilities
# ---------------------------------------------------------------------------

CITATION_REGEX = re.compile(r'\[\^([a-zA-Z0-9_\-]+)\]')


def extract_citation_tags(text: str) -> List[str]:
    """
    Extracts all unique citation chunk IDs from a generated markdown response
    in the order they first appear.

    Example:
        'Auth uses Bearer tokens[^chunk_1][^chunk_2]' -> ['chunk_1', 'chunk_2']
    """
    matches = CITATION_REGEX.findall(text)
    seen: set = set()
    ordered_unique: List[str] = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            ordered_unique.append(m)
    return ordered_unique


def strip_citation_tags(text: str) -> str:
    """Removes all [^chunk_id] citation markers from text."""
    return CITATION_REGEX.sub("", text).strip()


def validate_citation_ids(
    answer: str,
    valid_chunk_ids: List[str],
) -> Dict[str, Any]:
    """
    Validates that every citation tag in the answer refers to a real chunk ID
    from the provided context. Returns a grounding validation report.

    Returns:
        {
            "cited_ids":      list of chunk IDs referenced in the answer,
            "valid_ids":      intersection with provided valid_chunk_ids,
            "fabricated_ids": cited IDs not in valid_chunk_ids (hallucinations),
            "is_grounded":    True when fabricated_ids is empty,
        }
    """
    cited = set(extract_citation_tags(answer))
    valid = set(valid_chunk_ids)
    fabricated = list(cited - valid)
    return {
        "cited_ids":      sorted(cited),
        "valid_ids":      sorted(cited & valid),
        "fabricated_ids": fabricated,
        "is_grounded":    len(fabricated) == 0,
    }

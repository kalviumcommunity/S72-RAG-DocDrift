import re
from typing import List, Dict, Any, Optional

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

4. CLARITY & FORMAT:
   - Use clean, developer-friendly Markdown with code snippets where helpful.
   - Be direct, concise, and technically accurate.
"""


def format_chunks_for_context(chunks: List[Dict[str, Any]]) -> str:
    """
    Formats retrieved vector/database chunks into standardized blocks for context injection into the prompt.
    Each block clearly demarcates the chunk_id, document title, version, section, line numbers, and content.
    """
    if not chunks:
        return "No documentation context provided."

    formatted_blocks = []
    for idx, c in enumerate(chunks, 1):
        # Support dict format from vector_store or DB models
        chunk_id = c.get("chunk_id") or c.get("id") or f"chunk_{idx}"
        doc_title = (
            c.get("document_title") or 
            c.get("file_name") or 
            (c.get("metadata", {}).get("file_name") if isinstance(c.get("metadata"), dict) else "") or
            "API Documentation"
        )
        version = (
            c.get("version") or 
            c.get("version_tag") or 
            (c.get("metadata", {}).get("version") if isinstance(c.get("metadata"), dict) else "latest")
        )
        section = (
            c.get("section_header") or 
            (c.get("metadata", {}).get("section_header") if isinstance(c.get("metadata"), dict) else "") or 
            "General"
        )
        start_line = c.get("start_line") or (c.get("metadata", {}).get("start_line") if isinstance(c.get("metadata"), dict) else None)
        end_line = c.get("end_line") or (c.get("metadata", {}).get("end_line") if isinstance(c.get("metadata"), dict) else None)
        lines_str = f" (Lines: {start_line}-{end_line})" if start_line is not None and end_line is not None else ""

        content = c.get("content") or c.get("text") or ""

        block = (
            f"--- CHUNK {idx} ---\n"
            f"Chunk ID: {chunk_id}\n"
            f"Document: {doc_title}\n"
            f"Version: {version}\n"
            f"Section: {section}{lines_str}\n"
            f"Content:\n{content.strip()}\n"
            f"-------------------"
        )
        formatted_blocks.append(block)

    return "\n\n".join(formatted_blocks)


def build_rag_user_prompt(
    query: str,
    chunks: List[Dict[str, Any]],
    selected_version: Optional[str] = None,
    is_comparison: bool = False
) -> str:
    """
    Constructs the user message payload containing query instructions and formatted context.
    """
    formatted_context = format_chunks_for_context(chunks)
    version_hint = f"Target Version: {selected_version}\n" if selected_version else ""
    comparison_hint = "Note: This is a version comparison query. Please clearly contrast the versions.\n" if is_comparison else ""

    return (
        f"DOCUMENTATION CONTEXT CHUNKS:\n\n"
        f"{formatted_context}\n\n"
        f"==================================================\n"
        f"USER QUESTION: {query}\n"
        f"{version_hint}"
        f"{comparison_hint}"
        f"REMINDER: Answer strictly using ONLY the context chunks above. Tag EVERY factual claim, code snippet, and parameter with [^chunk_id] using the exact chunk IDs from the context."
    )


CITATION_REGEX = re.compile(r'\[\^([a-zA-Z0-9_\-]+)\]')


def extract_citation_tags(text: str) -> List[str]:
    """
    Extracts all unique citation chunk IDs from a generated markdown response.
    Example: 'Auth uses Bearer tokens[^chunk_1][^chunk_2]' -> ['chunk_1', 'chunk_2']
    """
    matches = CITATION_REGEX.findall(text)
    seen = set()
    ordered_unique = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            ordered_unique.append(m)
    return ordered_unique

"""
Version Diff & Drift Analysis
================================
POST /diff — compares two API documentation versions on a topic and returns
             structured breaking-change / deprecation / migration analysis.
"""

import json
import importlib
import warnings
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.services.vector_store import vector_store
from app.services.query_intent import query_intent_analyzer
from app.core.config import settings as app_settings
from app.core.logging import logger

router = APIRouter(prefix="/diff", tags=["Version Diff"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DiffRequest(BaseModel):
    version_a: str = Field(..., description="Older/source API version (e.g. 'v1.0')")
    version_b: str = Field(..., description="Newer/target API version (e.g. 'v2.0')")
    topic: str = Field(..., min_length=1, description="Topic, endpoint, or feature to compare")
    top_k: int = Field(default=5, ge=1, le=20, description="Chunks to retrieve per version")
    score_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    use_llm: bool = Field(default=True, description="Use LLM for structured drift analysis")


class BreakingChange(BaseModel):
    title: str
    description: str
    version_a_behavior: Optional[str] = None
    version_b_behavior: Optional[str] = None
    chunk_ids: List[str] = Field(default_factory=list)


class Deprecation(BaseModel):
    item: str
    reason: Optional[str] = None
    replacement: Optional[str] = None
    chunk_ids: List[str] = Field(default_factory=list)


class MigrationExample(BaseModel):
    description: str
    before_code: Optional[str] = None
    after_code: Optional[str] = None


class DiffResponse(BaseModel):
    version_a: str
    version_b: str
    topic: str
    breaking_changes: List[BreakingChange] = Field(default_factory=list)
    deprecations: List[Deprecation] = Field(default_factory=list)
    new_features: List[str] = Field(default_factory=list)
    migration_tips: List[MigrationExample] = Field(default_factory=list)
    summary: str = ""
    version_a_chunk_count: int = 0
    version_b_chunk_count: int = 0
    analysis_mode: str = "llm"


# ---------------------------------------------------------------------------
# Version Drift System Prompt
# ---------------------------------------------------------------------------

VERSION_DRIFT_SYSTEM_PROMPT = """You are DocDrift Version Analyst, an expert at comparing API documentation between versions.
Given documentation context chunks from two API versions, produce a structured JSON analysis of the differences.

### INSTRUCTIONS:
1. Identify BREAKING CHANGES — behaviors that changed in a way that breaks existing integrations
2. Identify DEPRECATIONS — features/parameters marked as deprecated in version_b
3. Identify NEW FEATURES — capabilities added in version_b not in version_a
4. Provide MIGRATION TIPS — concrete code-level before/after examples where possible
5. Cite EVERY finding with the exact [^chunk_id] from the provided context

### OUTPUT FORMAT:
Return ONLY valid JSON matching this exact schema:
{
  "breaking_changes": [
    {
      "title": "Short title of the breaking change",
      "description": "Detailed explanation",
      "version_a_behavior": "How it worked in version A",
      "version_b_behavior": "How it works in version B",
      "chunk_ids": ["chunk_abc", "chunk_def"]
    }
  ],
  "deprecations": [
    {
      "item": "Deprecated feature/parameter/endpoint",
      "reason": "Why it was deprecated",
      "replacement": "What to use instead",
      "chunk_ids": ["chunk_xyz"]
    }
  ],
  "new_features": ["Feature 1 description", "Feature 2 description"],
  "migration_tips": [
    {
      "description": "What to change",
      "before_code": "// v1.0 code",
      "after_code": "// v2.0 code"
    }
  ],
  "summary": "One-paragraph executive summary of the version differences"
}

Do NOT include explanatory text outside the JSON object.
"""


def _build_drift_user_prompt(
    version_a: str,
    version_b: str,
    topic: str,
    chunks_a: List[Dict[str, Any]],
    chunks_b: List[Dict[str, Any]],
) -> str:
    def _fmt(chunks: List[Dict], version: str) -> str:
        if not chunks:
            return f"  No documentation found for '{topic}' in {version}."
        blocks = []
        for i, c in enumerate(chunks, 1):
            cid = c.get("chunk_id") or c.get("id") or f"chunk_{i}"
            sec = c.get("section_header") or "General"
            content = (c.get("content") or c.get("text") or "").strip()
            blocks.append(f"[Chunk ID: {cid}] [{sec}]\n{content}")
        return "\n\n".join(blocks)

    return (
        f"TOPIC: {topic}\n\n"
        f"=== VERSION A: {version_a} ===\n{_fmt(chunks_a, version_a)}\n\n"
        f"=== VERSION B: {version_b} ===\n{_fmt(chunks_b, version_b)}\n\n"
        f"Analyze the differences between {version_a} and {version_b} for the topic '{topic}'.\n"
        f"Return structured JSON as specified in the system prompt."
    )


def _deterministic_diff(
    version_a: str,
    version_b: str,
    topic: str,
    chunks_a: List[Dict],
    chunks_b: List[Dict],
) -> DiffResponse:
    """
    Offline fallback diff: compares chunk content at the token level and
    flags chunks that appear only in one version.
    """
    ids_a = {c.get("chunk_id") or c.get("id") for c in chunks_a}
    ids_b = {c.get("chunk_id") or c.get("id") for c in chunks_b}
    only_in_a = [c for c in chunks_a if (c.get("chunk_id") or c.get("id")) not in ids_b]
    only_in_b = [c for c in chunks_b if (c.get("chunk_id") or c.get("id")) not in ids_a]

    breaking = []
    if only_in_a:
        breaking.append(BreakingChange(
            title=f"Content removed in {version_b}",
            description=f"{len(only_in_a)} chunk(s) present in {version_a} have no counterpart in {version_b}.",
            version_a_behavior="Documented behavior exists",
            version_b_behavior="No corresponding documentation found",
            chunk_ids=[c.get("chunk_id") or "" for c in only_in_a],
        ))

    new_feats = [
        f"[{c.get('section_header', 'New')}] {(c.get('content') or '')[:120]}..."
        for c in only_in_b
    ]

    return DiffResponse(
        version_a=version_a,
        version_b=version_b,
        topic=topic,
        breaking_changes=breaking,
        new_features=new_feats,
        summary=(
            f"Offline analysis: {version_a} has {len(chunks_a)} chunks, "
            f"{version_b} has {len(chunks_b)} chunks for topic '{topic}'. "
            f"{len(only_in_a)} chunk(s) removed, {len(only_in_b)} added."
        ),
        version_a_chunk_count=len(chunks_a),
        version_b_chunk_count=len(chunks_b),
        analysis_mode="deterministic",
    )


def _llm_diff(
    version_a: str,
    version_b: str,
    topic: str,
    chunks_a: List[Dict],
    chunks_b: List[Dict],
) -> DiffResponse:
    """Invokes an LLM to produce structured drift analysis JSON."""
    user_prompt = _build_drift_user_prompt(version_a, version_b, topic, chunks_a, chunks_b)
    raw_text = None

    # Try Ollama
    if app_settings.OLLAMA_BASE_URL:
        try:
            import urllib.request
            url = f"{app_settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
            payload = json.dumps({
                "model": app_settings.OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": VERSION_DRIFT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1}
            }).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if app_settings.OLLAMA_API_KEY:
                headers["Authorization"] = f"Bearer {app_settings.OLLAMA_API_KEY}"

            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_text = data.get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.debug(f"Drift LLM (Ollama) skipped/failed: {e}")

    # Try modern Google GenAI
    if not raw_text:
        try:
            modern_genai = importlib.import_module("google.genai")
            genai_types = importlib.import_module("google.genai.types")
            if app_settings.GEMINI_API_KEY:
                client = modern_genai.Client(api_key=app_settings.GEMINI_API_KEY)
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=user_prompt,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=VERSION_DRIFT_SYSTEM_PROMPT,
                        temperature=0.1,
                    ),
                )
                raw_text = response.text.strip() if response and response.text else None
        except Exception as e:
            logger.warning(f"Drift LLM (modern GenAI) failed: {e}")


    # Try legacy Gemini
    if not raw_text:
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning)
                genai = importlib.import_module("google.generativeai")
                if app_settings.GEMINI_API_KEY:
                    genai.configure(api_key=app_settings.GEMINI_API_KEY)
                    model = genai.GenerativeModel(
                        model_name="gemini-1.5-flash",
                        system_instruction=VERSION_DRIFT_SYSTEM_PROMPT,
                    )
                    resp = model.generate_content(user_prompt)
                    raw_text = resp.text.strip() if resp and resp.text else None
        except Exception as e:
            logger.warning(f"Drift LLM (legacy Gemini) failed: {e}")

    if not raw_text:
        return _deterministic_diff(version_a, version_b, topic, chunks_a, chunks_b)

    # Strip markdown code fences if present
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = "\n".join(raw_text.split("\n")[1:])
    if raw_text.endswith("```"):
        raw_text = "\n".join(raw_text.split("\n")[:-1])

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.error("Failed to parse LLM drift JSON; falling back to deterministic.")
        return _deterministic_diff(version_a, version_b, topic, chunks_a, chunks_b)

    return DiffResponse(
        version_a=version_a,
        version_b=version_b,
        topic=topic,
        breaking_changes=[BreakingChange(**bc) for bc in parsed.get("breaking_changes", [])],
        deprecations=[Deprecation(**d) for d in parsed.get("deprecations", [])],
        new_features=parsed.get("new_features", []),
        migration_tips=[MigrationExample(**m) for m in parsed.get("migration_tips", [])],
        summary=parsed.get("summary", ""),
        version_a_chunk_count=len(chunks_a),
        version_b_chunk_count=len(chunks_b),
        analysis_mode="llm",
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=DiffResponse,
    summary="Compare two API versions on a topic and return structured diff",
    description=(
        "Queries documentation chunks from both `version_a` and `version_b` for the given "
        "`topic`, then uses an LLM (or deterministic fallback) to produce a structured JSON "
        "analysis with breaking changes, deprecations, new features, and migration examples."
    ),
)
async def diff_versions(request: DiffRequest) -> DiffResponse:
    """
    POST /api/v1/diff

    ```json
    {
      "version_a": "v1.0",
      "version_b": "v2.0",
      "topic": "OAuth2 authentication",
      "top_k": 5
    }
    ```
    """
    if request.version_a == request.version_b:
        raise HTTPException(status_code=400, detail="version_a and version_b must be different")
    if not request.topic.strip():
        raise HTTPException(status_code=400, detail="topic cannot be empty")

    # Retrieve chunks for both versions in parallel
    try:
        chunks_a = await run_in_threadpool(
            vector_store.query,
            query_text=request.topic,
            version_tag=request.version_a,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
        )
    except Exception as e:
        logger.warning(f"Vector query failed for version_a={request.version_a}: {e}")
        chunks_a = []

    try:
        chunks_b = await run_in_threadpool(
            vector_store.query,
            query_text=request.topic,
            version_tag=request.version_b,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
        )
    except Exception as e:
        logger.warning(f"Vector query failed for version_b={request.version_b}: {e}")
        chunks_b = []

    if request.use_llm:
        result = await run_in_threadpool(
            _llm_diff, request.version_a, request.version_b, request.topic, chunks_a, chunks_b
        )
    else:
        result = await run_in_threadpool(
            _deterministic_diff, request.version_a, request.version_b, request.topic, chunks_a, chunks_b
        )

    return result

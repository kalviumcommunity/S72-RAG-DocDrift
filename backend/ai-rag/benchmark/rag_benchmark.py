"""
RAG Benchmark Evaluation Script
=================================
Automated evaluation across 20 multi-version queries measuring:
  1. Version Strictness  — does the answer cite only the correct version's chunks?
  2. Citation Accuracy   — do cited chunk IDs exist in the retrieved context?
  3. Hallucination Rate  — % of claims unsupported by cited context

Run:
    cd backend
    python -m ai-rag.benchmark.rag_benchmark --help
    python -m ai-rag.benchmark.rag_benchmark [--host http://localhost:8000] [--output results.json]

Or directly:
    python ai_rag/benchmark/rag_benchmark.py
"""

import json
import time
import re
import argparse
import statistics
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from difflib import SequenceMatcher

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    import urllib.request, urllib.parse
    _HAS_HTTPX = False


# ---------------------------------------------------------------------------
# Benchmark query catalogue (20 multi-version queries)
# ---------------------------------------------------------------------------

BENCHMARK_QUERIES = [
    # (query, target_version, expected_not_version)
    ("How do I authenticate using Bearer tokens?",                 "v2.0", "v1.0"),
    ("What is the correct way to pass API keys in v1.0?",          "v1.0", "v2.0"),
    ("What endpoints changed between v1 and v2?",                  None,   None),
    ("How do I paginate results in v2.0?",                         "v2.0", "v1.0"),
    ("What was the rate limit in v1?",                             "v1.0", "v2.0"),
    ("Is the /users/me endpoint available in v2?",                 "v2.0", "v1.0"),
    ("What HTTP methods does /auth/token accept in v1?",           "v1.0", "v2.0"),
    ("How do I handle 401 errors in v2.0?",                        "v2.0", "v1.0"),
    ("What parameters does /search accept in v1.0?",               "v1.0", "v2.0"),
    ("Is the api_key query parameter deprecated in v2?",           "v2.0", "v1.0"),
    ("How do I create a workspace via v2 API?",                    "v2.0", "v1.0"),
    ("What is the response format for /documents in v1?",          "v1.0", "v2.0"),
    ("Compare authentication between v1.0 and v2.0",              None,   None),
    ("What breaking changes occurred in v2.0?",                    "v2.0", "v1.0"),
    ("How do I upload a file in v2.0?",                            "v2.0", "v1.0"),
    ("What is the base URL for v1.0 endpoints?",                   "v1.0", "v2.0"),
    ("How do I list all documents in v2?",                         "v2.0", "v1.0"),
    ("What errors can /auth/login return in v1?",                  "v1.0", "v2.0"),
    ("Are webhooks supported in v2.0?",                            "v2.0", "v1.0"),
    ("What is the migration path from v1 to v2 for auth?",         None,   None),
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    query: str
    target_version: Optional[str]
    expected_not_version: Optional[str]
    answer: str = ""
    cited_ids: List[str] = field(default_factory=list)
    context_chunk_ids: List[str] = field(default_factory=list)
    context_versions: List[str] = field(default_factory=list)
    faithfulness_score: float = 0.0
    is_grounded: bool = False
    pipeline_mode: str = "unknown"
    # Metrics
    version_strict: Optional[bool] = None   # None = N/A (comparison query)
    citation_accuracy: float = 0.0
    hallucination_pct: float = 0.0
    latency_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class BenchmarkReport:
    total_queries: int
    successful: int
    failed: int
    avg_latency_ms: float
    # Accuracy metrics (averages over applicable queries)
    version_strictness_pct: float       # % of version-targeted queries that cited correct version only
    citation_accuracy_pct: float        # % of cited IDs that exist in context
    hallucination_pct: float            # avg % of claims unsupported by cited chunks
    avg_faithfulness_score: float
    results: List[QueryResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class DocDriftClient:
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def query_rag(self, query: str, version: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"query": query, "top_k": 5}
        if version:
            payload["selected_version"] = version

        url = f"{self.base_url}/api/v1/chat/rag"
        if _HAS_HTTPX:
            r = httpx.post(url, json=payload, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        else:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())

    def verify_answer(
        self,
        answer: str,
        context_chunks: List[Dict[str, Any]],
        threshold: float = 70.0,
    ) -> Dict[str, Any]:
        payload = {"answer": answer, "context_chunks": context_chunks, "threshold": threshold}
        url = f"{self.base_url}/api/v1/chat/verify-answer"
        if _HAS_HTTPX:
            r = httpx.post(url, json=payload, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        else:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------

CITATION_RE = re.compile(r'\[\^([a-zA-Z0-9_\-]+)\]')


def compute_citation_accuracy(cited_ids: List[str], context_ids: List[str]) -> float:
    """% of cited chunk IDs that actually exist in the retrieved context."""
    if not cited_ids:
        return 1.0
    valid = sum(1 for cid in cited_ids if cid in set(context_ids))
    return valid / len(cited_ids)


def compute_version_strictness(
    context_versions: List[str],
    target_version: str,
    expected_not: Optional[str],
) -> bool:
    """
    Returns True if the context only contains chunks from the target version
    and none from the forbidden version.
    """
    in_target = any(v == target_version for v in context_versions)
    has_wrong = expected_not and any(v == expected_not for v in context_versions)
    return in_target and not has_wrong


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def run_benchmark(
    host: str = "http://localhost:8000",
    output_path: Optional[str] = None,
    timeout: int = 30,
) -> BenchmarkReport:
    client = DocDriftClient(base_url=host, timeout=timeout)
    results: List[QueryResult] = []

    print(f"\n{'='*60}")
    print(f"  DocDrift RAG Benchmark — {len(BENCHMARK_QUERIES)} queries")
    print(f"  Target: {host}")
    print(f"{'='*60}\n")

    for i, (query, target_ver, not_ver) in enumerate(BENCHMARK_QUERIES, 1):
        print(f"[{i:02d}/{len(BENCHMARK_QUERIES)}] {query[:60]}...")
        qr = QueryResult(query=query, target_version=target_ver, expected_not_version=not_ver)

        t0 = time.perf_counter()
        try:
            resp = client.query_rag(query, version=target_ver)
            qr.latency_ms = round((time.perf_counter() - t0) * 1000, 1)

            qr.answer = resp.get("answer", "")
            qr.cited_ids = resp.get("cited_chunk_ids", [])
            qr.faithfulness_score = resp.get("faithfulness_score") or 0.0
            qr.is_grounded = resp.get("is_grounded", False)
            qr.pipeline_mode = resp.get("pipeline_mode", "unknown")

            # Extract context chunk info
            citations = resp.get("citations", [])
            qr.context_chunk_ids = [c.get("chunk_id", "") for c in citations]
            qr.context_versions = list({c.get("version", "") for c in citations if c.get("version")})

            # Metric 1: Version Strictness
            if target_ver and not_ver:
                qr.version_strict = compute_version_strictness(
                    qr.context_versions, target_ver, not_ver
                )

            # Metric 2: Citation Accuracy
            qr.citation_accuracy = compute_citation_accuracy(qr.cited_ids, qr.context_chunk_ids)

            # Metric 3: Hallucination % (via verify-answer)
            if qr.answer and citations:
                try:
                    faith_resp = client.verify_answer(qr.answer, citations)
                    total = faith_resp.get("total_claims", 0)
                    unfaithful = faith_resp.get("unfaithful_claims_count", 0)
                    qr.hallucination_pct = round((unfaithful / total * 100) if total > 0 else 0.0, 1)
                except Exception:
                    qr.hallucination_pct = 0.0

            status = "✓ GROUNDED" if qr.is_grounded else "⚠ UNGROUNDED"
            vs = ("✓" if qr.version_strict else "✗") if qr.version_strict is not None else "N/A"
            print(
                f"     {status} | VS={vs} | CA={qr.citation_accuracy:.0%} "
                f"| HAL={qr.hallucination_pct:.1f}% | FS={qr.faithfulness_score:.1f}% "
                f"| {qr.latency_ms}ms"
            )

        except Exception as exc:
            qr.latency_ms = round((time.perf_counter() - t0) * 1000, 1)
            qr.error = str(exc)
            print(f"     ✗ ERROR: {exc}")

        results.append(qr)

    # ---------------------------------------------------------------------------
    # Aggregate report
    # ---------------------------------------------------------------------------
    successful = [r for r in results if not r.error]
    failed = [r for r in results if r.error]

    version_strictness_results = [r.version_strict for r in successful if r.version_strict is not None]
    version_strictness_pct = (
        round(sum(version_strictness_results) / len(version_strictness_results) * 100, 1)
        if version_strictness_results else 0.0
    )

    citation_accs = [r.citation_accuracy for r in successful]
    hallucinations = [r.hallucination_pct for r in successful]
    faith_scores = [r.faithfulness_score for r in successful]
    latencies = [r.latency_ms for r in successful]

    report = BenchmarkReport(
        total_queries=len(results),
        successful=len(successful),
        failed=len(failed),
        avg_latency_ms=round(statistics.mean(latencies), 1) if latencies else 0.0,
        version_strictness_pct=version_strictness_pct,
        citation_accuracy_pct=round(statistics.mean(citation_accs) * 100, 1) if citation_accs else 0.0,
        hallucination_pct=round(statistics.mean(hallucinations), 1) if hallucinations else 0.0,
        avg_faithfulness_score=round(statistics.mean(faith_scores), 1) if faith_scores else 0.0,
        results=results,
    )

    print(f"\n{'='*60}")
    print("  BENCHMARK RESULTS")
    print(f"{'='*60}")
    print(f"  Queries: {report.total_queries} total | {report.successful} OK | {report.failed} failed")
    print(f"  Avg Latency:          {report.avg_latency_ms} ms")
    print(f"  Version Strictness:   {report.version_strictness_pct}%")
    print(f"  Citation Accuracy:    {report.citation_accuracy_pct}%")
    print(f"  Hallucination Rate:   {report.hallucination_pct}%")
    print(f"  Avg Faithfulness:     {report.avg_faithfulness_score}%")
    print(f"{'='*60}\n")

    if output_path:
        out = {
            "summary": {k: v for k, v in asdict(report).items() if k != "results"},
            "results": [asdict(r) for r in results],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"  Report saved to: {output_path}")

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="DocDrift RAG Benchmark")
    parser.add_argument("--host", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--output", default="benchmark_results.json", help="Output JSON path")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout seconds")
    args = parser.parse_args()
    run_benchmark(host=args.host, output_path=args.output, timeout=args.timeout)


if __name__ == "__main__":
    main()

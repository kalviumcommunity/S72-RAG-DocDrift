import os
import json
import pytest
from app.services.query_intent import QueryIntentAnalyzer, query_intent_analyzer
from app.schemas.intent import QueryIntentEnum, QueryIntentResponse


def test_version_normalization():
    analyzer = QueryIntentAnalyzer()
    assert analyzer.normalize_version("1") == "v1.0"
    assert analyzer.normalize_version("v2") == "v2.0"
    assert analyzer.normalize_version("v1.0") == "v1.0"
    assert analyzer.normalize_version("2.1") == "v2.1"
    assert analyzer.normalize_version("latest") == "latest"


def test_extract_versions():
    analyzer = QueryIntentAnalyzer()
    assert analyzer.extract_versions("How to authenticate in v2?") == ["v2.0"]
    assert analyzer.extract_versions("Difference between v1 and v2?") == ["v1.0", "v2.0"]
    assert analyzer.extract_versions("Comparing version 1.0 with version 2.0") == ["v1.0", "v2.0"]
    assert analyzer.extract_versions("How does the API work?") == []


def test_extract_endpoints():
    analyzer = QueryIntentAnalyzer()
    q = "What endpoint do I use in v2 instead of /charges? Maybe /payments?"
    endpoints = analyzer.extract_endpoints(q)
    assert "/charges" in endpoints
    assert "/payments" in endpoints

    q_delete = "Does DELETE /customers/:id delete permanently?"
    endpoints_delete = analyzer.extract_endpoints(q_delete)
    assert any("/customers" in ep for ep in endpoints_delete)


def test_single_version_intent():
    analyzer = QueryIntentAnalyzer()
    
    # Query specifying single version
    res = analyzer.analyze("How do I authenticate with the API in v2?", mode="regex")
    assert res.is_comparison is False
    assert res.target_versions == ["v2.0"]
    assert res.intent == QueryIntentEnum.FEATURE_USAGE.value

    # Another single version query
    res_v1 = analyzer.analyze("How do I paginate results in v1?", mode="regex")
    assert res_v1.is_comparison is False
    assert res_v1.target_versions == ["v1.0"]


def test_comparison_version_intent():
    analyzer = QueryIntentAnalyzer()

    # Query asking for changes between v1 and v2
    res1 = analyzer.analyze("How did authentication change from v1 to v2?", mode="regex")
    assert res1.is_comparison is True
    assert set(res1.target_versions) == {"v1.0", "v2.0"}
    assert res1.intent == QueryIntentEnum.COMPARISON.value

    # Query with 'vs'
    res2 = analyzer.analyze("What is the default limit for listing charges/payments in v1 vs v2?", mode="regex")
    assert res2.is_comparison is True
    assert set(res2.target_versions) == {"v1.0", "v2.0"}
    assert res2.intent == QueryIntentEnum.COMPARISON.value


def test_migration_intent():
    analyzer = QueryIntentAnalyzer()

    res = analyzer.analyze("What endpoint do I use in v2 instead of /charges?", mode="regex")
    assert res.intent == QueryIntentEnum.MIGRATION.value
    assert "/charges" in res.detected_endpoints
    # Cross-version migration should target both old and new versions
    assert set(res.target_versions) == {"v1.0", "v2.0"}


def test_troubleshooting_intent():
    analyzer = QueryIntentAnalyzer()

    res = analyzer.analyze("I am getting a 401 Unauthorized when passing api_key in v2. Why?", mode="regex")
    assert res.is_comparison is False
    assert res.target_versions == ["v2.0"]
    assert res.intent == QueryIntentEnum.TROUBLESHOOTING.value


def test_general_intent_with_fallback_selected_version():
    analyzer = QueryIntentAnalyzer()

    # Query without explicit version, but selected_version in session context
    res = analyzer.analyze("How do I create a charge?", selected_version="v1.0", mode="regex")
    assert res.is_comparison is False
    assert res.target_versions == ["v1.0"]

    # Query without any version at all
    res_no_ver = analyzer.analyze("How do I create a charge?", mode="regex")
    assert res_no_ver.is_comparison is False
    assert res_no_ver.target_versions == []
    assert res_no_ver.intent == QueryIntentEnum.GENERAL.value


def test_benchmark_queries_accuracy():
    """
    Evaluates QueryIntentAnalyzer against all queries in ai-rag/benchmark/queries.json.
    Verifies that target_versions and comparison flags match expected benchmark behavior.
    """
    benchmark_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ai-rag", "benchmark", "queries.json"))
    if not os.path.exists(benchmark_file):
        pytest.skip("Benchmark queries.json not found")

    with open(benchmark_file, "r", encoding="utf-8") as f:
        benchmark_queries = json.load(f)

    analyzer = QueryIntentAnalyzer()

    for item in benchmark_queries:
        qid = item["id"]
        query_text = item["query"]
        expected_versions = item["target_versions"]
        expected_intent = item.get("intent")

        result = analyzer.analyze(query_text, mode="regex")

        # 1. Target versions check
        assert set(result.target_versions) == set(expected_versions), (
            f"Query {qid} ('{query_text}') failed: expected {expected_versions}, got {result.target_versions}"
        )

        # 2. Comparison flag check
        expected_is_comparison = len(expected_versions) > 1
        assert result.is_comparison == expected_is_comparison, (
            f"Query {qid} is_comparison mismatch: expected {expected_is_comparison}, got {result.is_comparison}"
        )

        # 3. Intent check
        if expected_intent:
            assert result.intent == expected_intent, (
                f"Query {qid} intent mismatch: expected {expected_intent}, got {result.intent}"
            )


def test_llm_fallback_resilience():
    """
    Ensures analyzer falls back cleanly to regex when no LLM API keys are provided.
    """
    analyzer = QueryIntentAnalyzer(gemini_api_key=None, openai_api_key=None)
    res = analyzer.analyze("Compare authentication in v1 and v2", mode="llm")
    assert res.is_comparison is True
    assert set(res.target_versions) == {"v1.0", "v2.0"}
    assert res.analysis_mode in ["regex", "fallback"]

import pytest
from app.services.faithfulness_evaluator import (
    FaithfulnessEvaluator,
    faithfulness_evaluator,
    compute_faithfulness_score,
)
from app.schemas.faithfulness import (
    ClaimVerificationResult,
    AnswerFaithfulnessReport,
)


def test_faithfulness_exact_or_direct_claim():
    source_chunk = (
        "In v2.0, authentication requires passing a Bearer token in the Authorization header. "
        "The older api_key query parameter is completely deprecated."
    )
    claim = "In v2.0, authentication requires passing a Bearer token in the Authorization header."
    score = compute_faithfulness_score(claim, source_chunk)

    assert score >= 90.0, f"Expected high score >= 90.0, got {score}"
    result = faithfulness_evaluator.verify_claim(claim, source_chunk)
    assert result.is_faithful is True
    assert result.verdict == "SUPPORTED"
    assert len(result.unsupported_entities) == 0


def test_faithfulness_paraphrased_claim():
    source_chunk = (
        "In v2.0, authentication requires passing a Bearer token in the Authorization header. "
        "The older api_key query parameter is completely deprecated."
    )
    claim = "Developers must pass a Bearer token inside the Authorization header when calling v2 APIs."
    score = compute_faithfulness_score(claim, source_chunk)

    assert score >= 70.0, f"Expected paraphrased score >= 70.0, got {score}"
    result = faithfulness_evaluator.verify_claim(claim, source_chunk)
    assert result.is_faithful is True


def test_faithfulness_fabricated_endpoint():
    source_chunk = "Use POST /v2/payments to initiate credit card transactions."
    claim = "You can initiate transactions using POST /v2/crypto-transfer."
    score = compute_faithfulness_score(claim, source_chunk)

    assert score < 50.0, f"Expected low score for fabricated endpoint, got {score}"
    result = faithfulness_evaluator.verify_claim(claim, source_chunk)
    assert result.is_faithful is False
    assert result.verdict == "UNSUPPORTED"
    assert any("crypto-transfer" in e for e in result.unsupported_entities)


def test_faithfulness_fabricated_limit_number():
    source_chunk = "The default page limit for listing payments in v2 is 20 records."
    claim = "The default page limit for listing payments in v2 is 500 records."
    score = compute_faithfulness_score(claim, source_chunk)

    assert score < 60.0, f"Expected lower score for wrong limit, got {score}"
    result = faithfulness_evaluator.verify_claim(claim, source_chunk)
    assert any("500" in e for e in result.unsupported_entities)


def test_faithfulness_empty_source_chunk():
    claim = "Authentication requires Bearer token."
    score = compute_faithfulness_score(claim, "")
    assert score == 0.0

    result = faithfulness_evaluator.verify_claim(claim, {})
    assert result.faithfulness_score == 0.0
    assert result.is_faithful is False


def test_faithfulness_empty_claim():
    source_chunk = "Some documentation text here."
    score = compute_faithfulness_score("", source_chunk)
    assert score == 100.0


def test_faithfulness_chunk_dict_input():
    chunk_dict = {
        "chunk_id": "chk_payments",
        "content": "POST /v2/payments accepts payment_method and amount parameters.",
        "section_header": "Create Payment"
    }
    claim = "POST /v2/payments takes the `payment_method` parameter."
    result = faithfulness_evaluator.verify_claim(claim, chunk_dict, chunk_id="chk_payments")

    assert result.faithfulness_score >= 80.0
    assert result.is_faithful is True
    assert result.chunk_id == "chk_payments"


def test_verify_answer_multi_claims():
    context_chunks = [
        {
            "chunk_id": "c1",
            "content": "In v1.0, pagination uses offset and limit parameters."
        },
        {
            "chunk_id": "c2",
            "content": "In v2.0, pagination uses cursor-based navigation with next_cursor."
        }
    ]

    answer = (
        "In v1.0, pagination uses offset and limit[^c1]. "
        "In v2.0, cursor-based pagination is used with next_cursor[^c2]."
    )

    report = faithfulness_evaluator.verify_answer(answer, context_chunks)
    assert isinstance(report, AnswerFaithfulnessReport)
    assert report.total_claims == 2
    assert report.faithful_claims_count == 2
    assert report.is_faithful is True
    assert report.overall_score >= 80.0


def test_verify_answer_with_hallucinated_citation():
    context_chunks = [
        {
            "chunk_id": "c1",
            "content": "Use Bearer token for auth."
        }
    ]

    answer = (
        "Use Bearer token for auth[^c1]. "
        "Pass secret key in X-Secret header[^non_existent_chunk]."
    )

    report = faithfulness_evaluator.verify_answer(answer, context_chunks)
    assert report.unfaithful_claims_count >= 1
    assert report.is_faithful is False
    # Verify the fake citation was caught
    fake_claims = [c for c in report.claim_verifications if c.chunk_id == "non_existent_chunk"]
    assert len(fake_claims) == 1
    assert fake_claims[0].is_faithful is False
    assert fake_claims[0].faithfulness_score == 0.0


def test_api_verify_claim_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    payload = {
        "claim": "In v2.0, pass Bearer token in the Authorization header.",
        "source_chunk": "In v2.0, authentication requires passing a Bearer token in the Authorization header.",
        "chunk_id": "chunk_auth_01"
    }

    resp = client.post("/api/v1/chat/verify-claim", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert "faithfulness_score" in data
    assert data["faithfulness_score"] >= 90.0
    assert data["is_faithful"] is True
    assert data["verdict"] == "SUPPORTED"


def test_api_verify_answer_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    payload = {
        "answer": "In v1, charges limit is 10[^chk_1]. In v2, payments limit is 20[^chk_2].",
        "context_chunks": [
            {"chunk_id": "chk_1", "content": "In v1, charges default limit is 10."},
            {"chunk_id": "chk_2", "content": "In v2, payments default limit is 20."}
        ],
        "threshold": 70.0
    }

    resp = client.post("/api/v1/chat/verify-answer", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert "overall_score" in data
    assert data["overall_score"] >= 80.0
    assert data["is_faithful"] is True
    assert data["total_claims"] == 2

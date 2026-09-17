import re
from typing import List, Dict, Any, Optional, Union, Tuple
from app.core.logging import logger
from app.core.prompts import CITATION_REGEX, extract_citation_tags
from app.services.embedding_service import embedding_service, cosine_similarity
from app.schemas.faithfulness import (
    ClaimVerificationResult,
    AnswerFaithfulnessReport,
)

# Common stopwords to exclude from content-word matching
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "when", "at", "by",
    "for", "with", "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "to", "from", "up", "down", "in", "out", "on", "off",
    "over", "under", "again", "further", "then", "once", "here", "there", "all", "any",
    "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not",
    "only", "own", "same", "so", "than", "too", "very", "can", "will", "just", "should",
    "now", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "this", "that", "these", "those", "it", "its", "must", "inside",
    "calling", "developers", "using", "takes", "take", "accepts", "provides", "used"
}

# Regex to detect technical API entities
ENDPOINT_REGEX = re.compile(r'(/(?:v\d+/)?(?:[a-zA-Z0-9_\-]+)(?:/[a-zA-Z0-9_\-]+)*)')
METHOD_REGEX = re.compile(r'\b(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\b')
CODE_TOKEN_REGEX = re.compile(r'`([a-zA-Z0-9_\-./]+)`')
NUMBER_REGEX = re.compile(r'\b(\d{1,4})\b')


def extract_chunk_text(source_chunk: Union[str, Dict[str, Any]]) -> str:
    """Extracts raw string content from either a raw string or chunk dictionary."""
    if isinstance(source_chunk, str):
        return source_chunk
    if isinstance(source_chunk, dict):
        return (
            source_chunk.get("content") or 
            source_chunk.get("text") or 
            source_chunk.get("excerpt") or 
            ""
        )
    return str(source_chunk)


def extract_technical_entities(text: str) -> Dict[str, List[str]]:
    """
    Extracts key technical entities (endpoints, HTTP methods, backticked code tokens, numbers)
    which must be grounded in documentation.
    """
    endpoints = [ep for ep in ENDPOINT_REGEX.findall(text) if len(ep) > 1 and not ep.endswith("/")]
    methods = METHOD_REGEX.findall(text)
    code_tokens = CODE_TOKEN_REGEX.findall(text)
    numbers = NUMBER_REGEX.findall(text)

    return {
        "endpoints": list(set(endpoints)),
        "methods": list(set(methods)),
        "code_tokens": list(set(code_tokens)),
        "numbers": list(set(numbers)),
    }


def stem_match(w: str, target: str) -> bool:
    """Checks if a claim word matches a source word via identity, substring, or common root."""
    if w == target:
        return True
    if w in target or target in w:
        return True
    min_len = min(len(w), len(target))
    if min_len >= 4 and w[:4] == target[:4]:
        return True
    # Version tags (v1 == v1.0, v2 == v2.0)
    if re.match(r'^v\d+(\.\d+)?$', w) and re.match(r'^v\d+(\.\d+)?$', target):
        return re.findall(r'\d+', w)[0] == re.findall(r'\d+', target)[0]
    return False


def tokenize_content_words(text: str) -> List[str]:
    """Tokenizes text into cleaned alphanumeric content words, filtering out stopwords."""
    words = re.findall(r'[a-zA-Z0-9_\-]+', text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def compute_token_overlap(claim: str, source_text: str) -> float:
    """
    Calculates the proportion of content words and bigrams from the claim
    that are grounded in the source text using root stem matching.
    """
    claim_words = tokenize_content_words(claim)
    if not claim_words:
        return 1.0

    chunk_words = tokenize_content_words(source_text)
    if not chunk_words:
        return 0.0

    matched = sum(1 for w in claim_words if any(stem_match(w, cw) for cw in chunk_words))
    word_overlap = matched / len(claim_words)

    # Bigram phrasing bonus
    if len(claim_words) >= 2:
        source_lower = source_text.lower()
        bigrams = [f"{claim_words[i]} {claim_words[i+1]}" for i in range(len(claim_words) - 1)]
        matched_bigrams = sum(1 for b in bigrams if b in source_lower)
        bigram_overlap = matched_bigrams / len(bigrams)
        return min(1.0, round(0.85 * word_overlap + 0.15 * bigram_overlap, 4))

    return round(word_overlap, 4)


class FaithfulnessEvaluator:
    """
    Evaluator that compares LLM generated claims against cited source chunks
    and computes a grounded faithfulness score between 0.0% and 100.0%.
    """

    def __init__(self, pass_threshold: float = 70.0):
        self.pass_threshold = pass_threshold

    def compute_faithfulness_score(
        self,
        claim: str,
        source_chunk: Union[str, Dict[str, Any]]
    ) -> float:
        """
        Core verification function.
        Compares the claim against the cited source chunk and returns a faithfulness score (0-100%).
        """
        result = self.verify_claim(claim, source_chunk)
        return result.faithfulness_score

    def verify_claim(
        self,
        claim: str,
        source_chunk: Union[str, Dict[str, Any]],
        chunk_id: Optional[str] = None,
        threshold: Optional[float] = None
    ) -> ClaimVerificationResult:
        """
        Comprehensive verification of an individual claim against its source chunk.
        Evaluates technical entity grounding, lexical overlap, and semantic similarity.
        """
        pass_thresh = threshold if threshold is not None else self.pass_threshold
        chunk_text = extract_chunk_text(source_chunk)

        clean_claim = re.sub(CITATION_REGEX, '', claim).strip()
        if not clean_claim:
            return ClaimVerificationResult(
                claim=claim,
                chunk_id=chunk_id,
                faithfulness_score=100.0,
                is_faithful=True,
                verdict="SUPPORTED",
                unsupported_entities=[],
                semantic_similarity=1.0,
                token_overlap_score=1.0,
                reasoning="Empty claim has no unsupported assertions."
            )

        if not chunk_text.strip():
            return ClaimVerificationResult(
                claim=clean_claim,
                chunk_id=chunk_id,
                faithfulness_score=0.0,
                is_faithful=False,
                verdict="UNSUPPORTED",
                unsupported_entities=["source_chunk_empty"],
                semantic_similarity=0.0,
                token_overlap_score=0.0,
                reasoning="Cited source chunk contains no documentation content."
            )

        # 1. Technical Entity Grounding Check
        claim_entities = extract_technical_entities(clean_claim)
        chunk_lower = chunk_text.lower()
        unsupported = []

        # Check endpoints
        for ep in claim_entities["endpoints"]:
            if ep.lower() not in chunk_lower:
                unsupported.append(f"endpoint:{ep}")

        # Check HTTP methods
        for m in claim_entities["methods"]:
            if m.lower() not in chunk_lower:
                unsupported.append(f"method:{m}")

        # Check code tokens (parameters, attributes)
        for ct in claim_entities["code_tokens"]:
            if ct.lower() not in chunk_lower:
                unsupported.append(f"code_token:`{ct}`")

        # Check critical numbers (e.g. status codes or pagination limits)
        for num in claim_entities["numbers"]:
            if num not in chunk_text:
                unsupported.append(f"number:{num}")

        total_entities = (
            len(claim_entities["endpoints"]) + 
            len(claim_entities["methods"]) + 
            len(claim_entities["code_tokens"]) + 
            len(claim_entities["numbers"])
        )

        if total_entities > 0:
            entity_support_score = 1.0 - (len(unsupported) / total_entities)
        else:
            entity_support_score = 1.0

        # 2. Token & Lexical Overlap
        token_overlap = compute_token_overlap(clean_claim, chunk_text)

        # 3. Semantic Cosine Similarity
        emb_claim = embedding_service.get_embedding(clean_claim)
        emb_chunk = embedding_service.get_embedding(chunk_text)
        semantic_sim = max(0.0, min(1.0, cosine_similarity(emb_claim, emb_chunk)))
        normalized_semantic = min(1.0, semantic_sim / 0.60)

        # 4. Composite Faithfulness Calculation (0.0 to 1.0)
        # Weighting: 60% lexical/concept recall, 30% normalized semantic, 10% entity support
        base_score = (0.60 * token_overlap) + (0.30 * normalized_semantic) + (0.10 * entity_support_score)

        # When all key claim concepts are present in chunk with zero missing entities, boost score
        if token_overlap >= 0.80 and not unsupported:
            base_score = max(base_score, token_overlap)

        # Apply strict exponential penalty for fabricated technical entities
        if unsupported:
            penalty = 0.5 ** len(unsupported)
            base_score *= penalty

        # Exact substring boost: If the claim is a direct excerpt from the chunk
        if clean_claim.lower() in chunk_lower:
            base_score = max(base_score, 0.98)

        # Scale to 0-100%
        faithfulness_pct = round(max(0.0, min(100.0, base_score * 100.0)), 1)
        is_faithful = faithfulness_pct >= pass_thresh

        # Determine qualitative verdict
        if faithfulness_pct >= 85.0:
            verdict = "SUPPORTED"
            reasoning = "Claim is fully grounded and supported by the cited documentation chunk."
        elif faithfulness_pct >= pass_thresh:
            verdict = "PARTIALLY_SUPPORTED"
            reasoning = "Claim is largely supported but may rephrase or extrapolate slightly."
        else:
            verdict = "UNSUPPORTED"
            unsupported_str = f" Missing entities: {', '.join(unsupported)}." if unsupported else ""
            reasoning = f"Claim lacks grounding or contradicts the cited documentation chunk.{unsupported_str}"

        return ClaimVerificationResult(
            claim=clean_claim,
            chunk_id=chunk_id,
            faithfulness_score=faithfulness_pct,
            is_faithful=is_faithful,
            verdict=verdict,
            unsupported_entities=unsupported,
            semantic_similarity=round(semantic_sim, 4),
            token_overlap_score=round(token_overlap, 4),
            reasoning=reasoning
        )

    def parse_claims_from_answer(self, answer: str) -> List[Tuple[str, List[str]]]:
        """
        Parses an LLM generated answer into individual claims tagged with their cited chunk IDs.
        Returns a list of (claim_text, list_of_cited_chunk_ids).
        """
        # Split text into sentence or bullet units
        raw_units = re.split(r'(?<=[.!?\n])\s+', answer)
        claims = []

        for unit in raw_units:
            unit_clean = unit.strip()
            if not unit_clean:
                continue

            cited_ids = extract_citation_tags(unit_clean)
            claim_text = re.sub(CITATION_REGEX, '', unit_clean).strip(" -*#")
            if claim_text:
                claims.append((claim_text, cited_ids))

        return claims

    def verify_answer(
        self,
        answer: str,
        context_chunks: List[Dict[str, Any]],
        threshold: Optional[float] = None
    ) -> AnswerFaithfulnessReport:
        """
        Verifies all claims in a generated answer against the corresponding cited chunks.
        Computes overall aggregate faithfulness percentage (0-100%).
        """
        pass_thresh = threshold if threshold is not None else self.pass_threshold
        parsed_claims = self.parse_claims_from_answer(answer)

        # Map chunks by chunk_id
        chunk_map: Dict[str, Dict[str, Any]] = {}
        for c in context_chunks:
            cid = c.get("chunk_id") or c.get("id")
            if cid:
                chunk_map[str(cid)] = c

        claim_results: List[ClaimVerificationResult] = []

        for claim_text, cited_ids in parsed_claims:
            if not cited_ids:
                # Claim without citation: Check against all available context
                best_result = None
                best_score = -1.0
                for c in context_chunks:
                    res = self.verify_claim(claim_text, c, threshold=pass_thresh)
                    if res.faithfulness_score > best_score:
                        best_score = res.faithfulness_score
                        best_result = res

                if best_result:
                    claim_results.append(best_result)
                else:
                    claim_results.append(ClaimVerificationResult(
                        claim=claim_text,
                        chunk_id=None,
                        faithfulness_score=0.0,
                        is_faithful=False,
                        verdict="UNSUPPORTED",
                        unsupported_entities=["uncited_claim"],
                        semantic_similarity=0.0,
                        token_overlap_score=0.0,
                        reasoning="Claim contains no citation tag and context chunks are empty."
                    ))
            else:
                # Claim with one or more citations
                claim_scores = []
                for cid in cited_ids:
                    chunk_obj = chunk_map.get(cid)
                    if chunk_obj:
                        res = self.verify_claim(claim_text, chunk_obj, chunk_id=cid, threshold=pass_thresh)
                    else:
                        # Hallucinated chunk ID
                        res = ClaimVerificationResult(
                            claim=claim_text,
                            chunk_id=cid,
                            faithfulness_score=0.0,
                            is_faithful=False,
                            verdict="UNSUPPORTED",
                            unsupported_entities=[f"invalid_citation:[^{cid}]"],
                            semantic_similarity=0.0,
                            token_overlap_score=0.0,
                            reasoning=f"Cited chunk ID '{cid}' does not exist in context."
                        )
                    claim_scores.append(res)

                # For multiple citations, pick the best matching supporting chunk
                best_res = max(claim_scores, key=lambda x: x.faithfulness_score)
                claim_results.append(best_res)

        if not claim_results:
            return AnswerFaithfulnessReport(
                overall_score=100.0,
                is_faithful=True,
                total_claims=0,
                faithful_claims_count=0,
                unfaithful_claims_count=0,
                claim_verifications=[]
            )

        avg_score = round(sum(c.faithfulness_score for c in claim_results) / len(claim_results), 1)
        faithful_count = sum(1 for c in claim_results if c.is_faithful)
        unfaithful_count = len(claim_results) - faithful_count
        is_overall_faithful = unfaithful_count == 0 and avg_score >= pass_thresh

        return AnswerFaithfulnessReport(
            overall_score=avg_score,
            is_faithful=is_overall_faithful,
            total_claims=len(claim_results),
            faithful_claims_count=faithful_count,
            unfaithful_claims_count=unfaithful_count,
            claim_verifications=claim_results
        )


# Global singleton instance
faithfulness_evaluator = FaithfulnessEvaluator()


def compute_faithfulness_score(
    claim: str,
    source_chunk: Union[str, Dict[str, Any]]
) -> float:
    """
    Top-level standalone verification function.
    Compares the LLM generated claim against the cited source chunk and returns
    a faithfulness score between 0.0% and 100.0%.
    """
    return faithfulness_evaluator.compute_faithfulness_score(claim, source_chunk)

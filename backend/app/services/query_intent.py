import json
import re
from typing import List, Optional, Dict, Any, Union
from app.core.config import settings
from app.core.logging import logger
from app.schemas.intent import QueryIntentEnum, QueryIntentResponse
from app.services.vector_filter import normalize_version_tag

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class QueryIntentAnalyzer:
    """
    Analyzes developer queries to determine version targeting and intent.
    Supports a hybrid model:
      - Regex/rule-based engine (zero-latency, offline, deterministic)
      - LLM-based engine (Gemini / OpenAI for nuanced natural-language queries)
      - Automatic fallback to regex if LLM is unavailable or unconfigured.
    """

    DEFAULT_KNOWN_VERSIONS = ["v1.0", "v2.0"]

    # Regex patterns for version extraction
    VERSION_PATTERNS = [
        re.compile(r'\bv(\d+(?:\.\d+)*)\b', re.IGNORECASE),                    # v1, v2, v1.0, v2.1
        re.compile(r'\bversion\s*(\d+(?:\.\d+)*)\b', re.IGNORECASE),          # version 1, version 2.0
        re.compile(r'\bv\.\s*(\d+(?:\.\d+)*)\b', re.IGNORECASE),              # v. 1, v.2
    ]

    # Patterns indicating comparison intent
    COMPARISON_PATTERNS = [
        re.compile(r'\bvs\b|\bversus\b', re.IGNORECASE),
        re.compile(r'\bcompare(?:d|ing)?\b', re.IGNORECASE),
        re.compile(r'\bcomparison\b', re.IGNORECASE),
        re.compile(r'\bdiff(?:erence)?(?:s)?\b', re.IGNORECASE),
        re.compile(r'\bchange(?:d|s)?\s+(?:from|between)\b', re.IGNORECASE),
        re.compile(r'\bfrom\s+v?\d+(?:\.\d+)?\s+to\s+v?\d+(?:\.\d+)?\b', re.IGNORECASE),
        re.compile(r'\bbetween\s+v?\d+(?:\.\d+)?\s+and\s+v?\d+(?:\.\d+)?\b', re.IGNORECASE),
    ]

    # Patterns indicating migration or cross-version replacement
    MIGRATION_PATTERNS = [
        re.compile(r'\bmigrat(?:e|ion|ing)\b', re.IGNORECASE),
        re.compile(r'\bupgrad(?:e|ing)\b', re.IGNORECASE),
        re.compile(r'\bdeprecat(?:ed|ion)\b', re.IGNORECASE),
        re.compile(r'\binstead\s+of\b', re.IGNORECASE),
        re.compile(r'\breplace(?:ment)?\s+for\b', re.IGNORECASE),
        re.compile(r'\bswitch(?:ing)?\s+from\b', re.IGNORECASE),
        re.compile(r'\btransition(?:ing)?\b', re.IGNORECASE),
    ]

    # Patterns indicating troubleshooting/error investigation
    TROUBLESHOOTING_PATTERNS = [
        re.compile(r'\b(?:400|401|403|404|422|500|502|503)\b'),
        re.compile(r'\b(?:unauthorized|forbidden|not found|bad request|internal error)\b', re.IGNORECASE),
        re.compile(r'\b(?:error|exception|fail(?:ed|ing|ure)?|issue|bug)\b', re.IGNORECASE),
        re.compile(r'\bwhy\s+(?:do\s+i|am\s+i|does\s+it)\b', re.IGNORECASE),
    ]

    # Endpoint extraction pattern
    ENDPOINT_PATTERN = re.compile(
        r'(?:(?:GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s+)?(/api/[a-zA-Z0-9_\-:{}/]+|/[a-zA-Z0-9_\-:{}/]+)',
        re.IGNORECASE
    )

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        default_model: Optional[str] = None
    ):
        self.gemini_api_key = gemini_api_key or settings.GEMINI_API_KEY
        self.openai_api_key = openai_api_key or settings.OPENAI_API_KEY
        self.llm_provider = settings.EMBEDDING_PROVIDER.lower() if hasattr(settings, "EMBEDDING_PROVIDER") else "gemini"
        self.default_model = default_model

        # Configure Gemini LLM client if available
        self._gemini_client = None
        if self.gemini_api_key and genai:
            try:
                genai.configure(api_key=self.gemini_api_key)
                self._gemini_client = genai.GenerativeModel("gemini-1.5-flash")
                logger.info("QueryIntentAnalyzer initialized with Gemini LLM.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini LLM client: {e}")

        # Configure OpenAI LLM client if available
        self._openai_client = None
        if self.openai_api_key and OpenAI:
            try:
                self._openai_client = OpenAI(api_key=self.openai_api_key)
                logger.info("QueryIntentAnalyzer initialized with OpenAI client.")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")

    def normalize_version(
        self,
        raw_version: str,
        available_versions: Optional[List[str]] = None
    ) -> str:
        """
        Normalizes extracted version string to standard format (e.g. '1' -> 'v1.0' or 'v1.0').
        Resolves against available_versions if provided.
        """
        cleaned = raw_version.strip().lower()
        if not cleaned:
            return "latest"

        # Remove leading 'v' if present for numeric comparison
        num_part = cleaned.lstrip("v").strip()
        has_dot = "." in num_part

        # Check against available versions first
        known = available_versions or self.DEFAULT_KNOWN_VERSIONS
        if known:
            for cand in known:
                cand_clean = cand.lower().lstrip("v")
                if num_part == cand_clean:
                    return cand
                if not has_dot and cand_clean.startswith(f"{num_part}."):
                    return cand

        # Fallback to normalize_version_tag
        if not has_dot and num_part.isdigit():
            # If standard single digit, expand to major.0 if commonly versioned
            return f"v{num_part}.0"

        return normalize_version_tag(cleaned)

    def extract_versions(
        self,
        query: str,
        available_versions: Optional[List[str]] = None
    ) -> List[str]:
        """
        Extracts all explicit version numbers mentioned in the query.
        Returns deduplicated, sorted list of normalized versions.
        """
        raw_versions = []
        for pattern in self.VERSION_PATTERNS:
            matches = pattern.findall(query)
            for m in matches:
                raw_versions.append(m)

        extracted = []
        for rv in raw_versions:
            norm = self.normalize_version(rv, available_versions)
            if norm not in extracted:
                extracted.append(norm)

        # Sort extracted versions cleanly (e.g. v1.0 before v2.0)
        extracted.sort()
        return extracted

    def extract_endpoints(self, query: str) -> List[str]:
        """
        Extracts API endpoint paths mentioned in the query (e.g. /charges, /payments, /users).
        """
        matches = self.ENDPOINT_PATTERN.findall(query)
        endpoints = []
        for ep in matches:
            # Clean up trailing punctuation
            clean_ep = ep.rstrip("?,.;:!)'\"")
            if len(clean_ep) > 1 and clean_ep not in endpoints:
                endpoints.append(clean_ep)
        return endpoints

    def analyze_regex(
        self,
        query: str,
        selected_version: Optional[str] = None,
        available_versions: Optional[List[str]] = None
    ) -> QueryIntentResponse:
        """
        Deterministic regex/rule-based intent and version analysis.
        """
        q = query.strip()
        known = available_versions or self.DEFAULT_KNOWN_VERSIONS
        detected_versions = self.extract_versions(q, available_versions=known)
        detected_endpoints = self.extract_endpoints(q)

        # Check comparison indicators
        has_comparison_keyword = any(p.search(q) for p in self.COMPARISON_PATTERNS)
        has_migration_keyword = any(p.search(q) for p in self.MIGRATION_PATTERNS)
        has_troubleshooting_keyword = any(p.search(q) for p in self.TROUBLESHOOTING_PATTERNS)

        target_versions = list(detected_versions)
        is_comparison = False
        intent = QueryIntentEnum.FEATURE_USAGE.value
        explanation = "Single version feature inquiry."

        # Case 1: Multiple versions explicitly detected
        if len(detected_versions) >= 2:
            is_comparison = True
            intent = QueryIntentEnum.COMPARISON.value
            explanation = f"Query compares {', '.join(detected_versions)} explicitly."

        # Case 2: Comparison keyword with at least one version or implied comparison
        elif has_comparison_keyword:
            is_comparison = True
            intent = QueryIntentEnum.COMPARISON.value
            if len(target_versions) == 1 and selected_version:
                sel_norm = self.normalize_version(selected_version, known)
                if sel_norm not in target_versions:
                    target_versions.append(sel_norm)
                    target_versions.sort()
            elif len(target_versions) == 0 and known:
                # If comparison asked without explicit versions (e.g. "compare auth methods"), target all known
                target_versions = list(known)
            explanation = "Comparison intent detected via comparison keywords."

        # Case 3: Migration / replacement query (e.g. "instead of /charges in v2")
        elif has_migration_keyword:
            intent = QueryIntentEnum.MIGRATION.value
            # Check if query references replacing an older endpoint/feature in a new version
            # E.g. "What endpoint do I use in v2 instead of /charges?"
            if "instead of" in q.lower() or "replace" in q.lower() or "upgrade" in q.lower() or "migrate" in q.lower():
                # Cross-version migration context: requires context from both old and new versions
                if len(target_versions) == 1 and known and len(known) >= 2:
                    # If user asks what to use in v2 instead of old endpoint, doc search needs both versions
                    if "instead of" in q.lower() or "migrate from" in q.lower():
                        target_versions = list(known)
                        is_comparison = True
                        explanation = "Cross-version migration/replacement query targeting transition between versions."
                    else:
                        explanation = f"Migration query targeting {target_versions[0]}."
                else:
                    is_comparison = len(target_versions) > 1
                    explanation = "Migration inquiry between documentation versions."
            else:
                is_comparison = len(target_versions) > 1
                explanation = "Migration or deprecation inquiry."

        # Case 4: Troubleshooting / error diagnostics
        elif has_troubleshooting_keyword:
            intent = QueryIntentEnum.TROUBLESHOOTING.value
            is_comparison = False
            if not target_versions and selected_version:
                target_versions = [self.normalize_version(selected_version, known)]
            explanation = "Troubleshooting or error query."

        # Case 5: Single version explicitly mentioned
        elif len(detected_versions) == 1:
            is_comparison = False
            intent = QueryIntentEnum.FEATURE_USAGE.value
            explanation = f"Targeted single version: {detected_versions[0]}."

        # Case 6: No explicit version in text, fallback to selected_version or general
        else:
            if selected_version:
                target_versions = [self.normalize_version(selected_version, known)]
                is_comparison = False
                intent = QueryIntentEnum.FEATURE_USAGE.value
                explanation = f"Inferred target version from active context: {target_versions[0]}."
            else:
                target_versions = []
                is_comparison = False
                intent = QueryIntentEnum.GENERAL.value
                explanation = "General documentation inquiry without specific version constraints."

        confidence = 0.95 if detected_versions else 0.85

        return QueryIntentResponse(
            query=query,
            is_comparison=is_comparison,
            target_versions=target_versions,
            intent=intent,
            detected_endpoints=detected_endpoints,
            confidence=confidence,
            analysis_mode="regex",
            explanation=explanation
        )

    def analyze_llm(
        self,
        query: str,
        selected_version: Optional[str] = None,
        available_versions: Optional[List[str]] = None
    ) -> QueryIntentResponse:
        """
        LLM-based query intent classification using Gemini or OpenAI.
        """
        known = available_versions or self.DEFAULT_KNOWN_VERSIONS
        system_prompt = (
            "You are an expert API documentation query classifier for DocDrift, a version-aware RAG assistant.\n"
            f"Known workspace versions: {json.dumps(known)}.\n"
            f"Active selected version in UI context: {selected_version or 'None'}.\n\n"
            "Analyze the user query and determine:\n"
            "1. 'is_comparison': true if comparing multiple versions, asking about differences, or migrating between versions; false if asking about a single version.\n"
            "2. 'target_versions': list of targeted versions (e.g. ['v1.0', 'v2.0'] or ['v2.0']).\n"
            "3. 'intent': one of ['single_version', 'comparison', 'migration', 'troubleshooting', 'feature_usage', 'general'].\n"
            "4. 'detected_endpoints': array of API paths mentioned (e.g. ['/charges']).\n"
            "5. 'confidence': float between 0.0 and 1.0.\n"
            "6. 'explanation': brief one-sentence reason.\n\n"
            "Return ONLY a valid JSON object with the above keys."
        )

        # 1. Try Gemini
        if self._gemini_client:
            try:
                prompt = f"{system_prompt}\n\nUser Query: \"{query}\"\nJSON Response:"
                response = self._gemini_client.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                data = json.loads(response.text.strip())
                return QueryIntentResponse(
                    query=query,
                    is_comparison=bool(data.get("is_comparison", False)),
                    target_versions=[normalize_version_tag(v) for v in data.get("target_versions", [])],
                    intent=str(data.get("intent", QueryIntentEnum.FEATURE_USAGE.value)),
                    detected_endpoints=list(data.get("detected_endpoints", [])),
                    confidence=float(data.get("confidence", 0.9)),
                    analysis_mode="llm",
                    explanation=data.get("explanation")
                )
            except Exception as e:
                logger.error(f"Gemini LLM intent classification failed: {e}. Falling back to regex.")

        # 2. Try OpenAI
        if self._openai_client:
            try:
                completion = self._openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query}
                    ],
                    response_format={"type": "json_object"}
                )
                data = json.loads(completion.choices[0].message.content)
                return QueryIntentResponse(
                    query=query,
                    is_comparison=bool(data.get("is_comparison", False)),
                    target_versions=[normalize_version_tag(v) for v in data.get("target_versions", [])],
                    intent=str(data.get("intent", QueryIntentEnum.FEATURE_USAGE.value)),
                    detected_endpoints=list(data.get("detected_endpoints", [])),
                    confidence=float(data.get("confidence", 0.9)),
                    analysis_mode="llm",
                    explanation=data.get("explanation")
                )
            except Exception as e:
                logger.error(f"OpenAI LLM intent classification failed: {e}. Falling back to regex.")

        # 3. Fallback to regex engine if no LLM was successful
        regex_resp = self.analyze_regex(query, selected_version, available_versions)
        regex_resp.analysis_mode = "fallback"
        return regex_resp

    def analyze(
        self,
        query: str,
        selected_version: Optional[str] = None,
        available_versions: Optional[List[str]] = None,
        mode: str = "hybrid"
    ) -> QueryIntentResponse:
        """
        Unified dispatch method for query analysis.
        Supported modes:
          - 'regex': rule-based pattern matching (fast, offline)
          - 'llm': LLM analysis with fallback
          - 'hybrid': regex first, invokes LLM if complex/ambiguous, or provides highest confidence
        """
        mode_lower = (mode or "hybrid").lower()

        if mode_lower == "regex":
            return self.analyze_regex(query, selected_version, available_versions)

        elif mode_lower == "llm":
            return self.analyze_llm(query, selected_version, available_versions)

        # Default: 'hybrid'
        # First perform deterministic regex analysis
        regex_result = self.analyze_regex(query, selected_version, available_versions)

        # If regex result has clear explicit signals or LLM clients are not configured, return regex
        if not (self._gemini_client or self._openai_client):
            return regex_result

        # If regex detected unambiguous explicit multiple versions or single version with high confidence, use it
        if regex_result.confidence >= 0.95 and regex_result.target_versions:
            return regex_result

        # If ambiguous or general query with LLM available, invoke LLM
        return self.analyze_llm(query, selected_version, available_versions)


# Singleton instance
query_intent_analyzer = QueryIntentAnalyzer()

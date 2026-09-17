import re
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.core.logging import logger
from app.core.prompts import (
    DOCDRIFT_SYSTEM_PROMPT,
    format_chunks_for_context,
    build_rag_user_prompt,
    extract_citation_tags,
)
from app.schemas.chat import RAGQueryResponse
from app.schemas.chunk import CitationDetail
from app.models.entities import DocTypeEnum

import importlib
import warnings

# Dynamic imports for LangChain with graceful offline fallback
try:
    _lc_prompts = importlib.import_module("langchain_core.prompts")
    _lc_parsers = importlib.import_module("langchain_core.output_parsers")
    _lc_google = importlib.import_module("langchain_google_genai")
    ChatPromptTemplate = getattr(_lc_prompts, "ChatPromptTemplate", None)
    StrOutputParser = getattr(_lc_parsers, "StrOutputParser", None)
    ChatGoogleGenerativeAI = getattr(_lc_google, "ChatGoogleGenerativeAI", None)
    LANGCHAIN_AVAILABLE = bool(ChatPromptTemplate and StrOutputParser and ChatGoogleGenerativeAI)
except ImportError:
    LANGCHAIN_AVAILABLE = False
    ChatPromptTemplate = None
    StrOutputParser = None
    ChatGoogleGenerativeAI = None

# Dynamic imports for Google GenAI SDK
try:
    modern_genai = importlib.import_module("google.genai")
    genai_types = importlib.import_module("google.genai.types")
except ImportError:
    modern_genai = None
    genai_types = None

try:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        genai = importlib.import_module("google.generativeai")
except ImportError:
    genai = None


class DocDriftRAGPipeline:
    """
    RAG Generation Pipeline for DocDrift.
    Enforces strict version-aware context grounding and [^chunk_id] claim attribution.
    Supports LangChain LCEL, native Gemini SDK, and deterministic offline fallback.
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        model_name: str = "gemini-1.5-flash",
        temperature: float = 0.1
    ):
        self.gemini_api_key = gemini_api_key or settings.GEMINI_API_KEY
        self.model_name = model_name
        self.temperature = temperature
        self._langchain_chain = None
        self._modern_gemini_client = None
        self._native_gemini_model = None

        self._init_models()

    def _init_models(self):
        """Initializes LangChain and native Gemini models if credentials exist."""
        # Initialize LangChain LLM if available
        if LANGCHAIN_AVAILABLE and self.gemini_api_key:
            try:
                llm = ChatGoogleGenerativeAI(
                    model=self.model_name,
                    google_api_key=self.gemini_api_key,
                    temperature=self.temperature
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", DOCDRIFT_SYSTEM_PROMPT),
                    ("human", "{user_prompt}")
                ])
                self._langchain_chain = prompt | llm | StrOutputParser()
                logger.info(f"LangChain Gemini RAG pipeline initialized with {self.model_name}.")
            except Exception as e:
                logger.warning(f"Failed to initialize LangChain Gemini pipeline: {e}")

        # Initialize native modern Google GenAI client if available
        if modern_genai and self.gemini_api_key:
            try:
                self._modern_gemini_client = modern_genai.Client(api_key=self.gemini_api_key)
                logger.info(f"Modern Google GenAI client initialized with {self.model_name}.")
            except Exception as e:
                logger.warning(f"Failed to initialize modern Google GenAI client: {e}")

        # Initialize legacy Gemini model if available
        if genai and self.gemini_api_key:
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=FutureWarning)
                    genai.configure(api_key=self.gemini_api_key)
                    self._native_gemini_model = genai.GenerativeModel(
                        model_name=self.model_name,
                        system_instruction=DOCDRIFT_SYSTEM_PROMPT
                    )
                logger.info(f"Legacy Gemini RAG model initialized with {self.model_name}.")
            except Exception as e:
                logger.warning(f"Failed to initialize legacy Gemini RAG model: {e}")

    def _generate_fallback_response(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        selected_version: Optional[str] = None,
        is_comparison: bool = False
    ) -> str:
        """
        Deterministic, offline fallback response generator.
        Constructs a strictly grounded Markdown answer with [^chunk_id] tags directly mapped
        from the supplied context chunks when external LLM APIs are unreachable or unconfigured.
        """
        if not chunks:
            ver_text = f"version {selected_version}" if selected_version else "the requested version"
            return f"The provided documentation does not contain sufficient information to answer this question for {ver_text}."

        # Group chunks by version tag
        version_chunks = {}
        for c in chunks:
            v = c.get("version") or c.get("version_tag") or "latest"
            version_chunks.setdefault(v, []).append(c)

        lines = []
        if is_comparison and len(version_chunks) >= 2:
            lines.append("### Version Comparison\n")
            for v, v_chunks in sorted(version_chunks.items()):
                lines.append(f"#### Version {v}:")
                for c in v_chunks:
                    cid = c.get("chunk_id") or c.get("id") or "chunk_0"
                    header = c.get("section_header") or "General"
                    # Clean excerpt snippet
                    content_clean = c.get("content", "").replace("\n", " ").strip()
                    snippet = content_clean[:180] + ("..." if len(content_clean) > 180 else "")
                    lines.append(f"- **{header}**: {snippet}[^{cid}]")
                lines.append("")
        else:
            lines.append("Based on the provided documentation:\n")
            for c in chunks:
                cid = c.get("chunk_id") or c.get("id") or "chunk_0"
                ver = c.get("version") or c.get("version_tag") or "latest"
                header = c.get("section_header") or "API Reference"
                content_clean = c.get("content", "").replace("\n", " ").strip()
                snippet = content_clean[:220] + ("..." if len(content_clean) > 220 else "")
                lines.append(f"In {ver}, regarding **{header}**: {snippet}[^{cid}]\n")

        return "\n".join(lines).strip()

    def extract_citations(
        self,
        answer_text: str,
        context_chunks: List[Dict[str, Any]]
    ) -> List[CitationDetail]:
        """
        Extracts all [^chunk_id] tags from the answer text, correlates them with
        the provided context chunks, and builds detailed CitationDetail instances.
        """
        cited_ids = extract_citation_tags(answer_text)
        chunk_map = {}
        for c in context_chunks:
            cid = c.get("chunk_id") or c.get("id")
            if cid:
                chunk_map[str(cid)] = c

        citations = []
        for cid in cited_ids:
            chunk_data = chunk_map.get(cid)
            if chunk_data:
                raw_type = (
                    chunk_data.get("doc_type") or 
                    (chunk_data.get("metadata", {}).get("doc_type") if isinstance(chunk_data.get("metadata"), dict) else None) or 
                    DocTypeEnum.API_REFERENCE
                )
                if isinstance(raw_type, str):
                    try:
                        doc_type_enum = DocTypeEnum(raw_type)
                    except ValueError:
                        doc_type_enum = DocTypeEnum.API_REFERENCE
                else:
                    doc_type_enum = raw_type

                content = chunk_data.get("content") or chunk_data.get("text") or ""
                excerpt = content[:200] + ("..." if len(content) > 200 else "")

                citation = CitationDetail(
                    chunk_id=cid,
                    document_id=chunk_data.get("doc_id") or chunk_data.get("document_id") or "doc_unknown",
                    document_title=(
                        chunk_data.get("document_title") or 
                        chunk_data.get("file_name") or 
                        (chunk_data.get("metadata", {}).get("file_name") if isinstance(chunk_data.get("metadata"), dict) else "Doc")
                    ),
                    version=(
                        chunk_data.get("version") or 
                        chunk_data.get("version_tag") or 
                        (chunk_data.get("metadata", {}).get("version") if isinstance(chunk_data.get("metadata"), dict) else "latest")
                    ),
                    doc_type=doc_type_enum,
                    section_header=(
                        chunk_data.get("section_header") or 
                        (chunk_data.get("metadata", {}).get("section_header") if isinstance(chunk_data.get("metadata"), dict) else "")
                    ),
                    start_line=chunk_data.get("start_line") or (chunk_data.get("metadata", {}).get("start_line") if isinstance(chunk_data.get("metadata"), dict) else None),
                    end_line=chunk_data.get("end_line") or (chunk_data.get("metadata", {}).get("end_line") if isinstance(chunk_data.get("metadata"), dict) else None),
                    excerpt=excerpt,
                    full_chunk_text=content,
                    confidence_score=chunk_data.get("similarity_score", 1.0)
                )
                citations.append(citation)

        return citations

    def validate_grounding(
        self,
        answer_text: str,
        context_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validates whether all citation tags present in the response actually exist
        in the provided context chunks, preventing citation hallucinations.
        """
        cited_ids = set(extract_citation_tags(answer_text))
        valid_chunk_ids = {
            str(c.get("chunk_id") or c.get("id"))
            for c in context_chunks
            if (c.get("chunk_id") or c.get("id"))
        }

        fabricated_ids = list(cited_ids - valid_chunk_ids)
        is_grounded = len(fabricated_ids) == 0

        return {
            "is_grounded": is_grounded,
            "cited_ids": list(cited_ids),
            "valid_chunk_ids": list(valid_chunk_ids),
            "fabricated_ids": fabricated_ids
        }

    def generate(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        selected_version: Optional[str] = None,
        is_comparison: bool = False,
        use_langchain: bool = True
    ) -> RAGQueryResponse:
        """
        Executes the end-to-end grounded RAG generation pipeline.
        Returns a strongly-typed RAGQueryResponse.
        """
        user_prompt = build_rag_user_prompt(
            query=query,
            chunks=context_chunks,
            selected_version=selected_version,
            is_comparison=is_comparison
        )

        answer_text = None
        pipeline_mode = "fallback"

        # 1. Attempt LangChain generation if requested and available
        if use_langchain and self._langchain_chain:
            try:
                answer_text = self._langchain_chain.invoke({"user_prompt": user_prompt})
                pipeline_mode = "langchain"
                logger.info("Generated answer successfully using LangChain pipeline.")
            except Exception as e:
                logger.error(f"LangChain generation error: {e}. Trying native Gemini fallback.")

        # 2. Attempt modern Google GenAI client if LangChain didn't run or failed
        if not answer_text and self._modern_gemini_client and genai_types:
            try:
                response = self._modern_gemini_client.models.generate_content(
                    model=self.model_name,
                    contents=user_prompt,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=DOCDRIFT_SYSTEM_PROMPT,
                        temperature=self.temperature
                    )
                )
                if response and response.text:
                    answer_text = response.text.strip()
                    pipeline_mode = "gemini"
                    logger.info("Generated answer successfully using modern Google GenAI client.")
            except Exception as e:
                logger.error(f"Modern Google GenAI error: {e}. Trying legacy Gemini model if available.")

        # 3. Attempt legacy native Gemini generation if modern SDK didn't run or failed
        if not answer_text and self._native_gemini_model:
            try:
                response = self._native_gemini_model.generate_content(user_prompt)
                if response and response.text:
                    answer_text = response.text.strip()
                    pipeline_mode = "gemini"
                    logger.info("Generated answer successfully using legacy Gemini model.")
            except Exception as e:
                logger.error(f"Legacy Gemini generation error: {e}. Falling back to deterministic generator.")

        # 4. Deterministic offline fallback if no LLM succeeded or in offline mode
        if not answer_text:
            answer_text = self._generate_fallback_response(
                query=query,
                chunks=context_chunks,
                selected_version=selected_version,
                is_comparison=is_comparison
            )
            pipeline_mode = "fallback"

        # Extract structured citations and validate grounding
        citations = self.extract_citations(answer_text, context_chunks)
        grounding_info = self.validate_grounding(answer_text, context_chunks)

        # Compute claim-level faithfulness verification
        from app.services.faithfulness_evaluator import faithfulness_evaluator
        faithfulness_report = faithfulness_evaluator.verify_answer(answer_text, context_chunks)

        return RAGQueryResponse(
            query=query,
            answer=answer_text,
            citations=citations,
            cited_chunk_ids=grounding_info["cited_ids"],
            query_analysis={
                "selected_version": selected_version,
                "is_comparison": is_comparison,
                "chunks_count": len(context_chunks),
                "claims_count": faithfulness_report.total_claims,
                "faithful_claims_count": faithfulness_report.faithful_claims_count,
            },
            is_grounded=grounding_info["is_grounded"],
            faithfulness_score=faithfulness_report.overall_score,
            pipeline_mode=pipeline_mode
        )


# Singleton instance
rag_pipeline = DocDriftRAGPipeline()

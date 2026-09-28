import hashlib
import json
import math
import urllib.request
import urllib.error
from typing import List, Optional
import numpy as np
from app.core.config import settings
from app.core.logging import logger

import importlib
import warnings

# Dynamic imports for optional AI providers (prevents IDE static resolution errors)
try:
    modern_genai = importlib.import_module("google.genai")
except ImportError:
    modern_genai = None

try:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        genai = importlib.import_module("google.generativeai")
except ImportError:
    genai = None


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes cosine similarity between two numerical vectors."""
    a = np.array(vec_a, dtype=float)
    b = np.array(vec_b, dtype=float)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


class EmbeddingService:
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.provider = (provider or settings.EMBEDDING_PROVIDER).lower()
        self.model = model or settings.EMBEDDING_MODEL
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.api_key = api_key or (
            settings.GEMINI_API_KEY if self.provider == "gemini" else settings.OLLAMA_API_KEY
        )
        
        # Configure Gemini
        if self.provider == "gemini":
            if self.api_key and genai:
                genai.configure(api_key=self.api_key)
                logger.info(f"Gemini embedding provider configured with model {self.model}")
            else:
                logger.warning("Gemini API key not configured or google.generativeai missing. Will use fallback generator if called.")

        # Configure Ollama
        elif self.provider == "ollama":
            logger.info(f"Ollama embedding provider configured at {self.base_url} with model {self.model}")

    def _fallback_deterministic_embedding(self, text: str, dim: int = 768) -> List[float]:
        """
        Generates a deterministic, normalized pseudo-embedding for testing/offline scenarios.
        Uses SHA-256 and bag-of-words hashing to produce meaningful semantic vector representations.
        """
        words = text.lower().split()
        vector = np.zeros(dim, dtype=float)
        
        for idx, word in enumerate(words):
            word_hash = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
            position_hash = (word_hash + idx * 31) % dim
            vector[position_hash] += 1.0 + (word_hash % 100) / 100.0
            
        # Add character n-grams to capture subword similarities
        for i in range(len(text) - 2):
            trigram = text[i:i+3].lower()
            trigram_hash = int(hashlib.md5(trigram.encode("utf-8")).hexdigest(), 16) % dim
            vector[trigram_hash] += 0.5

        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector.tolist()

    def _query_ollama_embedding(self, text: str) -> Optional[List[float]]:
        """Queries the Ollama API for embeddings."""
        url = f"{self.base_url}/api/embeddings"
        payload = json.dumps({"model": self.model, "prompt": text}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "embedding" in data:
                    return data["embedding"]
        except Exception as e:
            logger.warning(f"Ollama embedding request failed ({e}). Falling back to deterministic embedding.")
        return None

    def get_embedding(self, text: str) -> List[float]:
        """Generates embedding for a single text string."""
        if not text or not text.strip():
            return [0.0] * 768

        # 1. Ollama
        if self.provider == "ollama":
            res = self._query_ollama_embedding(text)
            if res:
                return res
            return self._fallback_deterministic_embedding(text)

        # 2. Gemini
        elif self.provider == "gemini" and self.api_key and genai:
            try:
                result = genai.embed_content(
                    model=self.model if "models/" in self.model else f"models/{self.model}",
                    content=text,
                    task_type="retrieval_document"
                )
                return result["embedding"]
            except Exception as e:
                logger.error(f"Error calling Gemini Embedding API: {e}. Falling back to deterministic embedding.")
                return self._fallback_deterministic_embedding(text)

        # 3. Fallback
        return self._fallback_deterministic_embedding(text)

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a batch of text strings."""
        if not texts:
            return []
        
        # 1. Ollama Batch (Iterative query or fallback)
        if self.provider == "ollama":
            return [self.get_embedding(t) for t in texts]

        # 2. Gemini Batch
        elif self.provider == "gemini" and self.api_key and genai:
            try:
                result = genai.embed_content(
                    model=self.model if "models/" in self.model else f"models/{self.model}",
                    content=texts,
                    task_type="retrieval_document"
                )
                return result["embedding"]
            except Exception as e:
                logger.error(f"Gemini batch embedding error: {e}. Falling back to item-by-item fallback.")
                return [self.get_embedding(t) for t in texts]

        # Fallback
        return [self.get_embedding(t) for t in texts]


embedding_service = EmbeddingService()


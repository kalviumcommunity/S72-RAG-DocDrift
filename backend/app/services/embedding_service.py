import hashlib
import math
from typing import List, Optional
import numpy as np
from app.core.config import settings
from app.core.logging import logger

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


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
        api_key: Optional[str] = None
    ):
        self.provider = (provider or settings.EMBEDDING_PROVIDER).lower()
        self.model = model or settings.EMBEDDING_MODEL
        self.api_key = api_key or (settings.GEMINI_API_KEY if self.provider == "gemini" else settings.OPENAI_API_KEY)
        
        # Configure Gemini
        if self.provider == "gemini":
            if self.api_key and genai:
                genai.configure(api_key=self.api_key)
                logger.info(f"Gemini embedding provider configured with model {self.model}")
            else:
                logger.warning("Gemini API key not configured or google.generativeai missing. Will use fallback generator if called.")

        # Configure OpenAI
        elif self.provider == "openai":
            if self.api_key and OpenAI:
                self.openai_client = OpenAI(api_key=self.api_key)
                logger.info(f"OpenAI embedding provider configured with model {self.model}")
            else:
                self.openai_client = None
                logger.warning("OpenAI API key not configured or openai package missing. Will use fallback generator if called.")

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

    def get_embedding(self, text: str) -> List[float]:
        """Generates embedding for a single text string."""
        if not text or not text.strip():
            return [0.0] * 768

        # 1. Gemini
        if self.provider == "gemini" and self.api_key and genai:
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

        # 2. OpenAI
        elif self.provider == "openai" and self.openai_client:
            try:
                response = self.openai_client.embeddings.create(
                    input=text,
                    model=self.model if self.model.startswith("text-embedding") else "text-embedding-3-small"
                )
                return response.data[0].embedding
            except Exception as e:
                logger.error(f"Error calling OpenAI Embedding API: {e}. Falling back to deterministic embedding.")
                return self._fallback_deterministic_embedding(text)

        # 3. Fallback
        return self._fallback_deterministic_embedding(text)

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a batch of text strings."""
        if not texts:
            return []
        
        # 1. Gemini Batch
        if self.provider == "gemini" and self.api_key and genai:
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

        # 2. OpenAI Batch
        elif self.provider == "openai" and self.openai_client:
            try:
                response = self.openai_client.embeddings.create(
                    input=texts,
                    model=self.model if self.model.startswith("text-embedding") else "text-embedding-3-small"
                )
                return [d.embedding for d in response.data]
            except Exception as e:
                logger.error(f"OpenAI batch embedding error: {e}. Falling back to item-by-item fallback.")
                return [self.get_embedding(t) for t in texts]

        # Fallback
        return [self.get_embedding(t) for t in texts]


embedding_service = EmbeddingService()

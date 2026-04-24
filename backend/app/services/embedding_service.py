import os
import logging
from typing import List, Union
import asyncio
from concurrent.futures import ThreadPoolExecutor
from sentence_transformers import SentenceTransformer
import numpy as np
import torch

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self.model = None
        self.model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.max_seq_length = 512

    async def initialize(self):
        """Initialize the embedding model"""
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            logger.info(f"Using device: {self.device}")

            # Load model in thread executor to avoid blocking
            self.model = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._load_model
            )

            # Test the model
            test_embedding = await self.encode_text("Test embedding")
            logger.info(
                f"Model loaded successfully. Embedding dimension: {len(test_embedding)}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize embedding service: {e}")
            raise

    def _load_model(self):
        """Load the sentence transformer model"""
        model = SentenceTransformer(self.model_name, device=self.device)
        model.max_seq_length = self.max_seq_length
        return model

    async def encode_text(self, text: str) -> List[float]:
        """Encode a single text into embedding"""
        try:
            # Truncate text if too long
            if len(text) > self.max_seq_length * 4:  # Rough character limit
                text = text[: self.max_seq_length * 4]

            # Encode in thread executor
            embedding = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._encode_single, text
            )

            return embedding.tolist()

        except Exception as e:
            logger.error(f"Failed to encode text: {e}")
            return []

    def _encode_single(self, text: str) -> np.ndarray:
        """Thread-safe single text encoding"""
        return self.model.encode(text, convert_to_numpy=True)

    async def encode_batch(
        self, texts: List[str], batch_size: int = 32
    ) -> List[List[float]]:
        """Encode multiple texts in batches"""
        try:
            # Truncate texts if too long
            processed_texts = []
            for text in texts:
                if len(text) > self.max_seq_length * 4:
                    text = text[: self.max_seq_length * 4]
                processed_texts.append(text)

            # Process in batches
            all_embeddings = []

            for i in range(0, len(processed_texts), batch_size):
                batch = processed_texts[i : i + batch_size]

                # Encode batch in thread executor
                batch_embeddings = await asyncio.get_event_loop().run_in_executor(
                    self.executor, self._encode_batch, batch
                )

                all_embeddings.extend(batch_embeddings.tolist())

                # Log progress for large batches
                if len(processed_texts) > batch_size:
                    progress = min(i + batch_size, len(processed_texts))
                    logger.info(f"Encoded {progress}/{len(processed_texts)} texts")

            return all_embeddings

        except Exception as e:
            logger.error(f"Failed to encode batch: {e}")
            return []

    def _encode_batch(self, texts: List[str]) -> np.ndarray:
        """Thread-safe batch encoding"""
        return self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    async def compute_similarity(self, text1: str, text2: str) -> float:
        """Compute similarity between two texts"""
        try:
            embeddings = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._compute_similarity, text1, text2
            )

            return float(embeddings)

        except Exception as e:
            logger.error(f"Failed to compute similarity: {e}")
            return 0.0

    def _compute_similarity(self, text1: str, text2: str) -> float:
        """Thread-safe similarity computation"""
        embeddings = self.model.encode([text1, text2], convert_to_numpy=True)
        similarity = np.dot(embeddings[0], embeddings[1]) / (
            np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
        )
        return similarity

    async def find_most_similar(
        self, query: str, candidates: List[str], top_k: int = 5
    ) -> List[tuple]:
        """Find most similar texts to query"""
        try:
            if not candidates:
                return []

            # Encode query and candidates
            query_embedding = await self.encode_text(query)
            candidate_embeddings = await self.encode_batch(candidates)

            # Compute similarities
            similarities = []
            for i, candidate_emb in enumerate(candidate_embeddings):
                similarity = np.dot(query_embedding, candidate_emb) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(candidate_emb)
                )
                similarities.append((i, float(similarity), candidates[i]))

            # Sort by similarity and return top_k
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:top_k]

        except Exception as e:
            logger.error(f"Failed to find similar texts: {e}")
            return []

    def get_model_info(self) -> dict:
        """Get information about the loaded model"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "max_seq_length": self.max_seq_length,
            "embedding_dimension": (
                self.model.get_sentence_embedding_dimension() if self.model else None
            ),
            "is_loaded": self.model is not None,
        }

    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.executor:
                self.executor.shutdown(wait=True)

            # Clear model from memory
            if self.model:
                del self.model
                self.model = None

            # Clear CUDA cache if using GPU
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info("Embedding service cleaned up")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def health_check(self) -> dict:
        """Check if the service is healthy"""
        try:
            if not self.model:
                return {"status": "unhealthy", "reason": "Model not loaded"}

            # Test encoding
            test_result = await self.encode_text("Health check test")

            if not test_result:
                return {"status": "unhealthy", "reason": "Encoding failed"}

            return {
                "status": "healthy",
                "model_info": self.get_model_info(),
                "test_embedding_length": len(test_result),
            }

        except Exception as e:
            return {"status": "unhealthy", "reason": str(e)}

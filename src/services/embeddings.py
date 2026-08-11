"""OpenAI embedding client used to vectorise chunks and search queries."""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from src.config import settings

logger = logging.getLogger(__name__)


class EmbeddingsService:
    """Generate OpenAI embeddings for single texts and batches."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.embedding_model

    async def embed(self, text: str) -> list[float]:
        """Embed a single text (used for search queries)."""
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as exc:
            logger.error(f"Embedding failed: {exc}", exc_info=True)
            raise

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed many texts in one API call (used for indexing document chunks)."""
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
            return [r.embedding for r in response.data]
        except Exception as exc:
            logger.error(f"Batch embedding failed: {exc}", exc_info=True)
            raise

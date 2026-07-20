from __future__ import annotations

import asyncpg
import numpy as np
from pgvector.asyncpg import register_vector

from src.config import settings


class PgDriver:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        self._pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=5,
            max_size=20,
            command_timeout=30,
        )
        async with self._pool.acquire() as conn:
            await register_vector(conn)
            await conn.execute("""
                CREATE EXTENSION IF NOT EXISTS vector;
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id SERIAL PRIMARY KEY,
                    document_name TEXT NOT NULL,
                    chunk_index INT NOT NULL,
                    text TEXT NOT NULL,
                    entities JSONB DEFAULT '[]'::jsonb,
                    embedding vector(1536),
                    created_at TIMESTAMPTZ DEFAULT now()
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_embedding
                    ON document_chunks
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100);
            """)

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def store_chunk(
        self,
        document_name: str,
        chunk_index: int,
        text: str,
        entities: list[str],
        embedding: list[float],
    ) -> int:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO document_chunks (document_name, chunk_index, text, entities, embedding)
                VALUES ($1, $2, $3, $4::jsonb, $5::vector)
                RETURNING id
                """,
                document_name,
                chunk_index,
                text,
                entities,
                embedding,
            )
            return row["id"]

    async def similarity_search(
        self,
        embedding: list[float],
        limit: int = 10,
        entity_filter: list[str] | None = None,
    ) -> list[dict]:
        async with self._pool.acquire() as conn:
            if entity_filter:
                rows = await conn.fetch(
                    """
                    SELECT id, document_name, chunk_index, text, entities,
                           1 - (embedding <=> $1::vector) AS similarity
                    FROM document_chunks
                    WHERE entities ?| $3
                    ORDER BY similarity DESC
                    LIMIT $2
                    """,
                    embedding,
                    limit,
                    entity_filter,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, document_name, chunk_index, text, entities,
                           1 - (embedding <=> $1::vector) AS similarity
                    FROM document_chunks
                    ORDER BY similarity DESC
                    LIMIT $2
                    """,
                    embedding,
                    limit,
                )
            return [dict(r) for r in rows]

    async def count_chunks(self) -> int:
        async with self._pool.acquire() as conn:
            row = await conn.fetchval("SELECT count(*) FROM document_chunks")
            return row or 0

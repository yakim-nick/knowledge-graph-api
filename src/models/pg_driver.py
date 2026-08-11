"""Async PostgreSQL/pgvector client for storing and searching document chunks."""

from __future__ import annotations

import asyncpg
from pgvector.asyncpg import register_vector

from src.config import settings


class PgDriver:
    """Async PostgreSQL client managing the connection pool and chunk storage."""

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """Create the connection pool and ensure the vector extension and schema exist."""
        # asyncpg expects a plain postgresql:// DSN, not SQLAlchemy's dialect prefix.
        dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        self._pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=5,
            max_size=20,
            command_timeout=30,
        )
        async with self._pool.acquire() as conn:
            await register_vector(conn)
            await self._ensure_schema(conn)

    async def _ensure_schema(self, conn: asyncpg.Connection) -> None:
        """Create the document_chunks table and its vector index if missing (idempotent)."""
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
        """Close the connection pool."""
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
        """Persist one chunk with its entities and embedding, returning the new row id."""
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

    def _build_similarity_query(
        self, entity_filter: list[str] | None
    ) -> tuple[str, list]:
        """Build the similarity SELECT, adding an entity filter clause when requested.

        Returns the SQL plus any extra parameters beyond the shared
        ($1 embedding, $2 limit) placeholders.
        """
        select = """
            SELECT id, document_name, chunk_index, text, entities,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM document_chunks
        """
        if entity_filter:
            return (
                select + " WHERE entities ?| $3\n ORDER BY similarity DESC\n LIMIT $2",
                [entity_filter],
            )
        return select + " ORDER BY similarity DESC\n LIMIT $2", []

    async def similarity_search(
        self,
        embedding: list[float],
        limit: int = 10,
        entity_filter: list[str] | None = None,
    ) -> list[dict]:
        """Return chunks ranked by cosine similarity, optionally restricted to chunks containing any of the given entities."""
        query, extra_params = self._build_similarity_query(entity_filter)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, embedding, limit, *extra_params)
            return [dict(r) for r in rows]

    async def count_chunks(self) -> int:
        """Return the total number of stored chunks (used for stats)."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchval("SELECT count(*) FROM document_chunks")
            return row or 0

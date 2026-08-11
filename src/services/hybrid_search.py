"""Hybrid retrieval: pgvector similarity search enriched with Neo4j graph context."""

from __future__ import annotations

import json
import logging
from typing import Any, TYPE_CHECKING

from src.models.schemas import DocumentChunk, SearchResultItem
from src.services.embeddings import EmbeddingsService

if TYPE_CHECKING:
    from src.models.neo4j_driver import Neo4jDriver
    from src.models.pg_driver import PgDriver

logger = logging.getLogger(__name__)

# How many neighbouring relationships to fetch per entity for graph context.
_GRAPH_CONTEXT_ENTITY_LIMIT = 5
_GRAPH_CONTEXT_RELATIONSHIP_LIMIT = 10


class HybridSearch:
    """Index chunks into pgvector and search them with optional graph context."""

    def __init__(self, neo4j: Neo4jDriver, pg: PgDriver) -> None:
        self._neo4j = neo4j
        self._pg = pg
        self._embeddings = EmbeddingsService()

    async def index_chunks(
        self,
        chunks: list[DocumentChunk],
        entities: list[Any],
    ) -> None:
        """Embed every chunk and store it in pgvector, tagged with the document's entity names."""
        texts = [c.text for c in chunks]
        embeddings = await self._embeddings.embed_batch(texts)

        entity_names = list({e.name for e in entities if hasattr(e, "name")})
        entity_names_str = [str(n) for n in entity_names]

        for chunk, emb in zip(chunks, embeddings):
            await self._pg.store_chunk(
                document_name=chunk.document_name,
                chunk_index=chunk.index,
                text=chunk.text,
                entities=entity_names_str,
                embedding=emb,
            )

        logger.info(
            f"Indexed {len(chunks)} chunks with {len(entity_names)} entity labels"
        )

    async def search(
        self,
        query: str,
        n_results: int = 10,
        entity_filter: list[str] | None = None,
        relationship_filter: list[str] | None = None,
    ) -> list[SearchResultItem]:
        """Embed the query, find similar chunks, and attach graph context per result."""
        query_embedding = await self._embeddings.embed(query)

        pg_results = await self._pg.similarity_search(
            embedding=query_embedding,
            limit=n_results,
            entity_filter=entity_filter,
        )

        items: list[SearchResultItem] = []
        for row in pg_results:
            entity_list = self._normalize_entities(row.get("entities"))
            graph_context = await self._fetch_graph_context(entity_list)
            items.append(
                SearchResultItem(
                    id=row["id"],
                    document_name=row["document_name"],
                    chunk_index=row["chunk_index"],
                    text=row["text"],
                    entities=entity_list,
                    similarity=float(row["similarity"]),
                    graph_context=graph_context if graph_context else None,
                )
            )

        return items

    def _normalize_entities(self, raw_entities: Any) -> list[str]:
        """Coerce the entities column (JSONB string or list) into a list of names.

        asyncpg may return JSONB as a JSON string depending on the connection
        configuration, so both shapes must be handled.
        """
        if isinstance(raw_entities, str):
            try:
                return json.loads(raw_entities)
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(raw_entities, list):
            return raw_entities
        return []

    async def _fetch_graph_context(self, entity_names: list[str]) -> list[dict]:
        """Fetch up to N outgoing relationships per entity to enrich a search result.

        Failures are logged and skipped so one broken entity never drops the result.
        """
        graph_context: list[dict] = []
        for entity_name in entity_names[:_GRAPH_CONTEXT_ENTITY_LIMIT]:
            try:
                ctx = await self._neo4j.run_cypher(
                    f"""
                    MATCH (n:Entity {{name: $name}})
                    OPTIONAL MATCH (n)-[r]->(m:Entity)
                    RETURN n.name AS source, type(r) AS rel_type, m.name AS target
                    LIMIT {_GRAPH_CONTEXT_RELATIONSHIP_LIMIT}
                    """,
                    {"name": entity_name},
                )
                graph_context.extend(ctx)
            except Exception as exc:
                logger.warning(f"Graph query for '{entity_name}' failed: {exc}")
        return graph_context

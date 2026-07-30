from __future__ import annotations

import json
import logging
from typing import Any

from src.models.neo4j_driver import Neo4jDriver
from src.models.pg_driver import PgDriver
from src.models.schemas import DocumentChunk, SearchResultItem
from src.services.embeddings import EmbeddingsService

logger = logging.getLogger(__name__)


class HybridSearch:
    def __init__(self, neo4j: Neo4jDriver, pg: PgDriver) -> None:
        self._neo4j = neo4j
        self._pg = pg
        self._embeddings = EmbeddingsService()

    async def index(
        self,
        chunks: list[DocumentChunk],
        entities: list[Any],
    ) -> None:
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

        logger.info(f"Indexed {len(chunks)} chunks with {len(entity_names)} entity labels")

    async def search(
        self,
        query: str,
        n_results: int = 10,
        entity_filter: list[str] | None = None,
        relationship_filter: list[str] | None = None,
    ) -> list[SearchResultItem]:
        query_embedding = await self._embeddings.embed(query)

        pg_results = await self._pg.similarity_search(
            embedding=query_embedding,
            limit=n_results,
            entity_filter=entity_filter,
        )

        items: list[SearchResultItem] = []
        for row in pg_results:
            graph_context: list[dict] = []
            entity_list = row.get("entities", [])
            if isinstance(entity_list, str):
                try:
                    entity_list = json.loads(entity_list)
                except (json.JSONDecodeError, TypeError):
                    entity_list = []
            elif not isinstance(entity_list, list):
                entity_list = []

            for entity_name in entity_list[:5]:
                try:
                    ctx = await self._neo4j.run_cypher(
                        """
                        MATCH (n:Entity {name: $name})
                        OPTIONAL MATCH (n)-[r]->(m:Entity)
                        RETURN n.name AS source, type(r) AS rel_type, m.name AS target
                        LIMIT 10
                        """,
                        {"name": entity_name},
                    )
                    graph_context.extend(ctx)
                except Exception as exc:
                    logger.warning(f"Graph query for '{entity_name}' failed: {exc}")

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

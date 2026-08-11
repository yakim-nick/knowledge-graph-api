"""Document ingestion pipeline: parse -> extract -> build graph -> index vectors."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.models.schemas import DocumentChunk, Entity, IngestResponse, Relationship
from src.services.document_parser import DocumentParser
from src.services.entity_extractor import EntityExtractor
from src.services.graph_builder import GraphBuilder
from src.services.hybrid_search import HybridSearch

if TYPE_CHECKING:
    from src.models.neo4j_driver import Neo4jDriver
    from src.models.pg_driver import PgDriver

logger = logging.getLogger(__name__)


class EmptyDocumentError(Exception):
    """Raised when a document yields no chunks after parsing."""


class IngestionService:
    """Coordinate the full ingestion pipeline shared by the API route."""

    def __init__(self, neo4j: Neo4jDriver, pg: PgDriver) -> None:
        self._neo4j = neo4j
        self._pg = pg
        self._parser = DocumentParser()
        self._extractor = EntityExtractor()

    async def ingest(self, content: bytes, filename: str) -> IngestResponse:
        """Parse *content*, extract entities/relationships, build the graph, and index chunks.

        Returns a summary of what was ingested so the caller can report it.
        Raises EmptyDocumentError when the document produces no chunks.
        """
        chunks = await self._parser.parse(content, filename)
        if not chunks:
            raise EmptyDocumentError(filename)

        entities, relationships = await self._extract_all(chunks)

        nodes_created = await GraphBuilder(self._neo4j).build(entities, relationships)
        await HybridSearch(self._neo4j, self._pg).index_chunks(chunks, entities)

        logger.info(
            f"Ingested '{filename}': "
            f"{len(chunks)} chunks, {len(entities)} entities, "
            f"{len(relationships)} relationships, {nodes_created} nodes"
        )

        return IngestResponse(
            filename=filename,
            chunks_processed=len(chunks),
            entities_extracted=len(entities),
            relationships_mapped=len(relationships),
            nodes_created=nodes_created,
        )

    async def _extract_all(
        self, chunks: list[DocumentChunk]
    ) -> tuple[list[Entity], list[Relationship]]:
        """Run LLM extraction over every chunk, aggregating the results."""
        entities: list[Entity] = []
        relationships: list[Relationship] = []
        for chunk in chunks:
            result = await self._extractor.extract(chunk.text)
            entities.extend(result.entities)
            relationships.extend(result.relationships)
        return entities, relationships

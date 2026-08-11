"""Translate extracted entities/relationships into Neo4j MERGE statements."""

from __future__ import annotations

import logging
import re
from typing import Any, TYPE_CHECKING

from src.models.schemas import Entity, Relationship

if TYPE_CHECKING:
    from src.models.neo4j_driver import Neo4jDriver

logger = logging.getLogger(__name__)

# Whitelists keep the graph schema predictable and prevent label injection.
ALLOWED_ENTITY_TYPES: set[str] = {
    "Service",
    "Database",
    "System",
    "Person",
    "Team",
    "Process",
    "Document",
    "API",
    "Infrastructure",
    "Concept",
    "Entity",
}

ALLOWED_REL_TYPES: set[str] = {
    "DEPENDS_ON",
    "OWNS",
    "USES",
    "DEPLOYS",
    "CONTAINS",
    "MANAGES",
    "COMMUNICATES_WITH",
    "DOCUMENTS",
    "IMPLEMENTS",
}

# Neo4j labels must start with a capital letter and contain only word chars.
_LABEL_RE = re.compile(r"^[A-Z][A-Za-z_]*$")


def _validate_label(label: str, allowed: set[str]) -> str:
    """Return *label* unchanged if it is well-formed and whitelisted, else raise ValueError."""
    if not _LABEL_RE.match(label):
        raise ValueError(f"Invalid label format: '{label}'")
    if label not in allowed:
        raise ValueError(f"Label '{label}' is not in allowed set: {sorted(allowed)}")
    return label


class GraphBuilder:
    """Build the Neo4j graph from extracted entities and relationships."""

    def __init__(self, neo4j: Neo4jDriver) -> None:
        self._neo4j = neo4j

    async def build(
        self,
        entities: list[Entity],
        relationships: list[Relationship],
    ) -> int:
        """Merge all entities and relationships into the graph in one transaction.

        Returns the number of entities processed (used for ingest stats).
        """
        queries: list[tuple[str, dict[str, Any]]] = []
        queries.extend(
            self._merge_entity_query(e.name, e.type, e.properties) for e in entities
        )
        queries.extend(
            self._merge_relationship_query(r.source, r.target, r.rel_type, r.properties)
            for r in relationships
        )

        if not queries:
            return 0

        await self._neo4j.execute_batch(queries)
        logger.info(
            f"Built graph: {len(entities)} entities, {len(relationships)} relationships"
        )
        return len(entities)

    def _merge_entity_query(
        self, name: str, type_: str, props: dict[str, str]
    ) -> tuple[str, dict]:
        """Build a MERGE that creates-or-updates an Entity node keyed by name."""
        label = _validate_label(type_, ALLOWED_ENTITY_TYPES)
        return (
            f"""
            MERGE (n:Entity:{label} {{name: $name}})
            ON CREATE SET n.type = $type, n.properties = $props, n.created_at = datetime()
            ON MATCH SET n.properties = $props, n.type = $type
            """,
            {"name": name, "type": type_, "props": props},
        )

    def _merge_relationship_query(
        self, source: str, target: str, rel_type: str, props: dict[str, str]
    ) -> tuple[str, dict]:
        """Build a MERGE that creates-or-updates a typed relationship between two entities."""
        label = _validate_label(rel_type, ALLOWED_REL_TYPES)
        return (
            f"""
            MATCH (a:Entity {{name: $source}})
            MATCH (b:Entity {{name: $target}})
            MERGE (a)-[r:{label}]->(b)
            ON CREATE SET r.properties = $props
            ON MATCH SET r.properties = $props
            """,
            {"source": source, "target": target, "props": props},
        )

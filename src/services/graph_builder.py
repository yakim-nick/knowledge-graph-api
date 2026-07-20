from __future__ import annotations

import logging
import re
from typing import Any, TYPE_CHECKING

from src.models.schemas import Entity, Relationship

if TYPE_CHECKING:
    from src.models.neo4j_driver import Neo4jDriver

logger = logging.getLogger(__name__)

ALLOWED_ENTITY_TYPES: set[str] = {
    "Service", "Database", "System", "Person", "Team",
    "Process", "Document", "API", "Infrastructure", "Concept",
    "Entity",
}

ALLOWED_REL_TYPES: set[str] = {
    "DEPENDS_ON", "OWNS", "USES", "DEPLOYS", "CONTAINS",
    "MANAGES", "COMMUNICATES_WITH", "DOCUMENTS", "IMPLEMENTS",
}

_LABEL_RE = re.compile(r"^[A-Z][A-Za-z_]*$")


def _sanitize_label(label: str, allowed: set[str]) -> str:
    if not _LABEL_RE.match(label):
        raise ValueError(f"Invalid label format: '{label}'")
    if label not in allowed:
        raise ValueError(f"Label '{label}' is not in allowed set: {sorted(allowed)}")
    return label


class GraphBuilder:
    def __init__(self, neo4j: Neo4jDriver) -> None:
        self._neo4j = neo4j

    async def build(
        self,
        entities: list[Entity],
        relationships: list[Relationship],
    ) -> int:
        queries: list[tuple[str, dict[str, Any]]] = []

        for entity in entities:
            queries.append(
                self._merge_entity_query(entity.name, entity.type, entity.properties)
            )

        for rel in relationships:
            queries.append(
                self._merge_relationship_query(
                    rel.source, rel.target, rel.rel_type, rel.properties
                )
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
        label = _sanitize_label(type_, ALLOWED_ENTITY_TYPES)
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
        label = _sanitize_label(rel_type, ALLOWED_REL_TYPES)
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

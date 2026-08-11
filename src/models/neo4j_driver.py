"""Thin async wrapper around the Neo4j driver for this application."""

from __future__ import annotations

from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver

from src.config import settings


class Neo4jDriver:
    """Async Neo4j client exposing the small set of operations the app needs."""

    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Create the driver and verify connectivity so failures surface at startup."""
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_pool_size=10,
            connection_acquisition_timeout=30.0,
        )
        await self._driver.verify_connectivity()

    async def disconnect(self) -> None:
        """Close the driver and release pooled connections."""
        if self._driver is not None:
            await self._driver.close()

    async def run_cypher(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Run a Cypher query in a fresh session and return all records as dicts."""
        if self._driver is None:
            raise RuntimeError("Neo4j driver not connected. Call connect() first.")
        async with self._driver.session() as session:
            result = await session.run(query, parameters or {})
            return await result.data()

    async def count_nodes(self) -> int:
        """Return the total number of nodes in the graph (used for stats)."""
        rows = await self.run_cypher("MATCH (n) RETURN count(n) AS count")
        return rows[0]["count"] if rows else 0

    async def count_relationships(self) -> int:
        """Return the total number of relationships in the graph (used for stats)."""
        rows = await self.run_cypher("MATCH ()-[r]->() RETURN count(r) AS count")
        return rows[0]["count"] if rows else 0

    async def execute_batch(
        self,
        queries: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """Execute a list of (query, params) pairs inside a single transaction.

        Running the whole batch in one transaction makes graph construction
        atomic: either every MERGE is applied or none is.
        """
        if self._driver is None:
            raise RuntimeError("Neo4j driver not connected.")
        async with self._driver.session() as session:
            async with session.begin_transaction() as tx:
                for query, params in queries:
                    await tx.run(query, params)
                await tx.commit()

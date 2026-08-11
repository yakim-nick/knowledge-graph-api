"""HTTP endpoints for read-only graph queries and hybrid search."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request

from src.services.hybrid_search import HybridSearch

from src.models.schemas import (
    GraphQueryRequest,
    GraphQueryResponse,
    SearchRequest,
    SearchResponse,
)

router = APIRouter(prefix="/query", tags=["query"])

# Cypher keywords that mutate the graph; blocked to keep /query read-only.
_FORBIDDEN_KEYWORDS_RE = re.compile(
    r"\b(?:CREATE|DELETE|SET|REMOVE|DROP|MERGE)\b",
    re.IGNORECASE,
)


def _assert_read_only_query(cypher: str) -> None:
    """Raise HTTP 403 if *cypher* contains any graph-mutating keyword."""
    if _FORBIDDEN_KEYWORDS_RE.search(cypher):
        raise HTTPException(
            status_code=403,
            detail="Write operations not allowed in read-only graph queries",
        )


@router.post("/graph", response_model=GraphQueryResponse)
async def query_graph(request: Request, body: GraphQueryRequest):
    """Run a read-only Cypher query against the graph and return its records."""
    _assert_read_only_query(body.cypher)

    try:
        results = await request.app.state.neo4j.run_cypher(body.cypher, body.parameters)
        return GraphQueryResponse(results=results, query=body.cypher)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/search", response_model=SearchResponse)
async def hybrid_search(request: Request, body: SearchRequest):
    """Run a hybrid vector + graph search and return ranked results."""
    search = HybridSearch(request.app.state.neo4j, request.app.state.pg)
    results = await search.search(
        query=body.query,
        n_results=body.n_results,
        entity_filter=body.entity_filter,
        relationship_filter=body.relationship_filter,
    )
    return SearchResponse(query=body.query, results=results)

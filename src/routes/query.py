from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from src.services.hybrid_search import HybridSearch

from src.models.schemas import (
    GraphQueryRequest,
    GraphQueryResponse,
    SearchRequest,
    SearchResponse,
)

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/graph", response_model=GraphQueryResponse)
async def query_graph(request: Request, body: GraphQueryRequest):
    forbidden_keywords = {"CREATE ", "DELETE ", "SET ", "REMOVE ", "DROP ", "MERGE "}
    upper = body.cypher.upper()
    for kw in forbidden_keywords:
        if kw in upper:
            raise HTTPException(
                status_code=403,
                detail=f"Write operations not allowed: {kw.strip()} is forbidden",
            )

    try:
        results = await request.app.state.neo4j.run_cypher(body.cypher, body.parameters)
        return GraphQueryResponse(results=results, query=body.cypher)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/search", response_model=SearchResponse)
async def hybrid_search(request: Request, body: SearchRequest):
    search = HybridSearch(request.app.state.neo4j, request.app.state.pg)
    results = await search.search(
        query=body.query,
        n_results=body.n_results,
        entity_filter=body.entity_filter,
        relationship_filter=body.relationship_filter,
    )
    return SearchResponse(query=body.query, results=results)

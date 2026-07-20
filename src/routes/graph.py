from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/stats")
async def graph_stats(request: Request):
    node_count = await request.app.state.neo4j.count_nodes()
    rel_count = await request.app.state.neo4j.count_relationships()
    chunk_count = await request.app.state.pg.count_chunks()
    return {
        "nodes": node_count,
        "relationships": rel_count,
        "vector_chunks": chunk_count,
    }

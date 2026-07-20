from __future__ import annotations

import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, Request

from src.models.schemas import IngestResponse
from src.services.document_parser import DocumentParser
from src.services.entity_extractor import EntityExtractor
from src.services.graph_builder import GraphBuilder
from src.services.hybrid_search import HybridSearch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
async def ingest_document(request: Request, file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    allowed_extensions = {".pdf", ".md", ".txt", ".html", ".json", ".yaml", ".yml"}
    ext = (
        f".{file.filename.rsplit('.', 1)[-1].lower()}"
        if "." in file.filename
        else ""
    )
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {allowed_extensions}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    chunks = await DocumentParser().parse(content, file.filename)
    if not chunks:
        raise HTTPException(status_code=400, detail="Document produced no chunks after parsing")

    all_entities: list = []
    all_relationships: list = []
    extractor = EntityExtractor()

    for chunk in chunks:
        result = await extractor.extract(chunk.text)
        all_entities.extend(result.entities)
        all_relationships.extend(result.relationships)

    graph_builder = GraphBuilder(request.app.state.neo4j)
    nodes_created = await graph_builder.build(all_entities, all_relationships)

    search = HybridSearch(request.app.state.neo4j, request.app.state.pg)
    await search.index(chunks, all_entities)

    logger.info(
        f"Ingested '{file.filename}': "
        f"{len(chunks)} chunks, {len(all_entities)} entities, "
        f"{len(all_relationships)} relationships, {nodes_created} nodes"
    )

    return IngestResponse(
        filename=file.filename,
        chunks_processed=len(chunks),
        entities_extracted=len(all_entities),
        relationships_mapped=len(all_relationships),
        nodes_created=nodes_created,
    )

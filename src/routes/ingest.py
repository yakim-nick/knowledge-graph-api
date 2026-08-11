"""HTTP endpoints for ingesting documents into the knowledge graph."""

from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, HTTPException, Request

from src.models.schemas import IngestResponse
from src.services.ingestion import EmptyDocumentError, IngestionService

router = APIRouter(prefix="/ingest", tags=["ingest"])

# File types the parser can decode into text.
ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt", ".html", ".json", ".yaml", ".yml"}


async def _validate_upload(file: UploadFile) -> bytes:
    """Validate the uploaded file and return its content, raising HTTP 400 on problems."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = f".{file.filename.rsplit('.', 1)[-1].lower()}" if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    return content


@router.post("", response_model=IngestResponse)
async def ingest_document(request: Request, file: UploadFile = File(...)):
    """Ingest an uploaded document: parse, extract, build the graph, and index it."""
    content = await _validate_upload(file)

    service = IngestionService(request.app.state.neo4j, request.app.state.pg)
    try:
        return await service.ingest(content, file.filename)
    except EmptyDocumentError:
        raise HTTPException(
            status_code=400,
            detail="Document produced no chunks after parsing",
        )

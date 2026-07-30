from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.config import settings
from src.middleware.auth import setup_auth
from src.models.neo4j_driver import Neo4jDriver
from src.models.pg_driver import PgDriver
from src.routes.ingest import router as ingest_router
from src.routes.query import router as query_router
from src.routes.graph import router as graph_router

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Knowledge Graph API")
    app.state.neo4j = Neo4jDriver()
    app.state.pg = PgDriver()
    try:
        await app.state.neo4j.connect()
        logger.info("Connected to Neo4j")
        await app.state.pg.connect()
        logger.info("Connected to PostgreSQL/pgvector")
    except Exception:
        logger.critical("Failed to connect to databases", exc_info=True)
        raise
    logger.info("Knowledge Graph API ready")
    yield
    await app.state.neo4j.disconnect()
    await app.state.pg.disconnect()
    logger.info("Knowledge Graph API shut down")


app = FastAPI(
    title="Private Knowledge Graph API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": str(exc) if not settings.is_production else "An unexpected error occurred."},
    )


app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(graph_router)

setup_auth(app)


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/")
async def root():
    return {
        "service": "Private Knowledge Graph API",
        "version": "1.0.0",
        "docs": "/docs",
    }

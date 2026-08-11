"""FastAPI application entrypoint: wiring, lifespan, and global error handling."""

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


async def _connect_databases(app: FastAPI) -> None:
    """Open connections to Neo4j and PostgreSQL, storing drivers on app.state.

    Drivers are attached to app.state so route handlers can reach them via
    ``request.app.state`` without re-creating connections per request.
    """
    app.state.neo4j = Neo4jDriver()
    app.state.pg = PgDriver()
    await app.state.neo4j.connect()
    logger.info("Connected to Neo4j")
    await app.state.pg.connect()
    logger.info("Connected to PostgreSQL/pgvector")


async def _disconnect_databases(app: FastAPI) -> None:
    """Close the database connections held on app.state during shutdown."""
    await app.state.neo4j.disconnect()
    await app.state.pg.disconnect()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the application lifecycle: connect databases on startup, close on shutdown."""
    logger.info("Starting Knowledge Graph API")
    try:
        await _connect_databases(app)
    except Exception:
        logger.critical("Failed to connect to databases", exc_info=True)
        raise
    logger.info("Knowledge Graph API ready")
    yield
    await _disconnect_databases(app)
    logger.info("Knowledge Graph API shut down")


app = FastAPI(
    title="Private Knowledge Graph API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Convert any unhandled exception into a JSON 500 response.

    Internal error details are only exposed outside production to aid debugging.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": str(exc)
            if not settings.is_production
            else "An unexpected error occurred.",
        },
    )


app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(graph_router)

setup_auth(app)


@app.get("/health")
async def health():
    """Liveness probe used by orchestrators and load balancers."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/")
async def root():
    """Service banner pointing users at the interactive API docs."""
    return {
        "service": "Private Knowledge Graph API",
        "version": "1.0.0",
        "docs": "/docs",
    }

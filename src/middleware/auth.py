"""API-key authentication middleware protecting write endpoints."""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_401_UNAUTHORIZED

from src.config import settings

logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-API-Key"

PROTECTED_PREFIXES = ("/ingest",)

AUTH_SKIP_PATHS = ("/health", "/")

# Paths that never require an API key (docs and OpenAPI schema).
_DOCS_PATHS = ("/docs", "/openapi.json", "/redoc")


def _is_public_path(path: str) -> bool:
    """Return True for paths that are always accessible without an API key."""
    return path in AUTH_SKIP_PATHS or path.startswith(_DOCS_PATHS)


def _is_protected_path(path: str) -> bool:
    """Return True for paths that require a valid API key when one is configured."""
    return path.startswith(PROTECTED_PREFIXES)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Reject requests to protected paths unless they carry the configured API key."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # No key configured -> auth is disabled entirely.
        if not settings.api_key:
            return await call_next(request)

        path = request.url.path
        if _is_public_path(path) or not _is_protected_path(path):
            return await call_next(request)

        api_key = request.headers.get(API_KEY_HEADER, "")
        if api_key != settings.api_key:
            logger.warning("Unauthorized request to %s", path)
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key",
            )

        return await call_next(request)


def setup_auth(app: FastAPI) -> None:
    """Attach the API-key middleware to the FastAPI app."""
    app.add_middleware(APIKeyMiddleware)

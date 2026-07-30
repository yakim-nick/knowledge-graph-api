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


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not settings.api_key:
            return await call_next(request)

        path = request.url.path
        if path in AUTH_SKIP_PATHS or path.startswith(("/docs", "/openapi.json", "/redoc")):
            return await call_next(request)

        if path.startswith(PROTECTED_PREFIXES):
            api_key = request.headers.get(API_KEY_HEADER, "")
            if api_key != settings.api_key:
                logger.warning("Unauthorized request to %s", path)
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail="Invalid or missing API key",
                )

        return await call_next(request)


def setup_auth(app: FastAPI) -> None:
    app.add_middleware(APIKeyMiddleware)

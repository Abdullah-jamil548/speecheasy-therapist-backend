from __future__ import annotations

import time
from typing import Callable

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("http")


def _who_from_auth(header: str | None) -> str:
    if not header or not header.lower().startswith("bearer "):
        return "anonymous"
    token = header.split(" ", 1)[1].strip()
    if not token:
        return "anonymous"
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        email = payload.get("email") or "?"
        sub = payload.get("sub") or "?"
        return f"{email} (id={sub})"
    except JWTError:
        return "invalid-token"


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Logs every API hit: who + method + path + status + time."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in ("/health", "/", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)

        who = _who_from_auth(request.headers.get("authorization"))
        started = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - started) * 1000
        log.info(
            "%s | %s %s | %s | %.0fms",
            who,
            request.method,
            request.url.path,
            response.status_code,
            ms,
        )
        return response

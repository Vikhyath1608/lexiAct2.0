"""
app/core/middleware.py
───────────────────────
RequestLoggingMiddleware — generates UUID correlation ID per request,
sets context vars used by structlog, logs method/path/status/duration.

RateLimitMiddleware — Redis sliding window, 429 on breach.
"""
from __future__ import annotations
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.logging import get_logger, request_id_var, user_id_var
from app.core.redis import is_rate_limited

logger = get_logger(__name__)

EXEMPT_PATHS = {"/health", "/health/ready", "/docs", "/redoc", "/openapi.json", "/metrics"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = str(uuid.uuid4())
        request_id_var.set(rid)
        user_id_var.set("-")  # updated in get_current_user if authenticated

        request.state.request_id = rid
        start = time.perf_counter()

        response: Response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = rid

        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        ip = request.headers.get(
            "X-Forwarded-For", request.client.host if request.client else "unknown"
        ).split(",")[0].strip()

        if await is_rate_limited(ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": "60"},
            )

        return await call_next(request)

"""
Security Middleware
====================
- Global error handler (structured JSON error responses)
- Rate limiting per client IP (in-memory sliding window)
- Request ID injection for traceability
"""

import time
import uuid
from collections import defaultdict, deque
from typing import Callable, Deque

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.logging import logger


# ---------------------------------------------------------------------------
# Request ID middleware
# ---------------------------------------------------------------------------

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Injects a unique X-Request-ID header into every request and response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# Global error handler middleware
# ---------------------------------------------------------------------------

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Catches unhandled exceptions and returns a structured JSON error response
    instead of a plain 500 HTML page, with the X-Request-ID for traceability.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            request_id = getattr(request.state, "request_id", "unknown")
            logger.error(
                f"[{request_id}] Unhandled exception on {request.method} {request.url.path}: {exc}",
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "detail": "An unexpected error occurred. Please try again.",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )


# ---------------------------------------------------------------------------
# Rate Limiting middleware (in-memory sliding window)
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple sliding-window rate limiter keyed by client IP.
    Excludes health-check and docs paths from limiting.

    Args:
        max_requests: Max requests allowed per window.
        window_seconds: Rolling window size in seconds.
        excluded_paths: URL path prefixes that bypass rate limiting.
    """

    EXCLUDED_PATHS = {"/", "/api/v1/health", "/api/v1/openapi.json", "/api/v1/docs", "/api/v1/redoc"}

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int = 60,
        window_seconds: int = 60,
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, Deque[float]] = defaultdict(deque)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time.monotonic()
        window_start = now - self.window_seconds
        bucket = self._buckets[client_ip]

        # Evict timestamps outside the window
        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - bucket[0])) + 1
            logger.warning(f"Rate limit exceeded for {client_ip} on {request.url.path}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": f"Rate limit of {self.max_requests} requests/{self.window_seconds}s exceeded.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        return await call_next(request)


# ---------------------------------------------------------------------------
# Input validation helpers (used by endpoints)
# ---------------------------------------------------------------------------

def validate_non_empty(value: str, field_name: str) -> str:
    """Raise ValueError if a string field is blank after stripping."""
    if not value or not value.strip():
        raise ValueError(f"'{field_name}' must not be empty")
    return value.strip()


def sanitize_version_tag(version: str) -> str:
    """
    Normalises a version tag to lowercase and strips whitespace.
    Raises ValueError for obviously malformed values.
    """
    v = version.strip().lower()
    if len(v) > 50:
        raise ValueError("Version tag too long (max 50 chars)")
    return v


# ---------------------------------------------------------------------------
# Register middleware on app
# ---------------------------------------------------------------------------

def apply_security_middleware(
    app: FastAPI,
    rate_limit: int = 60,
    rate_window: int = 60,
) -> None:
    """
    Attaches all security middleware to the FastAPI application.
    Call this BEFORE app startup (e.g. in main.py after app = FastAPI(...)).
    Middleware is applied in LIFO order by Starlette, so register outermost last.
    """
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RateLimitMiddleware, max_requests=rate_limit, window_seconds=rate_window)
    app.add_middleware(RequestIDMiddleware)
    logger.info(
        f"Security middleware applied: rate_limit={rate_limit}req/{rate_window}s"
    )

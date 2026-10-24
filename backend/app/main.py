"""FastAPI application factory: API, structured errors, request IDs, static SPA."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.routes import ApiError, router
from app.config import Settings, get_settings
from app.services.repository import DataRepository


class JsonFormatter(logging.Formatter):
    _std = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update({k: v for k, v in record.__dict__.items() if k not in self._std})
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("winddesk")
    root.handlers = [handler]
    root.setLevel(level)
    root.propagate = False


def _error(
    status: int, code: str, message: str, request: Request, details: list[dict[str, Any]] | None = None
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message, "request_id": getattr(request.state, "request_id", None)}
    if details is not None:
        body["details"] = details
    return JSONResponse({"error": body}, status_code=status)


def create_app(settings: Settings | None = None, repo: DataRepository | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    log = logging.getLogger("winddesk.http")

    app = FastAPI(
        title="Wind Desk API",
        version=__version__,
        description="Point-in-time evaluation of Elexon WINDFOR forecasts against FUELHH wind actuals.",
    )
    app.state.settings = settings
    app.state.repo = repo or DataRepository(settings)

    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET"])

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = rid
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        if request.url.path.startswith("/api/"):
            log.info(
                "request",
                extra={
                    "request_id": rid,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                },
            )
        return response

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status, exc.code, exc.message, request)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "")} for e in exc.errors()]
        return _error(422, "validation_error", "Request parameters are invalid.", request, details)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error(exc.status_code, "http_error", str(exc.detail), request)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", extra={"request_id": getattr(request.state, "request_id", None)})
        return _error(500, "internal_error", "An unexpected error occurred.", request)

    app.include_router(router)

    # Serve the built SPA from the same origin when present (production container / Vercel).
    static = settings.static_dir
    if (static / "index.html").exists():
        if (static / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str, request: Request) -> Response:
            if path.startswith("api/"):
                return _error(404, "http_error", "Not Found", request)
            candidate = (static / path).resolve()
            if path and candidate.is_file() and static.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(static / "index.html")

    return app


app = create_app()

"""Punkt wejścia FastAPI, rejestrujący routery i endpoint diagnostyczny."""

import logging
import os
import subprocess
import time
from uuid import uuid4

from fastapi import FastAPI
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.admin.panel import register_admin_panel
from app.api.v1.router import v1_router
from app.config import get_settings
from app.database.session import engine
from app.logging_config import configure_logging, request_id_context

settings = get_settings()
configure_logging(settings.log_level)

logger = logging.getLogger(__name__)


def _commit_hash() -> str:
    """Zwraca hash bieżącego commita albo wartość developerską."""

    configured_hash = os.getenv("GIT_COMMIT")
    if configured_hash:
        return configured_hash
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "development"


app = FastAPI(title="Safe Route Backend", version="0.1.0")
app.include_router(v1_router, prefix="/v1")
register_admin_panel(app, engine)


@app.middleware("http")
async def log_http_requests(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    request_id = uuid4().hex
    started_at = time.perf_counter()
    context_token = request_id_context.set(request_id)
    try:
        response = await call_next(request)
    except Exception as exc:
        route = request.scope.get("route")
        logger.error(
            "Unhandled request error request_id=%s method=%s route=%s error=%s",
            request_id,
            request.method,
            getattr(route, "path", "unmatched"),
            type(exc).__name__,
        )
        raise
    finally:
        request_id_context.reset(context_token)

    elapsed_ms = (time.perf_counter() - started_at) * 1_000
    route = request.scope.get("route")
    route_template = getattr(route, "path", "unmatched")
    log = logger.error if response.status_code >= 500 else logger.info
    log(
        "HTTP request request_id=%s method=%s route=%s status=%d duration_ms=%.2f",
        request_id,
        request.method,
        route_template,
        response.status_code,
        elapsed_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
def health() -> dict[str, str]:
    """Zwraca wersję API i hash commita dla liveness check."""

    return {
        "status": "ok",
        "version": app.version,
        "commit": _commit_hash(),
        "mode": settings.api_mode,
    }

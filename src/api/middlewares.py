"""Browser request policy, CORS and request tracing."""

import re
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from src.config import settings
from src.utils.logger import logger


async def protect_browser_requests(request: Request, call_next):
    # CORS alone does not prevent cross-site form submissions using cookies.
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        allowed = {value.strip() for value in settings.CORS_ORIGINS.split(",")}
        if origin and origin not in allowed:
            return JSONResponse(status_code=403, content={"detail": "Nguồn yêu cầu không được phép."})
    response = await call_next(request)
    if request.url.path.startswith(("/api/", "/static/")):
        response.headers["Cache-Control"] = "no-store"
    return response


def _trace_headers(request):
    elapsed_ms = (perf_counter() - request.state.started_at) * 1000
    return {"X-Request-ID": request.state.request_id, "X-Process-Time": f"{elapsed_ms:.3f}"}


async def trace_request(request: Request, call_next):
    supplied = request.headers.get("X-Request-ID", "")
    request.state.request_id = supplied if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", supplied) else str(uuid4())
    request.state.started_at = perf_counter()
    with logger.contextualize(request_id=request.state.request_id):
        response = await call_next(request)
        response.headers.update(_trace_headers(request))
        logger.info("{} {} {}", request.method, request.scope.get("route", request.url).path, response.status_code)
        return response


async def unexpected_error(request: Request, exc: Exception):
    with logger.contextualize(request_id=request.state.request_id):
        logger.error("Unhandled request error: {}", type(exc).__name__)
    return PlainTextResponse("Internal Server Error", status_code=500, headers=_trace_headers(request))


def configure_middlewares(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )
    app.middleware("http")(protect_browser_requests)
    app.middleware("http")(trace_request)
    app.add_exception_handler(Exception, unexpected_error)

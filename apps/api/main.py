import logging
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from apps.api.core.config import get_settings
from apps.api.core.errors import register_exception_handlers
from apps.api.core.logging import configure_logging, reset_request_id, set_request_id
from apps.api.routes import api_router

request_logger = logging.getLogger("apps.api.requests")


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    yield


settings = get_settings()

app = FastAPI(
    title="CreatorOS API",
    description="Orchestration API for the CreatorOS content workflow",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
register_exception_handlers(app)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    token = set_request_id(request_id)
    started_at = perf_counter()
    try:
        response = await call_next(request)
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        request_logger.info(
            "API request completed",
            extra={
                "duration_ms": duration_ms,
                "http_method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
            },
        )
        return response
    except Exception:
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        request_logger.exception(
            "API request failed",
            extra={
                "duration_ms": duration_ms,
                "http_method": request.method,
                "path": request.url.path,
            },
        )
        raise
    finally:
        reset_request_id(token)


@app.get("/", tags=["meta"])
def read_root() -> dict[str, str]:
    return {
        "name": "CreatorOS API",
        "environment": settings.app_env,
        "docs_url": "/docs",
    }

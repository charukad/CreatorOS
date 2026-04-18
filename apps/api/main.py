from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.core.config import get_settings
from apps.api.core.logging import configure_logging
from apps.api.routes import api_router


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


@app.get("/", tags=["meta"])
def read_root() -> dict[str, str]:
    return {
        "name": "CreatorOS API",
        "environment": settings.app_env,
        "docs_url": "/docs",
    }

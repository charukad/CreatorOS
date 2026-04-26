from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from apps.api.core.config import get_settings
from apps.api.services.job_events import build_background_job_events_stream

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/background-jobs/stream")
def stream_background_job_events_route(
    project_id: Annotated[UUID | None, Query()] = None,
    job_id: Annotated[UUID | None, Query()] = None,
) -> StreamingResponse:
    settings = get_settings()
    return StreamingResponse(
        build_background_job_events_stream(
            settings.redis_url,
            project_id=project_id,
            job_id=job_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

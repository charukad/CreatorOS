from datetime import UTC, datetime

from apps.api.core.redis import publish_json
from apps.api.models.background_job import BackgroundJob
from apps.api.schemas.enums import BackgroundJobType

GENERAL_JOB_EVENTS_CHANNEL = "creatoros:jobs:events"
WORKER_WAKEUP_CHANNELS = {
    "browser": "creatoros:jobs:wakeup:browser",
    "media": "creatoros:jobs:wakeup:media",
    "publisher": "creatoros:jobs:wakeup:publisher",
    "analytics": "creatoros:jobs:wakeup:analytics",
}


def emit_background_job_event(
    job: BackgroundJob,
    *,
    event_type: str,
    publish_to_worker_queue: bool = False,
    metadata: dict[str, object] | None = None,
) -> None:
    payload_json = job.payload_json if isinstance(job.payload_json, dict) else {}
    worker_type = resolve_background_job_worker_type(job.job_type)
    event = {
        "event_type": event_type,
        "background_job_id": str(job.id),
        "job_type": job.job_type.value,
        "job_state": job.state.value,
        "provider_name": job.provider_name.value if job.provider_name is not None else None,
        "project_id": str(job.project_id),
        "script_id": str(job.script_id) if job.script_id is not None else None,
        "worker_type": worker_type,
        "correlation_id": payload_json.get("correlation_id"),
        "published_at": datetime.now(UTC).isoformat(),
        "metadata": metadata or {},
    }
    publish_json(GENERAL_JOB_EVENTS_CHANNEL, event)

    if publish_to_worker_queue and worker_type in WORKER_WAKEUP_CHANNELS:
        publish_json(WORKER_WAKEUP_CHANNELS[worker_type], event)


def resolve_background_job_worker_type(job_type: BackgroundJobType) -> str:
    if job_type in {
        BackgroundJobType.GENERATE_AUDIO_BROWSER,
        BackgroundJobType.GENERATE_VISUALS_BROWSER,
    }:
        return "browser"
    if job_type in {BackgroundJobType.COMPOSE_ROUGH_CUT, BackgroundJobType.FINAL_EXPORT}:
        return "media"
    if job_type == BackgroundJobType.PUBLISH_CONTENT:
        return "publisher"
    if job_type == BackgroundJobType.SYNC_ANALYTICS:
        return "analytics"
    return "inline_local"

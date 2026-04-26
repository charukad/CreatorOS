from __future__ import annotations

import json
import logging
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from time import monotonic
from typing import Protocol
from uuid import UUID

from redis.exceptions import RedisError

from apps.api.core.redis import get_redis_client
from apps.api.services.queue_events import GENERAL_JOB_EVENTS_CHANNEL

logger = logging.getLogger(__name__)


class RedisPubSubLike(Protocol):
    def subscribe(self, *channels: str) -> None: ...

    def get_message(
        self,
        *,
        ignore_subscribe_messages: bool = True,
        timeout: float = 0.0,
    ) -> dict[str, object] | None: ...

    def close(self) -> None: ...


def build_background_job_events_stream(
    redis_url: str,
    *,
    project_id: UUID | None = None,
    job_id: UUID | None = None,
    keepalive_seconds: float = 15.0,
    poll_timeout_seconds: float = 1.0,
    monotonic_fn: Callable[[], float] = monotonic,
) -> Generator[str, None, None]:
    pubsub = get_redis_client(redis_url).pubsub()
    pubsub.subscribe(GENERAL_JOB_EVENTS_CHANNEL)
    yield _format_sse_event(
        "stream_open",
        {"channel": GENERAL_JOB_EVENTS_CHANNEL, "opened_at": datetime.now(UTC).isoformat()},
    )
    yield "retry: 5000\n\n"

    last_sent_at = monotonic_fn()
    try:
        while True:
            try:
                message = pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=poll_timeout_seconds,
                )
            except (OSError, RedisError, ValueError) as error:
                logger.warning(
                    "Background job event stream listener failed",
                    extra={"error_type": error.__class__.__name__},
                )
                yield _format_sse_event(
                    "stream_error",
                    {
                        "error_type": error.__class__.__name__,
                        "occurred_at": datetime.now(UTC).isoformat(),
                    },
                )
                return

            event = parse_background_job_event_message(message)
            now = monotonic_fn()
            if event is None:
                if (now - last_sent_at) >= keepalive_seconds:
                    yield _format_sse_event(
                        "keepalive",
                        {"sent_at": datetime.now(UTC).isoformat()},
                    )
                    last_sent_at = now
                continue

            if not _event_matches_filters(event, project_id=project_id, job_id=job_id):
                continue

            yield _format_sse_event("job_event", event)
            last_sent_at = now
    finally:
        pubsub.close()


def parse_background_job_event_message(message: object) -> dict[str, object] | None:
    if not isinstance(message, dict):
        return None

    if message.get("type") != "message":
        return None

    raw_payload = message.get("data")
    if not isinstance(raw_payload, str) or raw_payload.strip() == "":
        return None

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    return payload


def _event_matches_filters(
    event: dict[str, object],
    *,
    project_id: UUID | None,
    job_id: UUID | None,
) -> bool:
    if project_id is not None and event.get("project_id") != str(project_id):
        return False
    if job_id is not None and event.get("background_job_id") != str(job_id):
        return False
    return True


def _format_sse_event(event_type: str, payload: dict[str, object]) -> str:
    serialized_payload = json.dumps(payload, sort_keys=True)
    return f"event: {event_type}\ndata: {serialized_payload}\n\n"

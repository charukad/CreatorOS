from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from redis.exceptions import RedisError

from apps.api.core.redis import get_redis_client

WORKER_HEARTBEAT_KEY_PREFIX = "creatoros:workers:heartbeat:"
WORKER_HEARTBEAT_TTL_SECONDS = 90


@dataclass(frozen=True)
class WorkerHeartbeat:
    worker_id: str
    worker_name: str
    worker_type: str
    status: str
    redis_listener_enabled: bool
    last_seen_at: str
    started_at: str
    processed_total: int
    wakeups_seen: int
    last_job_id: str | None
    last_job_type: str | None
    last_event_type: str | None
    active_job_count: int
    idle_shutdown_seconds: float
    poll_interval_seconds: float
    listen_timeout_seconds: float

    def to_json(self) -> dict[str, object]:
        return {
            "worker_id": self.worker_id,
            "worker_name": self.worker_name,
            "worker_type": self.worker_type,
            "status": self.status,
            "redis_listener_enabled": self.redis_listener_enabled,
            "last_seen_at": self.last_seen_at,
            "started_at": self.started_at,
            "processed_total": self.processed_total,
            "wakeups_seen": self.wakeups_seen,
            "last_job_id": self.last_job_id,
            "last_job_type": self.last_job_type,
            "last_event_type": self.last_event_type,
            "active_job_count": self.active_job_count,
            "idle_shutdown_seconds": self.idle_shutdown_seconds,
            "poll_interval_seconds": self.poll_interval_seconds,
            "listen_timeout_seconds": self.listen_timeout_seconds,
        }


def build_worker_heartbeat_key(worker_id: str) -> str:
    return f"{WORKER_HEARTBEAT_KEY_PREFIX}{worker_id}"


def write_worker_heartbeat(
    *,
    redis_url: str,
    worker_id: str,
    worker_name: str,
    worker_type: str,
    status: str,
    redis_listener_enabled: bool,
    started_at: str,
    processed_total: int,
    wakeups_seen: int,
    last_job_id: str | None,
    last_job_type: str | None,
    last_event_type: str | None,
    active_job_count: int,
    idle_shutdown_seconds: float,
    poll_interval_seconds: float,
    listen_timeout_seconds: float,
    now: datetime | None = None,
) -> bool:
    heartbeat = WorkerHeartbeat(
        worker_id=worker_id,
        worker_name=worker_name,
        worker_type=worker_type,
        status=status,
        redis_listener_enabled=redis_listener_enabled,
        last_seen_at=(now or datetime.now(UTC)).isoformat(),
        started_at=started_at,
        processed_total=processed_total,
        wakeups_seen=wakeups_seen,
        last_job_id=last_job_id,
        last_job_type=last_job_type,
        last_event_type=last_event_type,
        active_job_count=active_job_count,
        idle_shutdown_seconds=idle_shutdown_seconds,
        poll_interval_seconds=poll_interval_seconds,
        listen_timeout_seconds=listen_timeout_seconds,
    )

    try:
        get_redis_client(redis_url).set(
            build_worker_heartbeat_key(worker_id),
            json.dumps(heartbeat.to_json(), sort_keys=True),
            ex=WORKER_HEARTBEAT_TTL_SECONDS,
        )
    except (OSError, RedisError, ValueError):
        return False

    return True


def clear_worker_heartbeat(*, redis_url: str, worker_id: str) -> bool:
    try:
        get_redis_client(redis_url).delete(build_worker_heartbeat_key(worker_id))
    except (OSError, RedisError, ValueError):
        return False

    return True


def list_worker_heartbeats(redis_url: str) -> list[dict[str, object]]:
    try:
        redis_client = get_redis_client(redis_url)
        raw_keys = sorted(redis_client.scan_iter(f"{WORKER_HEARTBEAT_KEY_PREFIX}*"))
    except (OSError, RedisError, ValueError):
        return []

    heartbeats: list[dict[str, object]] = []
    for key in raw_keys:
        try:
            payload = redis_client.get(key)
        except (OSError, RedisError, ValueError):
            continue

        if not isinstance(payload, str) or payload.strip() == "":
            continue

        try:
            parsed_payload = json.loads(payload)
        except json.JSONDecodeError:
            continue

        if not isinstance(parsed_payload, dict):
            continue

        heartbeats.append(_normalize_worker_heartbeat(parsed_payload))

    heartbeats.sort(
        key=lambda item: (
            str(item.get("worker_type", "")),
            str(item.get("worker_name", "")),
            str(item.get("worker_id", "")),
        )
    )
    return heartbeats


def _normalize_worker_heartbeat(payload: dict[str, Any]) -> dict[str, object]:
    return {
        "worker_id": str(payload.get("worker_id", "")),
        "worker_name": str(payload.get("worker_name", "")),
        "worker_type": str(payload.get("worker_type", "")),
        "status": str(payload.get("status", "unknown")),
        "redis_listener_enabled": bool(payload.get("redis_listener_enabled", False)),
        "last_seen_at": str(payload.get("last_seen_at", "")),
        "started_at": str(payload.get("started_at", "")),
        "processed_total": int(payload.get("processed_total", 0)),
        "wakeups_seen": int(payload.get("wakeups_seen", 0)),
        "last_job_id": _coerce_optional_string(payload.get("last_job_id")),
        "last_job_type": _coerce_optional_string(payload.get("last_job_type")),
        "last_event_type": _coerce_optional_string(payload.get("last_event_type")),
        "active_job_count": int(payload.get("active_job_count", 0)),
        "idle_shutdown_seconds": float(payload.get("idle_shutdown_seconds", 0.0)),
        "poll_interval_seconds": float(payload.get("poll_interval_seconds", 0.0)),
        "listen_timeout_seconds": float(payload.get("listen_timeout_seconds", 0.0)),
    }


def _coerce_optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None

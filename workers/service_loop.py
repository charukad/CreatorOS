from __future__ import annotations

import json
import logging
import os
import socket
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic, sleep
from typing import Protocol, TypeAlias
from uuid import uuid4

from apps.api.core.redis import get_redis_client
from apps.api.services.queue_events import WORKER_WAKEUP_CHANNELS
from apps.api.services.worker_presence import clear_worker_heartbeat, write_worker_heartbeat
from redis.exceptions import RedisError


class WorkerWakeListener(Protocol):
    def wait_for_wakeup(self, timeout_seconds: float) -> dict[str, object] | None: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class WorkerServiceConfig:
    worker_name: str
    worker_type: str
    redis_url: str
    enable_redis_listener: bool
    poll_interval_seconds: float
    listen_timeout_seconds: float
    idle_shutdown_seconds: float
    max_jobs_per_iteration: int | None


WorkerProcessor: TypeAlias = Callable[[int | None], int]
WorkerListenerFactory: TypeAlias = Callable[
    [WorkerServiceConfig, logging.Logger],
    WorkerWakeListener,
]


class RedisWorkerWakeListener:
    def __init__(
        self,
        *,
        redis_url: str,
        worker_type: str,
        logger: logging.Logger,
        reconnect_backoff_seconds: float,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> None:
        self._redis_url = redis_url
        self._worker_type = worker_type
        self._logger = logger
        self._reconnect_backoff_seconds = reconnect_backoff_seconds
        self._sleep = sleep_fn
        self._channel = WORKER_WAKEUP_CHANNELS[worker_type]
        self._pubsub = None

    def wait_for_wakeup(self, timeout_seconds: float) -> dict[str, object] | None:
        if not self._ensure_subscription():
            return None

        try:
            message = self._pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=timeout_seconds,
            )
        except (OSError, RedisError, ValueError) as error:
            self._logger.warning(
                "Redis worker listener read failed",
                extra={
                    "channel": self._channel,
                    "error_type": error.__class__.__name__,
                    "worker_type": self._worker_type,
                },
            )
            self.close()
            self._sleep(self._reconnect_backoff_seconds)
            return None

        event = _parse_job_event_message(message)
        if event is None:
            return None

        self._logger.info(
            "Worker wake-up event received",
            extra={
                "channel": self._channel,
                "event_type": event.get("event_type"),
                "background_job_id": event.get("background_job_id"),
                "worker_type": self._worker_type,
            },
        )
        return event

    def close(self) -> None:
        if self._pubsub is None:
            return

        try:
            self._pubsub.close()
        finally:
            self._pubsub = None

    def _ensure_subscription(self) -> bool:
        if self._pubsub is not None:
            return True

        try:
            self._pubsub = get_redis_client(self._redis_url).pubsub()
            self._pubsub.subscribe(self._channel)
        except (OSError, RedisError, ValueError) as error:
            self._logger.warning(
                "Redis worker listener connect failed",
                extra={
                    "channel": self._channel,
                    "error_type": error.__class__.__name__,
                    "worker_type": self._worker_type,
                },
            )
            self.close()
            self._sleep(self._reconnect_backoff_seconds)
            return False

        return True


def run_worker_service(
    *,
    config: WorkerServiceConfig,
    logger: logging.Logger,
    process_pending_jobs: WorkerProcessor,
    listener_factory: WorkerListenerFactory | None = None,
    sleep_fn: Callable[[float], None] = sleep,
    monotonic_fn: Callable[[], float] = monotonic,
) -> int:
    listener: WorkerWakeListener | None = None
    if config.enable_redis_listener:
        listener = (
            listener_factory(config, logger)
            if listener_factory is not None
            else RedisWorkerWakeListener(
                redis_url=config.redis_url,
                worker_type=config.worker_type,
                logger=logger,
                reconnect_backoff_seconds=config.poll_interval_seconds,
                sleep_fn=sleep_fn,
            )
        )

    processed_total = 0
    last_activity_at = monotonic_fn()
    worker_id = _build_worker_id(config)
    started_at = datetime.now(UTC).isoformat()
    wakeups_seen = 0
    last_job_id: str | None = None
    last_job_type: str | None = None
    last_event_type: str | None = "worker_started"
    active_job_count = 0

    _publish_worker_presence(
        config=config,
        worker_id=worker_id,
        started_at=started_at,
        status="starting",
        processed_total=processed_total,
        wakeups_seen=wakeups_seen,
        last_job_id=last_job_id,
        last_job_type=last_job_type,
        last_event_type=last_event_type,
        active_job_count=active_job_count,
    )

    try:
        while True:
            processed_jobs = process_pending_jobs(config.max_jobs_per_iteration)
            if processed_jobs > 0:
                processed_total += processed_jobs
                last_activity_at = monotonic_fn()
                last_event_type = "jobs_processed"
                active_job_count = processed_jobs
                _publish_worker_presence(
                    config=config,
                    worker_id=worker_id,
                    started_at=started_at,
                    status="processing",
                    processed_total=processed_total,
                    wakeups_seen=wakeups_seen,
                    last_job_id=last_job_id,
                    last_job_type=last_job_type,
                    last_event_type=last_event_type,
                    active_job_count=active_job_count,
                )
                if (
                    config.max_jobs_per_iteration is not None
                    and processed_jobs >= config.max_jobs_per_iteration
                ):
                    continue

            if _idle_shutdown_reached(
                idle_shutdown_seconds=config.idle_shutdown_seconds,
                last_activity_at=last_activity_at,
                monotonic_fn=monotonic_fn,
            ):
                _publish_worker_presence(
                    config=config,
                    worker_id=worker_id,
                    started_at=started_at,
                    status="idle_shutdown",
                    processed_total=processed_total,
                    wakeups_seen=wakeups_seen,
                    last_job_id=last_job_id,
                    last_job_type=last_job_type,
                    last_event_type="idle_shutdown",
                    active_job_count=0,
                )
                logger.info(
                    "Worker idle shutdown reached",
                    extra={"worker_type": config.worker_type, "processed_total": processed_total},
                )
                return processed_total

            if listener is None:
                _publish_worker_presence(
                    config=config,
                    worker_id=worker_id,
                    started_at=started_at,
                    status="polling",
                    processed_total=processed_total,
                    wakeups_seen=wakeups_seen,
                    last_job_id=last_job_id,
                    last_job_type=last_job_type,
                    last_event_type="polling_wait",
                    active_job_count=0,
                )
                sleep_fn(config.poll_interval_seconds)
                continue

            _publish_worker_presence(
                config=config,
                worker_id=worker_id,
                started_at=started_at,
                status="listening",
                processed_total=processed_total,
                wakeups_seen=wakeups_seen,
                last_job_id=last_job_id,
                last_job_type=last_job_type,
                last_event_type="listener_wait",
                active_job_count=0,
            )
            wake_event = listener.wait_for_wakeup(config.listen_timeout_seconds)
            if wake_event is not None:
                last_activity_at = monotonic_fn()
                wakeups_seen += 1
                last_job_id = _coerce_optional_string(wake_event.get("background_job_id"))
                last_job_type = _coerce_optional_string(wake_event.get("job_type"))
                last_event_type = _coerce_optional_string(wake_event.get("event_type")) or "wakeup"
                _publish_worker_presence(
                    config=config,
                    worker_id=worker_id,
                    started_at=started_at,
                    status="wakeup_received",
                    processed_total=processed_total,
                    wakeups_seen=wakeups_seen,
                    last_job_id=last_job_id,
                    last_job_type=last_job_type,
                    last_event_type=last_event_type,
                    active_job_count=0,
                )
    finally:
        _publish_worker_presence(
            config=config,
            worker_id=worker_id,
            started_at=started_at,
            status="stopping",
            processed_total=processed_total,
            wakeups_seen=wakeups_seen,
            last_job_id=last_job_id,
            last_job_type=last_job_type,
            last_event_type="worker_stopped",
            active_job_count=0,
        )
        if listener is not None:
            listener.close()
        clear_worker_heartbeat(redis_url=config.redis_url, worker_id=worker_id)


def _idle_shutdown_reached(
    *,
    idle_shutdown_seconds: float,
    last_activity_at: float,
    monotonic_fn: Callable[[], float],
) -> bool:
    if idle_shutdown_seconds <= 0:
        return False
    return (monotonic_fn() - last_activity_at) >= idle_shutdown_seconds


def _parse_job_event_message(message: object) -> dict[str, object] | None:
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


def _build_worker_id(config: WorkerServiceConfig) -> str:
    hostname = socket.gethostname().split(".")[0] or "localhost"
    return f"{config.worker_type}-{hostname}-{os.getpid()}-{uuid4().hex[:8]}"


def _publish_worker_presence(
    *,
    config: WorkerServiceConfig,
    worker_id: str,
    started_at: str,
    status: str,
    processed_total: int,
    wakeups_seen: int,
    last_job_id: str | None,
    last_job_type: str | None,
    last_event_type: str | None,
    active_job_count: int,
) -> None:
    write_worker_heartbeat(
        redis_url=config.redis_url,
        worker_id=worker_id,
        worker_name=config.worker_name,
        worker_type=config.worker_type,
        status=status,
        redis_listener_enabled=config.enable_redis_listener,
        started_at=started_at,
        processed_total=processed_total,
        wakeups_seen=wakeups_seen,
        last_job_id=last_job_id,
        last_job_type=last_job_type,
        last_event_type=last_event_type,
        active_job_count=active_job_count,
        idle_shutdown_seconds=config.idle_shutdown_seconds,
        poll_interval_seconds=config.poll_interval_seconds,
        listen_timeout_seconds=config.listen_timeout_seconds,
    )


def _coerce_optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None

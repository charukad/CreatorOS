from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic, sleep
from typing import Protocol, TypeAlias

from apps.api.core.redis import get_redis_client
from apps.api.services.queue_events import WORKER_WAKEUP_CHANNELS
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

    try:
        while True:
            processed_jobs = process_pending_jobs(config.max_jobs_per_iteration)
            if processed_jobs > 0:
                processed_total += processed_jobs
                last_activity_at = monotonic_fn()
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
                logger.info(
                    "Worker idle shutdown reached",
                    extra={"worker_type": config.worker_type, "processed_total": processed_total},
                )
                return processed_total

            if listener is None:
                sleep_fn(config.poll_interval_seconds)
                continue

            wake_event = listener.wait_for_wakeup(config.listen_timeout_seconds)
            if wake_event is not None:
                last_activity_at = monotonic_fn()
    finally:
        if listener is not None:
            listener.close()


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

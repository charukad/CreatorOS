import logging

from workers.service_loop import (
    WorkerServiceConfig,
    _parse_job_event_message,
    run_worker_service,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeWakeListener:
    def __init__(self, clock: FakeClock, events: list[dict[str, object] | None]) -> None:
        self._clock = clock
        self._events = list(events)
        self.closed = False
        self.wait_calls: list[float] = []

    def wait_for_wakeup(self, timeout_seconds: float) -> dict[str, object] | None:
        self.wait_calls.append(timeout_seconds)
        self._clock.sleep(timeout_seconds)
        if not self._events:
            return None
        return self._events.pop(0)

    def close(self) -> None:
        self.closed = True


def test_worker_service_processes_backlog_before_sleep_polling() -> None:
    clock = FakeClock()
    process_calls: list[int | None] = []
    results = iter([2, 0])

    def process_pending_jobs(max_jobs: int | None) -> int:
        process_calls.append(max_jobs)
        return next(results, 0)

    total_processed = run_worker_service(
        config=WorkerServiceConfig(
            worker_name="test-browser-worker",
            worker_type="browser",
            redis_url="redis://localhost:6379/0",
            enable_redis_listener=False,
            poll_interval_seconds=2.0,
            listen_timeout_seconds=1.0,
            idle_shutdown_seconds=2.0,
            max_jobs_per_iteration=5,
        ),
        logger=logging.getLogger("tests.worker_service.poll"),
        process_pending_jobs=process_pending_jobs,
        sleep_fn=clock.sleep,
        monotonic_fn=clock.monotonic,
    )

    assert total_processed == 2
    assert process_calls == [5, 5]
    assert clock.now == 2.0


def test_worker_service_reacts_to_listener_wakeup_events() -> None:
    clock = FakeClock()
    listener = FakeWakeListener(
        clock,
        events=[
            {"event_type": "job_queued", "background_job_id": "job-1"},
            None,
            None,
        ],
    )
    process_calls: list[int | None] = []
    results = iter([0, 3, 0, 0])

    def process_pending_jobs(max_jobs: int | None) -> int:
        process_calls.append(max_jobs)
        return next(results, 0)

    total_processed = run_worker_service(
        config=WorkerServiceConfig(
            worker_name="test-publisher-worker",
            worker_type="publisher",
            redis_url="redis://localhost:6379/0",
            enable_redis_listener=True,
            poll_interval_seconds=1.0,
            listen_timeout_seconds=1.0,
            idle_shutdown_seconds=2.0,
            max_jobs_per_iteration=10,
        ),
        logger=logging.getLogger("tests.worker_service.listener"),
        process_pending_jobs=process_pending_jobs,
        listener_factory=lambda _config, _logger: listener,
        sleep_fn=clock.sleep,
        monotonic_fn=clock.monotonic,
    )

    assert total_processed == 3
    assert process_calls == [10, 10, 10, 10]
    assert listener.wait_calls == [1.0, 1.0, 1.0]
    assert listener.closed is True


def test_parse_job_event_message_ignores_invalid_payloads() -> None:
    assert _parse_job_event_message({"type": "message", "data": "not-json"}) is None
    assert _parse_job_event_message({"type": "subscribe", "data": "{}"}) is None
    message = {
        "type": "message",
        "data": "{\"event_type\":\"job_queued\"}",
    }
    assert _parse_job_event_message(message) == {
        "event_type": "job_queued"
    }


def test_worker_service_writes_heartbeat_lifecycle(monkeypatch) -> None:
    clock = FakeClock()
    heartbeat_statuses: list[str] = []
    cleared_worker_ids: list[str] = []

    monkeypatch.setattr(
        "workers.service_loop.write_worker_heartbeat",
        lambda **payload: heartbeat_statuses.append(str(payload["status"])) or True,
    )
    monkeypatch.setattr(
        "workers.service_loop.clear_worker_heartbeat",
        lambda **payload: cleared_worker_ids.append(str(payload["worker_id"])) or True,
    )

    results = iter([1, 0])
    total_processed = run_worker_service(
        config=WorkerServiceConfig(
            worker_name="test-browser-worker",
            worker_type="browser",
            redis_url="redis://localhost:6379/0",
            enable_redis_listener=False,
            poll_interval_seconds=1.0,
            listen_timeout_seconds=1.0,
            idle_shutdown_seconds=1.0,
            max_jobs_per_iteration=10,
        ),
        logger=logging.getLogger("tests.worker_service.heartbeat"),
        process_pending_jobs=lambda _max_jobs: next(results, 0),
        sleep_fn=clock.sleep,
        monotonic_fn=clock.monotonic,
    )

    assert total_processed == 1
    assert heartbeat_statuses == [
        "starting",
        "processing",
        "polling",
        "idle_shutdown",
        "stopping",
    ]
    assert len(cleared_worker_ids) == 1
    assert cleared_worker_ids[0].startswith("browser-")

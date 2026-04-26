import json
from collections.abc import Iterator
from uuid import uuid4

from apps.api.main import app
from apps.api.services.job_events import build_background_job_events_stream
from fastapi.testclient import TestClient


class FakePubSub:
    def __init__(self, messages: list[dict[str, object] | None]) -> None:
        self._messages: Iterator[dict[str, object] | None] = iter(messages)
        self.channels: tuple[str, ...] = ()
        self.closed = False

    def subscribe(self, *channels: str) -> None:
        self.channels = channels

    def get_message(
        self,
        *,
        ignore_subscribe_messages: bool = True,
        timeout: float = 0.0,
    ) -> dict[str, object] | None:
        return next(self._messages, None)

    def close(self) -> None:
        self.closed = True


class FakeRedisClient:
    def __init__(self, pubsub: FakePubSub) -> None:
        self._pubsub = pubsub

    def pubsub(self) -> FakePubSub:
        return self._pubsub


def test_background_job_events_stream_filters_matching_project_and_job(monkeypatch) -> None:
    matching_project_id = uuid4()
    matching_job_id = uuid4()
    pubsub = FakePubSub(
        [
            {
                "type": "message",
                "data": json.dumps(
                    {
                        "background_job_id": str(uuid4()),
                        "event_type": "job_progress_updated",
                        "project_id": str(uuid4()),
                    }
                ),
            },
            {
                "type": "message",
                "data": json.dumps(
                    {
                        "background_job_id": str(matching_job_id),
                        "event_type": "job_progress_updated",
                        "project_id": str(matching_project_id),
                        "progress_percent": 60,
                    }
                ),
            },
        ]
    )
    monkeypatch.setattr(
        "apps.api.services.job_events.get_redis_client",
        lambda _redis_url: FakeRedisClient(pubsub),
    )

    stream = build_background_job_events_stream(
        "redis://test",
        project_id=matching_project_id,
        job_id=matching_job_id,
        keepalive_seconds=30.0,
        poll_timeout_seconds=0.0,
    )

    assert "event: stream_open" in next(stream)
    assert next(stream) == "retry: 5000\n\n"
    event_chunk = next(stream)

    assert "event: job_event" in event_chunk
    assert str(matching_project_id) in event_chunk
    assert str(matching_job_id) in event_chunk

    stream.close()
    assert pubsub.channels == ("creatoros:jobs:events",)
    assert pubsub.closed is True


def test_background_job_events_stream_emits_keepalive_when_idle(monkeypatch) -> None:
    pubsub = FakePubSub([None])
    monotonic_values = iter([0.0, 20.0])
    monkeypatch.setattr(
        "apps.api.services.job_events.get_redis_client",
        lambda _redis_url: FakeRedisClient(pubsub),
    )

    stream = build_background_job_events_stream(
        "redis://test",
        keepalive_seconds=10.0,
        poll_timeout_seconds=0.0,
        monotonic_fn=lambda: next(monotonic_values),
    )

    assert "event: stream_open" in next(stream)
    assert next(stream) == "retry: 5000\n\n"
    keepalive_chunk = next(stream)

    assert "event: keepalive" in keepalive_chunk
    stream.close()
    assert pubsub.closed is True


def test_background_job_events_route_returns_event_stream(monkeypatch) -> None:
    def fake_stream(*_args, **_kwargs):
        yield 'event: job_event\ndata: {"background_job_id": "job-1"}\n\n'

    monkeypatch.setattr(
        "apps.api.routes.job_events.build_background_job_events_stream",
        fake_stream,
    )

    client = TestClient(app)
    response = client.get("/api/events/background-jobs/stream")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert "event: job_event" in response.text

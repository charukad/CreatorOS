import json
import logging
from datetime import date, datetime
from functools import lru_cache
from time import monotonic
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from apps.api.core.config import get_settings
from apps.api.core.redaction import redact_sensitive_value

logger = logging.getLogger("apps.api.redis")

RECENT_FAILURE_TTL_SECONDS = 5.0
_recent_failure_times: dict[str, float] = {}


@lru_cache(maxsize=8)
def _build_redis_client(redis_url: str) -> Redis:
    return Redis.from_url(
        redis_url,
        decode_responses=True,
        health_check_interval=30,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )


def get_redis_client(redis_url: str | None = None) -> Redis:
    resolved_url = redis_url or get_settings().redis_url
    return _build_redis_client(resolved_url)


def get_redis_connection_status(redis_url: str | None = None) -> str:
    resolved_url = redis_url or get_settings().redis_url
    safe_url = redact_sensitive_value(resolved_url)

    try:
        if get_redis_client(resolved_url).ping():
            _recent_failure_times.pop(resolved_url, None)
            return f"reachable ({safe_url})"
    except (OSError, RedisError) as error:
        _recent_failure_times[resolved_url] = monotonic()
        return f"unavailable: {error.__class__.__name__} ({safe_url})"

    return f"unavailable: ping_failed ({safe_url})"


def publish_json(channel: str, payload: dict[str, object], *, redis_url: str | None = None) -> bool:
    resolved_url = redis_url or get_settings().redis_url
    safe_url = redact_sensitive_value(resolved_url)
    failed_at = _recent_failure_times.get(resolved_url)
    if failed_at is not None and (monotonic() - failed_at) < RECENT_FAILURE_TTL_SECONDS:
        return False

    try:
        get_redis_client(resolved_url).publish(channel, json.dumps(payload, default=_json_default))
    except (OSError, RedisError) as error:
        _recent_failure_times[resolved_url] = monotonic()
        logger.warning(
            "Redis publish failed",
            extra={
                "channel": channel,
                "error_type": error.__class__.__name__,
                "redis_url": safe_url,
            },
        )
        return False

    _recent_failure_times.pop(resolved_url, None)
    return True


def _json_default(value: Any) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)

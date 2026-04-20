import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from apps.api.core.redaction import redact_secrets, redact_sensitive_value

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
_BASE_LOG_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__)


class JsonLogFormatter(logging.Formatter):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "service": self.service_name,
            "message": redact_sensitive_value(record.getMessage()),
        }

        request_id = get_request_id()
        if request_id is not None:
            payload["request_id"] = request_id

        for key, value in record.__dict__.items():
            if key in _BASE_LOG_RECORD_KEYS or key.startswith("_"):
                continue
            payload[key] = redact_secrets(value)

        if record.exc_info is not None:
            payload["exception"] = redact_sensitive_value(self.formatException(record.exc_info))

        return json.dumps(payload, default=str, sort_keys=True)


def set_request_id(request_id: str) -> Token[str | None]:
    return request_id_context.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    request_id_context.reset(token)


def get_request_id() -> str | None:
    return request_id_context.get()


def configure_logging(service_name: str = "api", level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter(service_name=service_name))
    logging.basicConfig(
        level=level,
        handlers=[handler],
        force=True,
    )

import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "cookie",
    "key",
    "password",
    "refresh_token",
    "secret",
    "session",
    "token",
}
SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"\b(password|passwd|token|secret|api[_-]?key|cookie|session)=([^&\s,]+)",
    flags=re.IGNORECASE,
)
REDACTION_TEXT = "[redacted]"


def redact_url_credentials(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme == "" or parsed.netloc == "":
        return value

    netloc = parsed.netloc
    if "@" in netloc:
        netloc = f"{REDACTION_TEXT}@{netloc.rsplit('@', 1)[1]}"

    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    redacted_query_items = [
        (key, REDACTION_TEXT if key.lower() in SENSITIVE_QUERY_KEYS else item_value)
        for key, item_value in query_items
    ]
    query = urlencode(redacted_query_items)
    return urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))


def redact_sensitive_value(value: str) -> str:
    redacted = redact_url_credentials(value)
    return SENSITIVE_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}={REDACTION_TEXT}",
        redacted,
    )


def redact_secrets(value: Any) -> Any:
    if isinstance(value, str):
        return redact_sensitive_value(value)
    if isinstance(value, Mapping):
        return {key: redact_secrets(item_value) for key, item_value in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [redact_secrets(item_value) for item_value in value]
    return value

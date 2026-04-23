from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from apps.api.core.redaction import redact_secrets, redact_sensitive_value
from apps.api.schemas.enums import ProviderName

from workers.browser.config import BrowserWorkerSettings
from workers.browser.selectors import SelectorBundle

_MANUAL_INTERVENTION_PATTERNS = {
    "authentication": (
        "login",
        "log in",
        "sign in",
        "reauth",
        "session expired",
        "not authenticated",
        "authentication",
        "unauthorized",
        "403",
    ),
    "captcha": (
        "captcha",
        "verify you are human",
        "verify you're human",
        "challenge",
        "robot",
    ),
    "verification": (
        "2fa",
        "two factor",
        "verification code",
        "approve sign in",
        "otp",
        "confirm your identity",
    ),
    "workspace_access": (
        "workspace unavailable",
        "subscription expired",
        "plan limit",
        "access denied",
        "manual intervention",
    ),
}
_PROFILE_NAMES = {
    ProviderName.ELEVENLABS_WEB: ("ElevenLabs", "elevenlabs", "elevenlabs_profile_name"),
    ProviderName.FLOW_WEB: ("Flow", "flow", "flow_profile_name"),
}


@dataclass(frozen=True, slots=True)
class BrowserSessionDescriptor:
    provider_name: ProviderName
    provider_label: str
    storage_slug: str
    workspace_label: str
    profile_name: str
    profile_path: Path
    debug_root: Path
    selector_version: str


class BrowserManualInterventionRequired(RuntimeError):
    def __init__(self, reason: str, *, category: str) -> None:
        super().__init__(reason)
        self.category = category

    @property
    def reason(self) -> str:
        return str(self)


def build_session_descriptor(
    settings: BrowserWorkerSettings,
    provider_name: ProviderName,
    selector_bundle: SelectorBundle,
) -> BrowserSessionDescriptor:
    try:
        provider_label, storage_slug, profile_attribute = _PROFILE_NAMES[provider_name]
    except KeyError as error:
        raise ValueError(f"Unsupported browser provider session: {provider_name.value}") from error

    profile_name = str(getattr(settings, profile_attribute))
    profile_path = settings.playwright_profile_root / profile_name
    profile_path.mkdir(parents=True, exist_ok=True)

    debug_root = settings.playwright_download_root / "debug" / storage_slug
    debug_root.mkdir(parents=True, exist_ok=True)

    return BrowserSessionDescriptor(
        provider_name=provider_name,
        provider_label=provider_label,
        storage_slug=storage_slug,
        workspace_label=selector_bundle.workspace_label,
        profile_name=profile_name,
        profile_path=profile_path,
        debug_root=debug_root,
        selector_version=selector_bundle.version,
    )


def classify_manual_intervention_error(
    error: Exception,
) -> BrowserManualInterventionRequired | None:
    if isinstance(error, BrowserManualInterventionRequired):
        return BrowserManualInterventionRequired(
            sanitize_browser_message(error.reason),
            category=error.category,
        )

    message = str(error).lower()
    for category, patterns in _MANUAL_INTERVENTION_PATTERNS.items():
        if any(pattern in message for pattern in patterns):
            return BrowserManualInterventionRequired(
                sanitize_browser_message(str(error)),
                category=category,
            )
    return None


def sanitize_browser_message(message: str) -> str:
    return redact_sensitive_value(message)


def sanitize_browser_metadata(metadata: dict[str, object] | None) -> dict[str, object]:
    if metadata is None:
        return {}
    sanitized = redact_secrets(metadata)
    return sanitized if isinstance(sanitized, dict) else {}

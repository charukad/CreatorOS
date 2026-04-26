from collections.abc import Sequence
from pathlib import Path

DEVELOPMENT_ENV_NAMES = {"", "dev", "development"}
TEST_ENV_NAMES = {"ci", "test", "testing"}
PRODUCTION_ENV_NAMES = {"prod", "production"}
LOCAL_PRODUCTION_ENV_NAMES = {"local-production", "localprod"}
UNSAFE_SECRET_KEYS = {"", "dev-secret-key", "replace-me", "changeme", "change-me"}


def normalize_app_env(app_env: str) -> str:
    value = app_env.strip().lower()
    if value in DEVELOPMENT_ENV_NAMES:
        return "development"
    if value in TEST_ENV_NAMES:
        return "testing"
    if value in PRODUCTION_ENV_NAMES:
        return "production"
    if value in LOCAL_PRODUCTION_ENV_NAMES:
        return "localprod"
    return value or "development"


def is_production_like(app_env: str) -> bool:
    return normalize_app_env(app_env) in {"production", "localprod"}


def validate_non_empty_path(value: Path, setting_name: str) -> None:
    if str(value).strip() == "":
        raise ValueError(f"{setting_name} must not be empty.")


def validate_distinct_paths(first: Path, first_name: str, second: Path, second_name: str) -> None:
    if first.expanduser() == second.expanduser():
        raise ValueError(f"{first_name} and {second_name} must be different paths.")


def validate_secret_key(app_env: str, secret_key: str) -> None:
    if is_production_like(app_env) and secret_key.strip() in UNSAFE_SECRET_KEYS:
        raise ValueError("SECRET_KEY must be set to a non-default value in production.")


def resolve_path_within_roots(
    value: Path,
    *,
    allowed_roots: Sequence[Path],
    path_name: str,
    must_exist: bool = False,
) -> Path:
    resolved_value = value.expanduser().resolve()
    resolved_roots = [root.expanduser().resolve() for root in allowed_roots]

    if not any(resolved_value.is_relative_to(root) for root in resolved_roots):
        formatted_roots = ", ".join(str(root) for root in resolved_roots)
        raise ValueError(f"{path_name} must stay within configured roots: {formatted_roots}.")

    if must_exist and not resolved_value.exists():
        raise FileNotFoundError(f"{path_name} does not exist on disk: {resolved_value}")

    return resolved_value

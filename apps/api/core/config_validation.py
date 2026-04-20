from pathlib import Path

PRODUCTION_ENV_NAMES = {"prod", "production"}
UNSAFE_SECRET_KEYS = {"", "dev-secret-key", "replace-me", "changeme", "change-me"}


def is_production_like(app_env: str) -> bool:
    return app_env.strip().lower() in PRODUCTION_ENV_NAMES


def validate_non_empty_path(value: Path, setting_name: str) -> None:
    if str(value).strip() == "":
        raise ValueError(f"{setting_name} must not be empty.")


def validate_distinct_paths(first: Path, first_name: str, second: Path, second_name: str) -> None:
    if first.expanduser() == second.expanduser():
        raise ValueError(f"{first_name} and {second_name} must be different paths.")


def validate_secret_key(app_env: str, secret_key: str) -> None:
    if is_production_like(app_env) and secret_key.strip() in UNSAFE_SECRET_KEYS:
        raise ValueError("SECRET_KEY must be set to a non-default value in production.")

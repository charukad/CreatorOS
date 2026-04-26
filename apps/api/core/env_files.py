from __future__ import annotations

import os
from pathlib import Path

from apps.api.core.config_validation import normalize_app_env


def build_settings_env_files(
    service_dir: str,
    *,
    app_env: str | None = None,
) -> tuple[str, ...]:
    normalized_env = normalize_app_env(app_env or os.getenv("APP_ENV", "development"))
    service_root = Path(service_dir)
    repo_root = Path(".")
    env_file_names = (
        ".env",
        ".env.local",
        f".env.{normalized_env}",
        f".env.{normalized_env}.local",
        ".env.secrets.local",
        f".env.{normalized_env}.secrets.local",
    )

    ordered_paths: list[str] = []
    for base_dir in (service_root, repo_root):
        for file_name in env_file_names:
            candidate = str(base_dir / file_name)
            if candidate not in ordered_paths:
                ordered_paths.append(candidate)

    return tuple(ordered_paths)

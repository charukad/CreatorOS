from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class ProviderJobPayload:
    project_id: str
    scene_id: str | None = None
    prompt: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BrowserProvider(Protocol):
    def ensure_session(self) -> None: ...

    def open_workspace(self) -> None: ...

    def submit_job(self, payload: ProviderJobPayload) -> str: ...

    def wait_for_completion(self, job_id: str) -> None: ...

    def collect_downloads(self, job_id: str) -> list[str]: ...

    def capture_debug_artifacts(self, job_id: str) -> None: ...


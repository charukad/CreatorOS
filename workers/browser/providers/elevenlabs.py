from __future__ import annotations

from uuid import uuid4

from workers.browser.config import BrowserWorkerSettings
from workers.browser.playwright_runtime import PlaywrightBrowserSession, launch_provider_session
from workers.browser.providers.base import BrowserProvider, ProviderJobPayload
from workers.browser.providers.debug_artifacts import (
    capture_playwright_checkpoint_artifacts,
    capture_playwright_failure_artifacts,
    write_failure_debug_artifacts,
)
from workers.browser.providers.dry_run import DryRunElevenLabsProvider
from workers.browser.selectors import (
    ResolvedSelectorCandidate,
    SelectorBundle,
    resolve_selector_candidate,
)
from workers.browser.sessions import (
    BrowserManualInterventionRequired,
    BrowserSessionDescriptor,
)


class ElevenLabsProvider(BrowserProvider):
    def __init__(
        self,
        settings: BrowserWorkerSettings,
        *,
        selector_bundle: SelectorBundle | None,
        session_descriptor: BrowserSessionDescriptor | None,
    ) -> None:
        if settings.browser_provider_mode == "dry_run":
            self._provider: BrowserProvider = DryRunElevenLabsProvider(
                settings.playwright_download_root
            )
        else:
            if selector_bundle is None or session_descriptor is None:
                raise ValueError("Playwright ElevenLabs provider requires selector/session data.")
            self._provider = _PlaywrightElevenLabsProvider(
                settings,
                selector_bundle=selector_bundle,
                session_descriptor=session_descriptor,
            )

    def ensure_session(self) -> None:
        self._provider.ensure_session()

    def open_workspace(self) -> None:
        self._provider.open_workspace()

    def submit_job(self, payload: ProviderJobPayload) -> str:
        return self._provider.submit_job(payload)

    def wait_for_completion(self, job_id: str) -> None:
        self._provider.wait_for_completion(job_id)

    def collect_downloads(self, job_id: str) -> list[str]:
        return self._provider.collect_downloads(job_id)

    def capture_debug_artifacts(self, job_id: str) -> list[str]:
        return self._provider.capture_debug_artifacts(job_id)

    def capture_failure_artifacts(self, job_id: str | None, error: Exception) -> list[str]:
        return self._provider.capture_failure_artifacts(job_id, error)


class _PlaywrightElevenLabsProvider(BrowserProvider):
    def __init__(
        self,
        settings: BrowserWorkerSettings,
        *,
        selector_bundle: SelectorBundle,
        session_descriptor: BrowserSessionDescriptor,
    ) -> None:
        self._settings = settings
        self._selector_bundle = selector_bundle
        self._session_descriptor = session_descriptor
        self._session: PlaywrightBrowserSession | None = None
        self._submitted_jobs: dict[str, ProviderJobPayload] = {}
        self._selector_resolutions: dict[str, ResolvedSelectorCandidate] = {}

    def ensure_session(self) -> None:
        if self._session is not None:
            return
        self._session = launch_provider_session(
            self._settings,
            self._session_descriptor,
            start_url=self._settings.elevenlabs_workspace_url,
        )

    def open_workspace(self) -> None:
        page = self._page()
        page.goto(self._workspace_url(), wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        if self._has_selector("auth_gate"):
            raise BrowserManualInterventionRequired(
                "ElevenLabs login or verification is required before narration generation "
                "can continue.",
                category="authentication",
            )
        self._resolve("workspace_shell")

    def submit_job(self, payload: ProviderJobPayload) -> str:
        page = self._page()
        self._fill("narration_input", payload.prompt or "")
        voice_label = str(payload.metadata.get("voice_label") or "").strip()
        if voice_label:
            self._click("voice_picker")
            page.get_by_text(voice_label, exact=False).click()
        self._click("generate_button")
        job_id = f"elevenlabs-{uuid4()}"
        self._submitted_jobs[job_id] = payload
        return job_id

    def wait_for_completion(self, job_id: str) -> None:
        del job_id
        self._resolve("download_button")

    def collect_downloads(self, job_id: str) -> list[str]:
        page = self._page()
        selector = self._resolve("download_button").candidate
        with page.expect_download(
            timeout=self._settings.playwright_download_timeout_ms
        ) as download_info:
            page.locator(selector).first.click()
        download = download_info.value
        destination_path = self._session.download_dir / _suggested_file_name(
            download,
            f"{job_id}.wav",
        )
        download.save_as(str(destination_path))
        return [str(destination_path)]

    def capture_debug_artifacts(self, job_id: str) -> list[str]:
        if self._session is None:
            return []
        return capture_playwright_checkpoint_artifacts(
            self._session.page,
            self._session_descriptor.debug_root,
            checkpoint_name="provider-debug",
            provider_job_id=job_id,
        )

    def capture_failure_artifacts(self, job_id: str | None, error: Exception) -> list[str]:
        if self._session is None:
            return write_failure_debug_artifacts(
                self._session_descriptor.debug_root,
                provider_job_id=job_id,
                error=error,
            )
        return capture_playwright_failure_artifacts(
            self._session.page,
            self._session_descriptor.debug_root,
            provider_job_id=job_id,
            error=error,
        )

    def _page(self):
        self.ensure_session()
        assert self._session is not None
        return self._session.page

    def _workspace_url(self) -> str:
        url = (self._settings.elevenlabs_workspace_url or "").strip()
        if not url:
            raise ValueError("ELEVENLABS_WORKSPACE_URL must be configured for playwright mode.")
        return url

    def _has_selector(self, key: str) -> bool:
        page = self._page()
        try:
            resolve_selector_candidate(
                self._selector_bundle,
                key,
                predicate=lambda candidate: page.locator(candidate).count() > 0,
            )
        except LookupError:
            return False
        return True

    def _resolve(self, key: str) -> ResolvedSelectorCandidate:
        resolution = resolve_selector_candidate(
            self._selector_bundle,
            key,
            predicate=lambda candidate: self._page().locator(candidate).count() > 0,
        )
        self._selector_resolutions[key] = resolution
        return resolution

    def _click(self, key: str) -> None:
        selector = self._resolve(key).candidate
        self._page().locator(selector).first.click()

    def _fill(self, key: str, value: str) -> None:
        selector = self._resolve(key).candidate
        self._page().locator(selector).first.fill(value)


def _suggested_file_name(download, fallback_name: str) -> str:
    suggested_name = getattr(download, "suggested_filename", None)
    if isinstance(suggested_name, str) and suggested_name.strip():
        return suggested_name
    return fallback_name

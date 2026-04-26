from pathlib import Path

import pytest
from apps.api.schemas.enums import ProviderName
from workers.browser.config import BrowserWorkerSettings
from workers.browser.playwright_runtime import launch_provider_session
from workers.browser.providers import FlowProvider, ProviderJobPayload
from workers.browser.providers.elevenlabs import ElevenLabsProvider
from workers.browser.selectors import load_selector_bundle, resolve_selector_candidate
from workers.browser.sessions import BrowserManualInterventionRequired, build_session_descriptor


class FakeLocator:
    def __init__(self, page: "FakePage", selector: str) -> None:
        self._page = page
        self._selector = selector

    @property
    def first(self) -> "FakeLocator":
        return self

    def count(self) -> int:
        return 1 if self._selector in self._page.available_selectors else 0

    def click(self) -> None:
        self._page.clicked.append(self._selector)

    def fill(self, value: str) -> None:
        self._page.fills.append((self._selector, value))


class FakeTextLocator:
    def __init__(self, page: "FakePage", text: str, *, exact: bool) -> None:
        self._page = page
        self._text = text
        self._exact = exact

    def click(self) -> None:
        self._page.text_clicks.append((self._text, self._exact))


class FakeDownload:
    def __init__(self, *, suggested_filename: str) -> None:
        self.suggested_filename = suggested_filename
        self.saved_paths: list[str] = []

    def save_as(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text("downloaded bytes", encoding="utf-8")
        self.saved_paths.append(path)


class FakeExpectDownload:
    def __init__(self, download: FakeDownload) -> None:
        self.value = download

    def __enter__(self) -> "FakeExpectDownload":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FakePage:
    def __init__(
        self,
        *,
        available_selectors: set[str],
        download: FakeDownload | None = None,
    ) -> None:
        self.available_selectors = available_selectors
        self.download = download or FakeDownload(suggested_filename="provider-output.bin")
        self.clicked: list[str] = []
        self.fills: list[tuple[str, str]] = []
        self.text_clicks: list[tuple[str, bool]] = []
        self.goto_calls: list[tuple[str, str]] = []
        self.load_state_calls: list[str] = []
        self.default_timeout_ms: int | None = None
        self.default_navigation_timeout_ms: int | None = None

    def set_default_timeout(self, value: int) -> None:
        self.default_timeout_ms = value

    def set_default_navigation_timeout(self, value: int) -> None:
        self.default_navigation_timeout_ms = value

    def goto(self, url: str, *, wait_until: str) -> None:
        self.goto_calls.append((url, wait_until))

    def wait_for_load_state(self, value: str) -> None:
        self.load_state_calls.append(value)

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    def get_by_text(self, text: str, *, exact: bool = False) -> FakeTextLocator:
        return FakeTextLocator(self, text, exact=exact)

    def expect_download(self, *, timeout: int) -> FakeExpectDownload:
        assert timeout > 0
        return FakeExpectDownload(self.download)

    def screenshot(self, *, full_page: bool = True) -> bytes:
        del full_page
        return b"\x89PNG\r\n\x1a\n"

    def content(self) -> str:
        return "<html><body>fake page</body></html>"


class FakeContext:
    def __init__(self, page: FakePage) -> None:
        self.pages = [page]
        self.closed = False

    def new_page(self) -> FakePage:
        return self.pages[0]

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, context: FakeContext) -> None:
        self._context = context
        self.launch_kwargs: dict[str, object] | None = None

    def launch_persistent_context(self, **kwargs):
        self.launch_kwargs = kwargs
        return self._context


class FakePlaywright:
    def __init__(self, chromium: FakeChromium) -> None:
        self.chromium = chromium


class FakeManager:
    def __init__(self, playwright: FakePlaywright) -> None:
        self._playwright = playwright
        self.stopped = False

    def start(self) -> FakePlaywright:
        return self._playwright

    def stop(self) -> None:
        self.stopped = True


def test_resolve_selector_candidate_uses_first_matching_fallback() -> None:
    bundle = load_selector_bundle(ProviderName.FLOW_WEB)

    resolution = resolve_selector_candidate(
        bundle,
        "download_button",
        predicate=lambda candidate: candidate in {"a[download]", "button[type='submit']"},
    )

    assert resolution.candidate == "a[download]"
    assert resolution.candidate_index == 1


def test_launch_provider_session_uses_persistent_profile_and_download_dir(tmp_path: Path) -> None:
    settings = BrowserWorkerSettings(
        BROWSER_PROVIDER_MODE="playwright",
        PLAYWRIGHT_PROFILE_ROOT=tmp_path / "profiles",
        PLAYWRIGHT_DOWNLOAD_ROOT=tmp_path / "downloads",
    )
    bundle = load_selector_bundle(ProviderName.ELEVENLABS_WEB)
    descriptor = build_session_descriptor(settings, ProviderName.ELEVENLABS_WEB, bundle)
    page = FakePage(available_selectors={"main"})
    context = FakeContext(page)
    chromium = FakeChromium(context)
    manager = FakeManager(FakePlaywright(chromium))

    session = launch_provider_session(
        settings,
        descriptor,
        start_url="https://example.com/workspace",
        sync_playwright_factory=lambda: manager,
    )

    assert chromium.launch_kwargs is not None
    assert chromium.launch_kwargs["user_data_dir"] == str(descriptor.profile_path)
    assert chromium.launch_kwargs["downloads_path"] == str(session.download_dir)
    assert chromium.launch_kwargs["accept_downloads"] is True
    assert page.default_timeout_ms == settings.playwright_action_timeout_ms
    assert page.default_navigation_timeout_ms == settings.playwright_navigation_timeout_ms
    assert page.goto_calls == [("https://example.com/workspace", "domcontentloaded")]

    session.close()
    assert context.closed is True
    assert manager.stopped is True


def test_elevenlabs_playwright_provider_requests_manual_intervention_on_auth_gate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = BrowserWorkerSettings(
        BROWSER_PROVIDER_MODE="playwright",
        PLAYWRIGHT_PROFILE_ROOT=tmp_path / "profiles",
        PLAYWRIGHT_DOWNLOAD_ROOT=tmp_path / "downloads",
    )
    bundle = load_selector_bundle(ProviderName.ELEVENLABS_WEB)
    descriptor = build_session_descriptor(settings, ProviderName.ELEVENLABS_WEB, bundle)
    page = FakePage(available_selectors={"text=/log in/i"})
    context = FakeContext(page)

    monkeypatch.setattr(
        "workers.browser.providers.elevenlabs.launch_provider_session",
        lambda settings, descriptor, start_url=None: type(
            "Session",
            (),
            {
                "context": context,
                "page": page,
                "download_dir": tmp_path / "downloads" / "elevenlabs",
            },
        )(),
    )

    provider = ElevenLabsProvider(
        settings,
        selector_bundle=bundle,
        session_descriptor=descriptor,
    )

    provider.ensure_session()
    with pytest.raises(BrowserManualInterventionRequired, match="ElevenLabs login"):
        provider.open_workspace()


def test_flow_playwright_provider_uses_fallback_selectors_and_saves_download(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = BrowserWorkerSettings(
        BROWSER_PROVIDER_MODE="playwright",
        PLAYWRIGHT_PROFILE_ROOT=tmp_path / "profiles",
        PLAYWRIGHT_DOWNLOAD_ROOT=tmp_path / "downloads",
    )
    bundle = load_selector_bundle(ProviderName.FLOW_WEB)
    descriptor = build_session_descriptor(settings, ProviderName.FLOW_WEB, bundle)
    download = FakeDownload(suggested_filename="scene-output.png")
    page = FakePage(
        available_selectors={
            "main",
            "textarea",
            "button[type='submit']",
            "text=/completed/i",
            "a[download]",
        },
        download=download,
    )
    context = FakeContext(page)

    monkeypatch.setattr(
        "workers.browser.providers.flow.launch_provider_session",
        lambda settings, descriptor, start_url=None: type(
            "Session",
            (),
            {
                "context": context,
                "page": page,
                "download_dir": tmp_path / "downloads" / "flow",
            },
        )(),
    )

    provider = FlowProvider(
        settings,
        selector_bundle=bundle,
        session_descriptor=descriptor,
    )

    provider.ensure_session()
    provider.open_workspace()
    job_id = provider.submit_job(
        ProviderJobPayload(
            project_id="project-1",
            scene_id="scene-1",
            prompt="Create a bold product demo frame.",
        )
    )
    provider.wait_for_completion(job_id)
    download_paths = provider.collect_downloads(job_id)

    assert page.fills == [("textarea", "Create a bold product demo frame.")]
    assert "button[type='submit']" in page.clicked
    assert "a[download]" in page.clicked
    assert download_paths == [str(tmp_path / "downloads" / "flow" / "scene-output.png")]
    assert Path(download_paths[0]).exists()

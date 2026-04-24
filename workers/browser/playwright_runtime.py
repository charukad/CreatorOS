from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workers.browser.config import BrowserWorkerSettings
from workers.browser.sessions import BrowserSessionDescriptor

try:  # pragma: no cover - exercised through injected fakes in tests
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - defensive import fallback
    sync_playwright = None

PlaywrightFactory = Callable[[], Any]


@dataclass(slots=True)
class PlaywrightBrowserSession:
    manager: Any
    playwright: Any
    context: Any
    page: Any
    download_dir: Path

    def close(self) -> None:
        self.context.close()
        self.manager.stop()


def build_provider_download_dir(
    settings: BrowserWorkerSettings,
    descriptor: BrowserSessionDescriptor,
) -> Path:
    download_dir = (
        settings.playwright_download_root
        / descriptor.storage_slug
        / descriptor.profile_name
    )
    download_dir.mkdir(parents=True, exist_ok=True)
    return download_dir


def launch_provider_session(
    settings: BrowserWorkerSettings,
    descriptor: BrowserSessionDescriptor,
    *,
    start_url: str | None = None,
    sync_playwright_factory: PlaywrightFactory | None = None,
) -> PlaywrightBrowserSession:
    factory = sync_playwright_factory or sync_playwright
    if factory is None:
        raise RuntimeError(
            "Playwright is not available in this environment. "
            "Install browser dependencies before using playwright provider mode."
        )

    download_dir = build_provider_download_dir(settings, descriptor)
    manager = factory()
    playwright = manager.start()
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=str(descriptor.profile_path),
        accept_downloads=True,
        downloads_path=str(download_dir),
        headless=settings.playwright_headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.set_default_timeout(settings.playwright_action_timeout_ms)
    page.set_default_navigation_timeout(settings.playwright_navigation_timeout_ms)
    if start_url:
        page.goto(start_url, wait_until="domcontentloaded")
    return PlaywrightBrowserSession(
        manager=manager,
        playwright=playwright,
        context=context,
        page=page,
        download_dir=download_dir,
    )

import logging

from workers.browser.config import get_settings
from workers.browser.runtime import run_pending_jobs

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger.info("CreatorOS browser worker bootstrap ready")
    logger.info("Provider mode: %s", settings.browser_provider_mode)
    logger.info("Headless mode: %s", settings.playwright_headless)
    logger.info("Profile root: %s", settings.playwright_profile_root)
    logger.info("Download root: %s", settings.playwright_download_root)
    logger.info(
        "Configured profiles: elevenlabs=%s flow=%s",
        settings.elevenlabs_profile_name,
        settings.flow_profile_name,
    )
    processed_jobs = run_pending_jobs(
        settings=settings,
        max_jobs=settings.browser_max_jobs_per_run,
    )
    logger.info("Processed %s browser job(s) in this run", processed_jobs)


if __name__ == "__main__":
    main()

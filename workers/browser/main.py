import logging

from workers.browser.config import get_settings

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger.info("CreatorOS browser worker bootstrap ready")
    logger.info("Headless mode: %s", settings.playwright_headless)
    logger.info("Profile root: %s", settings.playwright_profile_root)
    logger.info("Download root: %s", settings.playwright_download_root)
    logger.info(
        "Configured profiles: elevenlabs=%s flow=%s",
        settings.elevenlabs_profile_name,
        settings.flow_profile_name,
    )


if __name__ == "__main__":
    main()

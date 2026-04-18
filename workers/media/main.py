import logging

from workers.media.config import get_settings

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger.info("CreatorOS media worker bootstrap ready")
    logger.info("Storage root: %s", settings.storage_root)
    logger.info("Downloads root: %s", settings.downloads_root)


if __name__ == "__main__":
    main()

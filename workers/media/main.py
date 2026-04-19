import logging

from workers.media.config import get_settings
from workers.media.runtime import run_pending_jobs

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger.info("CreatorOS media worker starting")
    logger.info("Storage root: %s", settings.storage_root)
    logger.info("Downloads root: %s", settings.downloads_root)
    processed_jobs = run_pending_jobs(settings=settings)
    logger.info("CreatorOS media worker finished after %s job(s)", processed_jobs)


if __name__ == "__main__":
    main()

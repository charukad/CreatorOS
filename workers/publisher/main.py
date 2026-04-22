import logging

from apps.api.core.logging import configure_logging

from workers.publisher.config import get_settings
from workers.publisher.runtime import run_pending_jobs

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(service_name="publisher-worker")
    logger.info("CreatorOS publisher worker starting")
    logger.info("Storage root: %s", settings.storage_root)
    processed_jobs = run_pending_jobs(settings=settings)
    logger.info("CreatorOS publisher worker finished after %s job(s)", processed_jobs)


if __name__ == "__main__":
    main()

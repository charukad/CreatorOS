import logging

from apps.api.core.logging import configure_logging

from workers.analytics.config import get_settings
from workers.analytics.runtime import run_pending_jobs

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(service_name="analytics-worker")
    logger.info("CreatorOS analytics worker starting")
    processed_jobs = run_pending_jobs(settings=settings)
    logger.info("CreatorOS analytics worker finished after %s job(s)", processed_jobs)


if __name__ == "__main__":
    main()

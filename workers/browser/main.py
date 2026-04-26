import logging

from apps.api.core.logging import configure_logging

from workers.browser.config import get_settings
from workers.browser.runtime import run_pending_jobs
from workers.service_loop import WorkerServiceConfig, run_worker_service

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(service_name="browser-worker")
    logger.info("CreatorOS browser worker bootstrap ready")
    logger.info("Provider mode: %s", settings.browser_provider_mode)
    logger.info("Headless mode: %s", settings.playwright_headless)
    logger.info("Profile root: %s", settings.playwright_profile_root)
    logger.info("Download root: %s", settings.playwright_download_root)
    logger.info("Redis listener enabled: %s", settings.worker_enable_redis_listener)
    logger.info("Worker listen timeout: %ss", settings.worker_listen_timeout_seconds)
    logger.info("Worker poll interval: %ss", settings.worker_poll_interval_seconds)
    logger.info(
        "Configured profiles: elevenlabs=%s flow=%s",
        settings.elevenlabs_profile_name,
        settings.flow_profile_name,
    )
    processed_jobs = run_worker_service(
        config=WorkerServiceConfig(
            worker_name="browser-worker",
            worker_type="browser",
            redis_url=settings.redis_url,
            enable_redis_listener=settings.worker_enable_redis_listener,
            poll_interval_seconds=settings.worker_poll_interval_seconds,
            listen_timeout_seconds=settings.worker_listen_timeout_seconds,
            idle_shutdown_seconds=settings.worker_idle_shutdown_seconds,
            max_jobs_per_iteration=settings.browser_max_jobs_per_run,
        ),
        logger=logger,
        process_pending_jobs=lambda max_jobs: run_pending_jobs(
            settings=settings,
            max_jobs=max_jobs,
        ),
    )
    logger.info("Processed %s browser job(s) in this worker run", processed_jobs)


if __name__ == "__main__":
    main()

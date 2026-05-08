from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]

from app.core.config import get_settings
from app.db.session import create_session
from app.services.observer_service import ObserverService

_scheduler: BackgroundScheduler | None = None
logger = logging.getLogger(__name__)


def start_scheduler() -> None:
    global _scheduler
    settings = get_settings()
    if not settings.scheduler_enabled:
        return
    if settings.scheduler_instance_role.lower() != "leader":
        logger.info("scheduler_skipped_non_leader role=%s", settings.scheduler_instance_role)
        return
    if _scheduler is not None and _scheduler.running:
        return
    if settings.app_env.lower() == "production":
        logger.warning(
            "scheduler_process_local_enabled app_env=production note='run a single scheduler instance or move to a distributed worker'"
        )
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(_run_observer_job, "interval", minutes=settings.observer_interval_minutes, id="observer")
    scheduler.start()
    _scheduler = scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def _run_observer_job() -> None:
    session = create_session()
    try:
        ObserverService(session).run_all_users()
    finally:
        session.close()

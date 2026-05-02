from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.db.session import create_session
from app.services.observer_service import ObserverService

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    settings = get_settings()
    if not settings.scheduler_enabled:
        return
    if _scheduler is not None and _scheduler.running:
        return
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

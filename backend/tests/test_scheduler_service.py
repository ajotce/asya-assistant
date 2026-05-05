from __future__ import annotations

from app.services import scheduler_service


class _DummySession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _DummyObserverService:
    called = 0
    last_session = None

    def __init__(self, session) -> None:
        self._session = session
        _DummyObserverService.last_session = session

    def run_all_users(self) -> int:
        _DummyObserverService.called += 1
        return 0


def test_run_observer_job_executes_observer_and_closes_session(monkeypatch) -> None:
    dummy_session = _DummySession()

    monkeypatch.setattr(scheduler_service, "create_session", lambda: dummy_session)
    monkeypatch.setattr(scheduler_service, "ObserverService", _DummyObserverService)

    scheduler_service._run_observer_job()

    assert _DummyObserverService.called == 1
    assert _DummyObserverService.last_session is dummy_session
    assert dummy_session.closed is True

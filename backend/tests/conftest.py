import pytest


@pytest.fixture(autouse=True)
def _default_registration_mode_open_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    # Keep legacy test suite behavior: email/password signup stays open unless a test overrides it.
    monkeypatch.setenv("REGISTRATION_MODE", "open")

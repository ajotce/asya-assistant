from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.core.config import Settings
from app.services.vision_service import VisionService


@dataclass
class _FakeResponse:
    payload: dict[str, Any]

    def raise_for_status(self) -> None:
        return

    def json(self) -> dict[str, Any]:
        return self.payload


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        VSELLM_API_KEY="test-key",
        VSELLM_BASE_URL="https://example.test/v1",
        VSELLM_VISION_MODEL="vision-model",
    )


def test_extract_vin_valid_and_high_confidence(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    def _post(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse({"value": "1HGCM82633A004352", "confidence": 0.92})

    monkeypatch.setattr("app.services.vision_service.httpx.post", _post)
    service = VisionService(settings)

    result = service.extract_vin(b"img")
    assert result.value == "1HGCM82633A004352"
    assert result.valid is True
    assert result.needs_confirmation is False


def test_extract_passport_low_confidence_requires_confirmation(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    def _post(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse({"value": "1234 567890", "confidence": 0.7})

    monkeypatch.setattr("app.services.vision_service.httpx.post", _post)
    service = VisionService(settings)

    result = service.extract_passport_number(b"img")
    assert result.value == "1234 567890"
    assert result.valid is True
    assert result.needs_confirmation is True


def test_extract_vin_invalid_check_digit(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    def _post(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse({"value": "XTA210990Y1234568", "confidence": 0.95})

    monkeypatch.setattr("app.services.vision_service.httpx.post", _post)
    service = VisionService(settings)

    result = service.extract_vin(b"img")
    assert result.valid is False

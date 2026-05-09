from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from app.core.config import Settings


@dataclass
class VisionExtractionResult:
    value: str
    confidence: float
    valid: bool
    needs_confirmation: bool


class VisionService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def extract_vin(self, image_bytes: bytes) -> VisionExtractionResult:
        result = self._extract(image_bytes=image_bytes, task="vin")
        value = self._normalize_vin(result.value)
        valid = self._is_valid_vin(value)
        return VisionExtractionResult(
            value=value,
            confidence=result.confidence,
            valid=valid,
            needs_confirmation=result.confidence < 0.85,
        )

    def extract_passport_number(self, image_bytes: bytes) -> VisionExtractionResult:
        result = self._extract(image_bytes=image_bytes, task="passport_number")
        value = self._normalize_passport_number(result.value)
        valid = self._is_valid_passport_number(value)
        return VisionExtractionResult(
            value=value,
            confidence=result.confidence,
            valid=valid,
            needs_confirmation=result.confidence < 0.85,
        )

    def _extract(self, image_bytes: bytes, task: str) -> VisionExtractionResult:
        if not self._settings.vsellm_api_key.strip():
            raise RuntimeError("VseLLM API key is not configured")
        model = self._settings.vsellm_vision_model.strip() or self._settings.default_chat_model.strip()
        if not model:
            raise RuntimeError("Vision model is not configured")

        headers = {"Authorization": f"Bearer {self._settings.vsellm_api_key.strip()}"}
        files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
        data = {
            "model": model,
            "task": task,
            "response_format": "json",
        }

        response = httpx.post(
            f"{self._settings.vsellm_base_url.rstrip('/')}/vision/extract",
            headers=headers,
            data=data,
            files=files,
            timeout=httpx.Timeout(timeout=self._settings.vsellm_vision_timeout_seconds, connect=10.0),
        )
        response.raise_for_status()
        payload = response.json()

        value = str(payload.get("value", "")).strip()
        confidence_raw = payload.get("confidence", 0.0)
        confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float, str)) else 0.0
        confidence = max(0.0, min(1.0, confidence))

        return VisionExtractionResult(
            value=value,
            confidence=confidence,
            valid=False,
            needs_confirmation=confidence < 0.85,
        )

    @staticmethod
    def _normalize_vin(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9]", "", value).upper()

    @staticmethod
    def _normalize_passport_number(value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) >= 10:
            return f"{digits[:4]} {digits[4:10]}"
        return digits

    @staticmethod
    def _is_valid_passport_number(value: str) -> bool:
        return bool(re.fullmatch(r"\d{4}\s\d{6}", value))

    @staticmethod
    def _is_valid_vin(value: str) -> bool:
        if not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", value):
            return False
        return VisionService._vin_check_digit_ok(value)

    @staticmethod
    def _vin_check_digit_ok(vin: str) -> bool:
        translit = {
            "A": 1,
            "B": 2,
            "C": 3,
            "D": 4,
            "E": 5,
            "F": 6,
            "G": 7,
            "H": 8,
            "J": 1,
            "K": 2,
            "L": 3,
            "M": 4,
            "N": 5,
            "P": 7,
            "R": 9,
            "S": 2,
            "T": 3,
            "U": 4,
            "V": 5,
            "W": 6,
            "X": 7,
            "Y": 8,
            "Z": 9,
        }
        weights = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

        total = 0
        for i, ch in enumerate(vin):
            if ch.isdigit():
                val = int(ch)
            else:
                val = translit.get(ch)
                if val is None:
                    return False
            total += val * weights[i]

        check = total % 11
        expected = "X" if check == 10 else str(check)
        return vin[8] == expected

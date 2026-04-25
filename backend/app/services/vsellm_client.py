from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings
from app.models.schemas import ModelInfo


@dataclass
class VseLLMError(Exception):
    status_code: int
    user_message: str


class VseLLMClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_models(self) -> list[ModelInfo]:
        api_key = self._settings.vsellm_api_key.strip()
        if not api_key:
            raise VseLLMError(status_code=503, user_message="VseLLM API-ключ не настроен на backend.")

        base_url = self._settings.vsellm_base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            response = httpx.get(
                f"{base_url}/models",
                headers=headers,
                timeout=httpx.Timeout(timeout=20.0, connect=10.0),
            )
        except httpx.TimeoutException as exc:
            raise VseLLMError(status_code=504, user_message="VseLLM не ответил вовремя. Попробуйте позже.") from exc
        except httpx.RequestError as exc:
            raise VseLLMError(
                status_code=502,
                user_message="Не удалось подключиться к VseLLM. Проверьте сеть и base URL.",
            ) from exc

        if response.status_code in (401, 403):
            raise VseLLMError(
                status_code=response.status_code,
                user_message="Ошибка авторизации VseLLM. Проверьте API-ключ на backend.",
            )
        if response.status_code == 404:
            raise VseLLMError(
                status_code=502,
                user_message="Эндпоинт моделей VseLLM не найден. Проверьте VSELLM_BASE_URL.",
            )
        if response.status_code == 429:
            raise VseLLMError(
                status_code=429,
                user_message="Сервис VseLLM временно ограничил частоту запросов. Попробуйте позже.",
            )
        if response.status_code >= 500:
            raise VseLLMError(
                status_code=502,
                user_message="Сервис VseLLM временно недоступен. Попробуйте позже.",
            )
        if response.status_code >= 400:
            raise VseLLMError(
                status_code=502,
                user_message="Не удалось получить список моделей из VseLLM.",
            )

        payload = response.json()
        raw_models: Any = payload.get("data", payload)
        if not isinstance(raw_models, list):
            raise VseLLMError(status_code=502, user_message="Некорректный формат ответа VseLLM для списка моделей.")

        models: list[ModelInfo] = []
        for item in raw_models:
            normalized = self._normalize_model(item)
            if normalized is not None:
                models.append(normalized)
        return models

    @staticmethod
    def _normalize_model(item: Any) -> ModelInfo | None:
        if isinstance(item, str):
            return ModelInfo(id=item)
        if not isinstance(item, dict):
            return None

        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            return None

        return ModelInfo(
            id=model_id,
            name=item.get("name") if isinstance(item.get("name"), str) else None,
            description=item.get("description") if isinstance(item.get("description"), str) else None,
            context_window=item.get("context_window") if isinstance(item.get("context_window"), int) else None,
            input_price=float(item["input_price"]) if isinstance(item.get("input_price"), (int, float)) else None,
            output_price=float(item["output_price"]) if isinstance(item.get("output_price"), (int, float)) else None,
            supports_vision=item.get("supports_vision") if isinstance(item.get("supports_vision"), bool) else None,
        )

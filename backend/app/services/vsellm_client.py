from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

import httpx

from app.core.config import Settings
from app.models.schemas import ModelInfo


@dataclass
class VseLLMError(Exception):
    status_code: int
    user_message: str


@dataclass
class EmbeddingsResult:
    vectors: List[List[float]]
    usage: Optional[dict]
    model: str


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

    def get_embeddings(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        return self.get_embeddings_with_usage(texts=texts, model=model).vectors

    def get_embeddings_with_usage(self, texts: List[str], model: Optional[str] = None) -> EmbeddingsResult:
        api_key = self._settings.vsellm_api_key.strip()
        if not api_key:
            raise VseLLMError(status_code=503, user_message="VseLLM API-ключ не настроен на backend.")
        cleaned = [text.strip() for text in texts if text and text.strip()]
        if not cleaned:
            raise VseLLMError(status_code=400, user_message="Не удалось подготовить текст для embeddings.")

        embedding_model = (model or self._settings.default_embedding_model or self._settings.default_chat_model).strip()
        if not embedding_model:
            raise VseLLMError(status_code=503, user_message="Embedding-модель не настроена на backend.")

        base_url = self._settings.vsellm_base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {"model": embedding_model, "input": cleaned}

        try:
            response = httpx.post(
                f"{base_url}/embeddings",
                headers=headers,
                json=payload,
                timeout=httpx.Timeout(timeout=60.0, connect=10.0),
            )
        except httpx.TimeoutException as exc:
            raise VseLLMError(
                status_code=504,
                user_message="Сервис embeddings VseLLM не ответил вовремя. Попробуйте позже.",
            ) from exc
        except httpx.RequestError as exc:
            raise VseLLMError(
                status_code=502,
                user_message="Не удалось подключиться к embeddings API VseLLM.",
            ) from exc

        if response.status_code in (401, 403):
            raise VseLLMError(
                status_code=response.status_code,
                user_message="Ошибка авторизации VseLLM. Проверьте API-ключ на backend.",
            )
        if response.status_code == 404:
            raise VseLLMError(
                status_code=502,
                user_message="Embeddings endpoint VseLLM не найден. Проверьте настройки.",
            )
        if response.status_code == 429:
            raise VseLLMError(
                status_code=429,
                user_message="Сервис embeddings VseLLM временно ограничил запросы. Попробуйте позже.",
            )
        if response.status_code >= 500:
            raise VseLLMError(
                status_code=502,
                user_message="Сервис embeddings VseLLM временно недоступен. Попробуйте позже.",
            )
        if response.status_code >= 400:
            raise VseLLMError(status_code=502, user_message="Ошибка запроса к embeddings API VseLLM.")

        response_payload = response.json()
        raw_data = response_payload.get("data")
        if not isinstance(raw_data, list) or not raw_data:
            raise VseLLMError(status_code=502, user_message="Некорректный формат ответа embeddings API.")

        vectors: List[List[float]] = []
        for item in raw_data:
            if not isinstance(item, dict):
                raise VseLLMError(status_code=502, user_message="Некорректный элемент embeddings в ответе API.")
            vector = item.get("embedding")
            if not isinstance(vector, list) or not vector:
                raise VseLLMError(status_code=502, user_message="Embeddings API вернул пустой вектор.")
            try:
                vectors.append([float(value) for value in vector])
            except (TypeError, ValueError) as exc:
                raise VseLLMError(status_code=502, user_message="Embeddings API вернул некорректный вектор.") from exc

        if len(vectors) != len(cleaned):
            raise VseLLMError(
                status_code=502,
                user_message="Embeddings API вернул неполный набор векторов. Повторите попытку.",
            )
        usage_raw = response_payload.get("usage")
        usage = usage_raw if isinstance(usage_raw, dict) else None
        return EmbeddingsResult(vectors=vectors, usage=usage, model=embedding_model)

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

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional

import httpx

from app.core.config import Settings
from app.models.schemas import ModelInfo

_REASONING_HEURISTIC_TOKENS = ("thinking", "reasoning", "-r1", "/o3", "-o3")


def is_likely_reasoning_model(model_id: str) -> bool:
    lower = model_id.lower()
    return any(token in lower for token in _REASONING_HEURISTIC_TOKENS)


@dataclass
class VseLLMError(Exception):
    status_code: int
    user_message: str


@dataclass
class EmbeddingsResult:
    vectors: List[List[float]]
    usage: Optional[dict]
    model: str


@dataclass
class ReasoningProbeResult:
    model_id: str
    streams_reasoning: bool
    checked_at: datetime
    error: Optional[str] = None


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

        supports_chat = VseLLMClient._extract_chat_support(item)
        supports_stream = VseLLMClient._extract_stream_support(item)
        supports_vision = VseLLMClient._extract_vision_support(item)

        return ModelInfo(
            id=model_id,
            name=item.get("name") if isinstance(item.get("name"), str) else None,
            description=item.get("description") if isinstance(item.get("description"), str) else None,
            context_window=item.get("context_window") if isinstance(item.get("context_window"), int) else None,
            input_price=float(item["input_price"]) if isinstance(item.get("input_price"), (int, float)) else None,
            output_price=float(item["output_price"]) if isinstance(item.get("output_price"), (int, float)) else None,
            supports_chat=supports_chat,
            supports_stream=supports_stream,
            supports_vision=supports_vision,
        )

    @staticmethod
    def _extract_chat_support(item: dict[str, Any]) -> Optional[bool]:
        explicit = VseLLMClient._first_non_none_bool(
            VseLLMClient._to_optional_bool(item.get("supports_chat")),
            VseLLMClient._to_optional_bool(item.get("supports_chat_completions")),
            VseLLMClient._to_optional_bool(item.get("supports_chat_completion")),
            VseLLMClient._to_optional_bool(item.get("chat_completions")),
            VseLLMClient._to_optional_bool(item.get("chat_completion")),
        )
        if explicit is not None:
            return explicit

        capabilities = item.get("capabilities")
        capability_support = VseLLMClient._extract_chat_support_from_capabilities(capabilities)
        if capability_support is not None:
            return capability_support

        endpoints = item.get("endpoints")
        endpoint_support = VseLLMClient._extract_chat_support_from_endpoints(endpoints)
        if endpoint_support is not None:
            return endpoint_support

        return None

    @staticmethod
    def _extract_stream_support(item: dict[str, Any]) -> Optional[bool]:
        explicit = VseLLMClient._first_non_none_bool(
            VseLLMClient._to_optional_bool(item.get("supports_stream")),
            VseLLMClient._to_optional_bool(item.get("supports_streaming")),
            VseLLMClient._to_optional_bool(item.get("stream")),
            VseLLMClient._to_optional_bool(item.get("streaming")),
        )
        if explicit is not None:
            return explicit

        capabilities = item.get("capabilities")
        if isinstance(capabilities, dict):
            stream_support = VseLLMClient._first_non_none_bool(
                VseLLMClient._to_optional_bool(capabilities.get("stream")),
                VseLLMClient._to_optional_bool(capabilities.get("streaming")),
                VseLLMClient._to_optional_bool(capabilities.get("supports_stream")),
                VseLLMClient._to_optional_bool(capabilities.get("supports_streaming")),
            )
            if stream_support is not None:
                return stream_support
        return None

    @staticmethod
    def _extract_vision_support(item: dict[str, Any]) -> Optional[bool]:
        explicit = VseLLMClient._to_optional_bool(item.get("supports_vision"))
        if explicit is not None:
            return explicit

        capabilities = item.get("capabilities")
        if isinstance(capabilities, dict):
            vision_support = VseLLMClient._first_non_none_bool(
                VseLLMClient._to_optional_bool(capabilities.get("vision")),
                VseLLMClient._to_optional_bool(capabilities.get("image")),
                VseLLMClient._to_optional_bool(capabilities.get("image_input")),
                VseLLMClient._to_optional_bool(capabilities.get("multimodal")),
            )
            if vision_support is not None:
                return vision_support

        modalities = item.get("modalities")
        if isinstance(modalities, list):
            lowered_modalities = {str(value).strip().lower() for value in modalities}
            if {"image", "vision", "multimodal"} & lowered_modalities:
                return True
        return None

    @staticmethod
    def _extract_chat_support_from_capabilities(capabilities: Any) -> Optional[bool]:
        if isinstance(capabilities, dict):
            for key in ("chat", "chat_completions", "chat-completions", "chat_completion"):
                parsed = VseLLMClient._to_optional_bool(capabilities.get(key))
                if parsed is not None:
                    return parsed
                nested = capabilities.get(key)
                if isinstance(nested, dict):
                    nested_value = VseLLMClient._first_non_none_bool(
                        VseLLMClient._to_optional_bool(nested.get("enabled")),
                        VseLLMClient._to_optional_bool(nested.get("supported")),
                        VseLLMClient._to_optional_bool(nested.get("available")),
                    )
                    if nested_value is not None:
                        return nested_value

            for key, value in capabilities.items():
                if not isinstance(key, str):
                    continue
                lowered = key.strip().lower()
                if "chat" not in lowered:
                    continue
                parsed = VseLLMClient._to_optional_bool(value)
                if parsed is not None:
                    return parsed

        if isinstance(capabilities, list):
            lowered_caps = {str(value).strip().lower() for value in capabilities}
            if {"chat", "chat_completions", "chat-completions", "chat_completion"} & lowered_caps:
                return True
        return None

    @staticmethod
    def _extract_chat_support_from_endpoints(endpoints: Any) -> Optional[bool]:
        if isinstance(endpoints, list):
            for endpoint in endpoints:
                endpoint_text = str(endpoint).strip().lower()
                if "/chat/completions" in endpoint_text or "chat/completions" in endpoint_text:
                    return True
        if isinstance(endpoints, dict):
            for key, value in endpoints.items():
                key_text = str(key).strip().lower()
                if "/chat/completions" in key_text or "chat/completions" in key_text or key_text in {"chat", "chat_completions"}:
                    parsed = VseLLMClient._to_optional_bool(value)
                    if parsed is not None:
                        return parsed
                    if isinstance(value, dict):
                        nested = VseLLMClient._first_non_none_bool(
                            VseLLMClient._to_optional_bool(value.get("enabled")),
                            VseLLMClient._to_optional_bool(value.get("supported")),
                        )
                        if nested is not None:
                            return nested
                    return True
        return None

    @staticmethod
    def _to_optional_bool(value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "enabled", "supported", "available"}:
                return True
            if lowered in {"false", "0", "no", "disabled", "unsupported", "unavailable"}:
                return False
        return None

    @staticmethod
    def _first_non_none_bool(*values: Optional[bool]) -> Optional[bool]:
        for value in values:
            if value is not None:
                return value
        return None

    def probe_reasoning_streaming(self, model_id: str, timeout: float = 15.0) -> ReasoningProbeResult:
        api_key = self._settings.vsellm_api_key.strip()
        if not api_key:
            return ReasoningProbeResult(
                model_id=model_id,
                streams_reasoning=False,
                checked_at=datetime.now(timezone.utc),
                error="API-ключ не настроен.",
            )

        payload = {
            "model": model_id,
            "stream": True,
            "max_tokens": 32,
            "messages": [{"role": "user", "content": "Привет"}],
        }
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            with httpx.stream(
                "POST",
                f"{self._settings.vsellm_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
                timeout=httpx.Timeout(timeout=timeout, connect=5.0),
            ) as response:
                if response.status_code >= 400:
                    return ReasoningProbeResult(
                        model_id=model_id,
                        streams_reasoning=False,
                        checked_at=datetime.now(timezone.utc),
                        error=f"HTTP {response.status_code}",
                    )

                streams_reasoning = False
                processed = 0
                for raw_line in response.iter_lines():
                    if not raw_line:
                        continue
                    line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                    if not line.startswith("data:"):
                        continue
                    raw_data = line[len("data:") :].strip()
                    if raw_data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(raw_data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    delta = (choices[0].get("delta") if choices and isinstance(choices[0], dict) else {}) or {}
                    for key in ("reasoning_content", "reasoning", "thinking"):
                        value = delta.get(key)
                        if isinstance(value, str) and value:
                            streams_reasoning = True
                            break
                    processed += 1
                    if streams_reasoning or processed >= 60:
                        break

                return ReasoningProbeResult(
                    model_id=model_id,
                    streams_reasoning=streams_reasoning,
                    checked_at=datetime.now(timezone.utc),
                )
        except (httpx.RequestError, httpx.TimeoutException):
            return ReasoningProbeResult(
                model_id=model_id,
                streams_reasoning=False,
                checked_at=datetime.now(timezone.utc),
                error="timeout/network",
            )

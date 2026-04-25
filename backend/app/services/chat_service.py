from __future__ import annotations

import json
import mimetypes
import re
from base64 import b64encode
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import httpx

from app.core.config import Settings
from app.models.schemas import ModelInfo
from app.services.settings_service import SettingsService
from app.services.vsellm_client import VseLLMClient, VseLLMError
from app.storage.file_store import SessionFileStore, StoredSessionFile
from app.storage.session_store import SessionStore
from app.storage.usage_store import UsageStore
from app.storage.vector_store import SessionVectorStore, StoredChunkVector


class ChatService:
    def __init__(
        self,
        settings: Settings,
        session_store: SessionStore,
        file_store: SessionFileStore,
        vector_store: SessionVectorStore,
        vsellm_client: VseLLMClient,
        settings_service: Optional[SettingsService] = None,
        usage_store: Optional[UsageStore] = None,
    ) -> None:
        self._settings = settings
        self._session_store = session_store
        self._file_store = file_store
        self._vector_store = vector_store
        self._vsellm_client = vsellm_client
        self._settings_service = settings_service or SettingsService(settings)
        self._usage_store = usage_store

    def build_messages_payload(self, session_id: str, user_message: str, file_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        runtime_settings = self._settings_service.get_settings()
        history = self._session_store.get_messages(session_id)
        attached_images = self._resolve_attached_images(session_id=session_id, file_ids=file_ids or [])
        if attached_images:
            self._ensure_vision_supported(selected_model=runtime_settings.selected_model)

        messages: List[Dict[str, Any]] = [{"role": "system", "content": runtime_settings.system_prompt}]
        file_context = self._build_retrieval_context(session_id=session_id, user_message=user_message)
        if file_context:
            messages.append({"role": "system", "content": file_context})
        messages.extend(history)
        messages.append({"role": "user", "content": self._build_user_content(user_message, attached_images)})
        return messages

    def stream_chat(self, session_id: str, user_message: str, file_ids: Optional[List[str]] = None) -> Generator[bytes, None, None]:
        try:
            self._validate_request(session_id=session_id, user_message=user_message, file_ids=file_ids or [])
            runtime_settings = self._settings_service.get_settings()
            messages = self.build_messages_payload(session_id=session_id, user_message=user_message, file_ids=file_ids or [])
            self._ensure_chat_supported(selected_model=runtime_settings.selected_model)
            self._session_store.append_message(session_id=session_id, role="user", content=user_message)
            model = runtime_settings.selected_model
            payload = {"model": model, "messages": messages, "stream": True}
            headers = {"Authorization": f"Bearer {self._settings.vsellm_api_key.strip()}"}
            assistant_text = ""
            usage: Any = None

            with httpx.stream(
                "POST",
                f"{self._settings.vsellm_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
                timeout=httpx.Timeout(timeout=120.0, connect=10.0),
            ) as response:
                if response.status_code >= 400:
                    provider_error = self._extract_provider_error_text(response)
                    if self._is_streaming_unsupported_error(response.status_code, provider_error):
                        fallback_text, fallback_thinking, usage = self._request_non_stream_completion(
                            payload=payload,
                            headers=headers,
                            model=model,
                        )
                        if fallback_thinking:
                            yield self._sse_event("thinking", {"text": fallback_thinking})
                        if fallback_text:
                            assistant_text += fallback_text
                            for chunk_text in self._split_text_for_sse(fallback_text):
                                yield self._sse_event("token", {"text": chunk_text})
                        if assistant_text:
                            self._session_store.append_message(session_id=session_id, role="assistant", content=assistant_text)
                        if self._usage_store is not None:
                            self._usage_store.record_chat_usage(
                                session_id=session_id,
                                usage=usage if isinstance(usage, dict) else None,
                            )
                        yield self._sse_event("done", {"usage": usage})
                        return
                    raise self._provider_status_error(
                        status_code=response.status_code,
                        model=model,
                        provider_reason=provider_error,
                    )

                for raw_line in response.iter_lines():
                    if not raw_line:
                        continue
                    line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                    if not line.startswith("data:"):
                        continue
                    raw_data = line[len("data:") :].strip()
                    if raw_data == "[DONE]":
                        break

                    chunk = json.loads(raw_data)
                    usage = chunk.get("usage", usage)
                    thinking = self._extract_delta_thinking(chunk)
                    if thinking:
                        yield self._sse_event("thinking", {"text": thinking})
                    delta = self._extract_delta_text(chunk)
                    if delta:
                        assistant_text += delta
                        yield self._sse_event("token", {"text": delta})

            if assistant_text:
                self._session_store.append_message(session_id=session_id, role="assistant", content=assistant_text)
            if self._usage_store is not None:
                self._usage_store.record_chat_usage(session_id=session_id, usage=usage if isinstance(usage, dict) else None)
            yield self._sse_event("done", {"usage": usage})
        except VseLLMError as exc:
            yield self._sse_event("error", {"message": exc.user_message})
            yield self._sse_event("done", {"usage": None})
        except (httpx.TimeoutException, httpx.RequestError):
            yield self._sse_event("error", {"message": "Не удалось получить ответ от VseLLM. Проверьте подключение и попробуйте позже."})
            yield self._sse_event("done", {"usage": None})
        except Exception:
            yield self._sse_event("error", {"message": "Произошла внутренняя ошибка при генерации ответа."})
            yield self._sse_event("done", {"usage": None})

    def _validate_request(self, session_id: str, user_message: str, file_ids: List[str]) -> None:
        if not session_id.strip():
            raise VseLLMError(status_code=400, user_message="session_id обязателен.")
        session = self._session_store.get_session(session_id)
        if session is None:
            raise VseLLMError(status_code=404, user_message="Сессия не найдена. Создайте новую сессию.")
        if not user_message.strip():
            raise VseLLMError(status_code=400, user_message="Сообщение не должно быть пустым.")
        if not self._settings.vsellm_api_key.strip():
            raise VseLLMError(status_code=503, user_message="VseLLM API-ключ не настроен на backend.")
        if not self._settings_service.get_settings().selected_model.strip():
            raise VseLLMError(status_code=503, user_message="Глобальная модель не настроена на backend.")
        for file_id in file_ids:
            if file_id not in session.file_ids:
                raise VseLLMError(status_code=400, user_message=f"Файл '{file_id}' не найден в текущей сессии.")

    def _build_retrieval_context(self, session_id: str, user_message: str) -> str:
        session = self._session_store.get_session(session_id)
        if session is None or not session.file_ids:
            return ""
        if not self._vector_store.has_session_chunks(session_id):
            return ""

        query_vector, embeddings_usage = self._get_embeddings_with_usage([user_message])
        if self._usage_store is not None and embeddings_usage is not None:
            self._usage_store.record_embeddings_usage(session_id=session_id, usage=embeddings_usage)
        query_embedding = query_vector[0]
        hits = self._vector_store.search(session_id=session_id, query_embedding=query_embedding, top_k=4)
        if not hits:
            return ""

        return self._format_retrieval_context(hits)

    @staticmethod
    def _format_retrieval_context(hits: List[StoredChunkVector]) -> str:
        lines = [
            "Контекст из загруженных файлов (используй как справочную информацию, если релевантно):",
        ]
        for index, hit in enumerate(hits, start=1):
            lines.append(f"{index}. Файл: {hit.filename}")
            lines.append(f"   Фрагмент: {hit.text}")
        return "\n".join(lines)

    def _resolve_attached_images(self, session_id: str, file_ids: List[str]) -> List[StoredSessionFile]:
        if not file_ids:
            return []
        files: List[StoredSessionFile] = []
        for file_id in file_ids:
            file = self._file_store.get_session_file(session_id=session_id, file_id=file_id)
            if file is None:
                raise VseLLMError(status_code=400, user_message=f"Файл '{file_id}' не найден в текущей сессии.")
            if not self._is_image_file(file):
                raise VseLLMError(
                    status_code=400,
                    user_message=f"Файл '{file.filename}' нельзя прикрепить к сообщению как изображение.",
                )
            files.append(file)
        return files

    def _get_embeddings_with_usage(self, texts: list[str]) -> tuple[list[list[float]], dict | None]:
        if hasattr(self._vsellm_client, "get_embeddings_with_usage"):
            result = self._vsellm_client.get_embeddings_with_usage(texts)
            return result.vectors, result.usage
        return self._vsellm_client.get_embeddings(texts), None

    @staticmethod
    def _is_image_file(file: StoredSessionFile) -> bool:
        if file.content_type.lower().startswith("image/"):
            return True
        guessed = mimetypes.guess_type(file.filename)[0] or ""
        return guessed.startswith("image/")

    @staticmethod
    def _build_user_content(user_message: str, image_files: List[StoredSessionFile]) -> Any:
        if not image_files:
            return user_message
        content: List[Dict[str, Any]] = [{"type": "text", "text": user_message}]
        for file in image_files:
            data_url = ChatService._to_data_url(file)
            content.append({"type": "image_url", "image_url": {"url": data_url}})
        return content

    @staticmethod
    def _to_data_url(file: StoredSessionFile) -> str:
        path = Path(file.path)
        if not path.exists():
            raise VseLLMError(status_code=400, user_message=f"Временный файл '{file.filename}' не найден.")
        content_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "image/png"
        payload = b64encode(path.read_bytes()).decode("ascii")
        return f"data:{content_type};base64,{payload}"

    def _ensure_vision_supported(self, selected_model: str) -> None:
        models = self._vsellm_client.get_models()
        model = next((item for item in models if item.id == selected_model), None)
        # Block only when the API explicitly marks the selected model as non-vision.
        # If model metadata is missing/unknown, try the request and surface provider error.
        if model is not None and model.supports_vision is False:
            raise VseLLMError(
                status_code=400,
                user_message=(
                    "Выбранная модель не поддерживает анализ изображений. "
                    "Выберите vision-модель в настройках и повторите запрос."
                ),
            )

    def _ensure_chat_supported(self, selected_model: str) -> None:
        model = self._get_selected_model_metadata(selected_model)
        if model is not None and model.supports_chat is False:
            raise VseLLMError(
                status_code=400,
                user_message=(
                    f"Модель '{selected_model}' по metadata провайдера не поддерживает chat/completions. "
                    "Выберите другую chat-модель в Настройках."
                ),
            )

    def _get_selected_model_metadata(self, selected_model: str) -> Optional[ModelInfo]:
        try:
            models = self._vsellm_client.get_models()
        except VseLLMError:
            return None
        return next((item for item in models if item.id == selected_model), None)

    @staticmethod
    def _extract_delta_text(chunk: Dict[str, Any]) -> str:
        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        delta = first.get("delta")
        if not isinstance(delta, dict):
            return ""
        text = delta.get("content")
        return text if isinstance(text, str) else ""

    @staticmethod
    def _extract_delta_thinking(chunk: Dict[str, Any]) -> str:
        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        delta = first.get("delta")
        if not isinstance(delta, dict):
            return ""
        for key in ("reasoning_content", "reasoning", "thinking"):
            value = delta.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    @staticmethod
    def _sse_event(event: str, payload: Dict[str, Any]) -> bytes:
        body = json.dumps(payload, ensure_ascii=False)
        return f"event: {event}\ndata: {body}\n\n".encode("utf-8")

    def _request_non_stream_completion(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        model: str,
    ) -> tuple[str, str, Any]:
        fallback_payload = {**payload, "stream": False}
        response = httpx.post(
            f"{self._settings.vsellm_base_url.rstrip('/')}/chat/completions",
            json=fallback_payload,
            headers=headers,
            timeout=httpx.Timeout(timeout=120.0, connect=10.0),
        )
        if response.status_code >= 400:
            provider_reason = self._extract_provider_error_text(response)
            raise self._provider_status_error(
                status_code=response.status_code,
                model=model,
                provider_reason=provider_reason,
            )

        payload_json = response.json()
        usage = payload_json.get("usage")
        text = self._extract_non_stream_text(payload_json)
        thinking = self._extract_non_stream_thinking(payload_json)
        return text, thinking, usage

    @staticmethod
    def _extract_non_stream_text(payload_json: Dict[str, Any]) -> str:
        choices = payload_json.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""

        message = first.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                chunks: list[str] = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    text_value = block.get("text")
                    if isinstance(text_value, str):
                        chunks.append(text_value)
                return "".join(chunks)

        text = first.get("text")
        if isinstance(text, str):
            return text
        return ""

    @staticmethod
    def _extract_non_stream_thinking(payload_json: Dict[str, Any]) -> str:
        choices = payload_json.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        message = first.get("message")
        if not isinstance(message, dict):
            return ""
        for key in ("reasoning_content", "reasoning", "thinking"):
            value = message.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    @staticmethod
    def _split_text_for_sse(text: str, chunk_size: int = 800) -> list[str]:
        if len(text) <= chunk_size:
            return [text]
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            start = end
        return chunks

    @staticmethod
    def _is_streaming_unsupported_error(status_code: int, provider_reason: Optional[str]) -> bool:
        if status_code not in (400, 404, 405, 409, 422):
            return False
        if not provider_reason:
            return False

        reason = provider_reason.lower()
        mentions_stream = "stream" in reason or "streaming" in reason
        explicit_markers = (
            "not support",
            "unsupported",
            "not available",
            "disabled",
            "must be false",
            "should be false",
            "unknown field",
        )
        return mentions_stream and any(marker in reason for marker in explicit_markers)

    @staticmethod
    def _extract_provider_error_text(response: httpx.Response) -> Optional[str]:
        body_text = ""
        try:
            body_text = response.read().decode("utf-8", errors="ignore").strip()
        except Exception:
            body_text = ""

        if not body_text:
            return None

        message = None
        try:
            payload = json.loads(body_text)
            message = ChatService._extract_message_from_payload(payload)
        except json.JSONDecodeError:
            message = body_text

        if not message:
            message = body_text
        return ChatService._sanitize_provider_message(message)

    @staticmethod
    def _extract_message_from_payload(payload: Any) -> Optional[str]:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, list):
            for item in payload:
                nested = ChatService._extract_message_from_payload(item)
                if nested:
                    return nested
            return None
        if not isinstance(payload, dict):
            return None

        for key in ("message", "detail", "error_description"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        error = payload.get("error")
        if error is not None:
            nested = ChatService._extract_message_from_payload(error)
            if nested:
                return nested

        errors = payload.get("errors")
        if isinstance(errors, list):
            for item in errors:
                nested = ChatService._extract_message_from_payload(item)
                if nested:
                    return nested
        return None

    @staticmethod
    def _sanitize_provider_message(message: str) -> str:
        sanitized = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer ***", message, flags=re.IGNORECASE)
        sanitized = re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "sk-***", sanitized)
        sanitized = sanitized.strip()
        if len(sanitized) > 500:
            return f"{sanitized[:500]}..."
        return sanitized

    @staticmethod
    def _provider_status_error(status_code: int, model: str, provider_reason: Optional[str]) -> VseLLMError:
        reason_suffix = f" Причина провайдера: {provider_reason}." if provider_reason else ""
        action_suffix = (
            f" Проверьте модель '{model}' в Настройках: выберите другую chat-модель "
            "или проверьте параметры провайдера."
        )

        if status_code in (401, 403):
            return VseLLMError(
                status_code=status_code,
                user_message="Ошибка авторизации VseLLM. Проверьте API-ключ на backend.",
            )
        if status_code in (400, 404, 422):
            return VseLLMError(
                status_code=400,
                user_message=(
                    f"Модель '{model}' не приняла chat/completions-запрос.{reason_suffix}{action_suffix}"
                ),
            )
        if status_code == 429:
            return VseLLMError(
                status_code=429,
                user_message=f"Сервис временно ограничил частоту запросов. Попробуйте позже.{reason_suffix}",
            )
        if status_code >= 500:
            return VseLLMError(
                status_code=502,
                user_message=f"Сервис VseLLM временно недоступен. Попробуйте позже.{reason_suffix}",
            )
        if status_code >= 400:
            return VseLLMError(
                status_code=502,
                user_message=f"Ошибка запроса к VseLLM.{reason_suffix}{action_suffix}",
            )
        return VseLLMError(status_code=502, user_message="Неизвестная ошибка запроса к VseLLM.")

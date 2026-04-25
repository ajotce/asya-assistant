from __future__ import annotations

import json
import mimetypes
from base64 import b64encode
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import httpx

from app.core.config import Settings
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
                self._raise_for_status(response.status_code)

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
    def _sse_event(event: str, payload: Dict[str, Any]) -> bytes:
        body = json.dumps(payload, ensure_ascii=False)
        return f"event: {event}\ndata: {body}\n\n".encode("utf-8")

    @staticmethod
    def _raise_for_status(status_code: int) -> None:
        if status_code in (401, 403):
            raise VseLLMError(status_code=status_code, user_message="Ошибка авторизации VseLLM. Проверьте API-ключ на backend.")
        if status_code == 404:
            raise VseLLMError(status_code=502, user_message="Модель или endpoint VseLLM не найдены. Проверьте настройки.")
        if status_code == 429:
            raise VseLLMError(status_code=429, user_message="Сервис временно ограничил частоту запросов. Попробуйте позже.")
        if status_code >= 500:
            raise VseLLMError(status_code=502, user_message="Сервис VseLLM временно недоступен. Попробуйте позже.")
        if status_code >= 400:
            raise VseLLMError(status_code=502, user_message="Ошибка запроса к VseLLM.")

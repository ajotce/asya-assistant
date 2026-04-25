from __future__ import annotations

import json
from typing import Any, Dict, Generator, List

import httpx

from app.core.config import Settings
from app.services.vsellm_client import VseLLMError
from app.storage.session_store import SessionStore


class ChatService:
    def __init__(self, settings: Settings, session_store: SessionStore) -> None:
        self._settings = settings
        self._session_store = session_store

    def build_messages_payload(self, session_id: str, user_message: str) -> List[Dict[str, str]]:
        history = self._session_store.get_messages(session_id)
        messages: List[Dict[str, str]] = [{"role": "system", "content": self._settings.default_system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        return messages

    def stream_chat(self, session_id: str, user_message: str) -> Generator[bytes, None, None]:
        try:
            self._validate_request(session_id=session_id, user_message=user_message)
            messages = self.build_messages_payload(session_id=session_id, user_message=user_message)
            self._session_store.append_message(session_id=session_id, role="user", content=user_message)
            model = self._settings.default_chat_model
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

    def _validate_request(self, session_id: str, user_message: str) -> None:
        if not session_id.strip():
            raise VseLLMError(status_code=400, user_message="session_id обязателен.")
        if not self._session_store.has_session(session_id):
            raise VseLLMError(status_code=404, user_message="Сессия не найдена. Создайте новую сессию.")
        if not user_message.strip():
            raise VseLLMError(status_code=400, user_message="Сообщение не должно быть пустым.")
        if not self._settings.vsellm_api_key.strip():
            raise VseLLMError(status_code=503, user_message="VseLLM API-ключ не настроен на backend.")
        if not self._settings.default_chat_model.strip():
            raise VseLLMError(status_code=503, user_message="Глобальная модель не настроена на backend.")

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

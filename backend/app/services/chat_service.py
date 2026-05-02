from __future__ import annotations

import json
import mimetypes
import re
from base64 import b64encode
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models.common import ActivityEntityType, ActivityEventType, ChatKind, MemoryStatus, MessageRole
from app.models.schemas import ModelInfo
from app.repositories.activity_log_repository import ActivityLogRepository
from app.repositories.behavior_rule_repository import BehaviorRuleRepository
from app.repositories.chat_repository import ChatRepository
from app.repositories.memory_episode_repository import MemoryEpisodeRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.personality_profile_repository import PersonalityProfileRepository
from app.repositories.user_profile_fact_repository import UserProfileFactRepository
from app.repositories.user_repository import UserRepository
from app.services.memory_extraction_service import MemoryExtractionService
from app.services.memory_service import MemoryService
from app.services.private_chat_crypto import decrypt_private_message, encrypt_private_message
from app.services.action_router import ActionRouter
from app.services.settings_service import SettingsService
from app.services.usage_recorder import UsageRecorder
from app.services.vsellm_client import VseLLMClient, VseLLMError
from app.storage.file_store import SessionFileStore, StoredSessionFile
from app.storage.session_store import SessionStore
from app.storage.usage_store import UsageStore
from app.storage.vector_store import SessionVectorStore, StoredChunkVector


@dataclass
class MemoryContextBuildResult:
    context: str
    used: bool
    meta: dict[str, Any]


class ChatService:
    def __init__(
        self,
        settings: Settings,
        file_store: SessionFileStore,
        vector_store: SessionVectorStore,
        vsellm_client: VseLLMClient,
        current_user_id: str = "",
        db_session: Optional[Session] = None,
        chat_repository: Optional[ChatRepository] = None,
        message_repository: Optional[MessageRepository] = None,
        session_store: Optional[SessionStore] = None,
        settings_service: Optional[SettingsService] = None,
        memory_extraction_service: Optional[MemoryExtractionService] = None,
        usage_recorder: Optional[UsageRecorder] = None,
        usage_store: Optional[UsageStore] = None,
        action_router: Optional[ActionRouter] = None,
    ) -> None:
        self._settings = settings
        self._current_user_id = current_user_id
        self._db_session = db_session
        self._chat_repository = chat_repository
        self._message_repository = message_repository
        self._session_store = session_store
        self._file_store = file_store
        self._vector_store = vector_store
        self._vsellm_client = vsellm_client
        self._settings_service = settings_service or SettingsService(settings)
        self._memory_extraction_service = memory_extraction_service
        self._usage_recorder = usage_recorder
        self._usage_store = usage_store
        self._action_router = action_router
        self._last_memory_usage_meta: dict[str, Any] | None = None

    def build_messages_payload(self, session_id: str, user_message: str, file_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        runtime_settings = self._get_runtime_settings()
        history = self._build_history_payload(session_id)
        attached_images = self._resolve_attached_images(session_id=session_id, file_ids=file_ids or [])
        if attached_images:
            self._ensure_vision_supported(selected_model=runtime_settings.selected_model)

        messages: List[Dict[str, Any]] = [{"role": "system", "content": runtime_settings.system_prompt}]
        memory_context = self._build_memory_context(session_id=session_id, user_message=user_message)
        self._last_memory_usage_meta = memory_context.meta if memory_context.used else None
        if memory_context.context:
            messages.append({"role": "system", "content": memory_context.context})
        file_context = self._build_retrieval_context(session_id=session_id, user_message=user_message)
        if file_context:
            messages.append({"role": "system", "content": file_context})
        messages.extend(history)
        messages.append({"role": "user", "content": self._build_user_content(user_message, attached_images)})
        return messages

    def stream_chat(self, session_id: str, user_message: str, file_ids: Optional[List[str]] = None) -> Generator[bytes, None, None]:
        try:
            self._validate_request(session_id=session_id, user_message=user_message, file_ids=file_ids or [])
            if self._action_router is not None:
                action_result = self._action_router.handle(
                    user_id=self._current_user_id,
                    session_id=session_id,
                    message=user_message,
                )
                if action_result.handled:
                    self._append_message(
                        chat_id=session_id,
                        role=MessageRole.USER.value,
                        content=user_message,
                        user_id=self._current_user_id,
                    )
                    self._append_message(
                        chat_id=session_id,
                        role=MessageRole.ASSISTANT.value,
                        content=action_result.message,
                        user_id=None,
                    )
                    yield self._sse_event("token", {"text": action_result.message})
                    yield self._sse_event("done", {"usage": None})
                    return
            runtime_settings = self._get_runtime_settings()
            messages = self.build_messages_payload(session_id=session_id, user_message=user_message, file_ids=file_ids or [])
            self._ensure_chat_supported(selected_model=runtime_settings.selected_model)
            self._append_message(
                chat_id=session_id,
                role=MessageRole.USER.value,
                content=user_message,
                user_id=self._current_user_id,
            )
            model = runtime_settings.selected_model
            payload = {"model": model, "messages": messages, "stream": True}
            headers = {"Authorization": f"Bearer {self._settings.vsellm_api_key.strip()}"}
            assistant_text = ""
            usage: Any = None

            if self._is_reasoning_model(model):
                yield from self._stream_reasoning_via_non_stream(
                    session_id=session_id,
                    payload=payload,
                    headers=headers,
                    model=model,
                )
                return

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
                            self._append_message(
                                chat_id=session_id,
                                role=MessageRole.ASSISTANT.value,
                                content=assistant_text,
                                user_id=None,
                            )
                            self._record_memory_usage_event(chat_id=session_id)
                            self._run_memory_extraction(
                                chat_id=session_id,
                                user_message=user_message,
                                assistant_message=assistant_text,
                            )
                        if self._usage_store is not None:
                            self._usage_store.record_chat_usage(
                                session_id=session_id,
                                usage=usage if isinstance(usage, dict) else None,
                            )
                        if self._usage_recorder is not None:
                            self._usage_recorder.record_chat_usage(
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
                self._append_message(
                    chat_id=session_id,
                    role=MessageRole.ASSISTANT.value,
                    content=assistant_text,
                    user_id=None,
                )
                self._record_memory_usage_event(chat_id=session_id)
                self._run_memory_extraction(
                    chat_id=session_id,
                    user_message=user_message,
                    assistant_message=assistant_text,
                )
            if self._usage_store is not None:
                self._usage_store.record_chat_usage(session_id=session_id, usage=usage if isinstance(usage, dict) else None)
            if self._usage_recorder is not None:
                self._usage_recorder.record_chat_usage(
                    session_id=session_id,
                    usage=usage if isinstance(usage, dict) else None,
                )
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
        if not self._session_exists_for_user(session_id):
            raise VseLLMError(status_code=404, user_message="Сессия не найдена. Создайте новую сессию.")
        if not user_message.strip():
            raise VseLLMError(status_code=400, user_message="Сообщение не должно быть пустым.")
        if not self._settings.vsellm_api_key.strip():
            raise VseLLMError(status_code=503, user_message="VseLLM API-ключ не настроен на backend.")
        if not self._get_runtime_settings().selected_model.strip():
            raise VseLLMError(status_code=503, user_message="Глобальная модель не настроена на backend.")
        for file_id in file_ids:
            if self._file_store.get_session_file(session_id=session_id, file_id=file_id) is None:
                raise VseLLMError(status_code=400, user_message=f"Файл '{file_id}' не найден в текущей сессии.")

    def _build_retrieval_context(self, session_id: str, user_message: str) -> str:
        if self._session_store is not None:
            session = self._session_store.get_session(session_id)
            if session is None or not session.file_ids:
                return ""
        else:
            session_files = self._file_store.get_session_files(session_id)
            if not session_files:
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

    def _build_memory_context(self, session_id: str, user_message: str) -> MemoryContextBuildResult:
        if not self._current_user_id or self._chat_repository is None or self._db_session is None:
            return MemoryContextBuildResult(context="", used=False, meta={})

        if self._is_private_encrypted_chat(session_id):
            return MemoryContextBuildResult(context="", used=False, meta={"disabled_private_chat": True})

        chat = self._chat_repository.get_for_user(session_id, self._current_user_id)
        if chat is None:
            return MemoryContextBuildResult(context="", used=False, meta={})

        space_settings = None
        if chat.space_id:
            from app.db.models.space_memory_settings import SpaceMemorySettings

            space_settings = self._db_session.get(SpaceMemorySettings, chat.space_id)
        if space_settings is not None and not space_settings.memory_read_enabled:
            return MemoryContextBuildResult(context="", used=False, meta={"disabled_by_space_settings": True})

        facts_repo = UserProfileFactRepository(self._db_session)
        rules_repo = BehaviorRuleRepository(self._db_session)
        episodes_repo = MemoryEpisodeRepository(self._db_session)
        personality_repo = PersonalityProfileRepository(self._db_session)

        facts = facts_repo.list_active_for_user_space(user_id=self._current_user_id, space_id=chat.space_id, limit=24)
        facts = self._apply_fact_status_conflict_policy(facts)
        rules = []
        if space_settings is None or space_settings.behavior_rules_enabled:
            rules = rules_repo.list_active_for_user_space(user_id=self._current_user_id, space_id=chat.space_id, limit=10)
        episodes = episodes_repo.list_relevant_for_user_space(user_id=self._current_user_id, space_id=chat.space_id, limit=12)
        episodes = self._select_relevant_episodes(episodes=episodes, user_message=user_message, limit=3)

        personality_base = personality_repo.get_base_for_user(self._current_user_id)
        personality_overlay = None
        if chat.space_id and (space_settings is None or space_settings.personality_overlay_enabled):
            personality_overlay = personality_repo.get_space_overlay_for_user(
                user_id=self._current_user_id,
                space_id=chat.space_id,
            )
        complaint_detected = self._is_quality_complaint_message(user_message)

        context = self._format_memory_context(
            facts=facts[:8],
            rules=rules[:6],
            episodes=episodes,
            personality_base=personality_base,
            personality_overlay=personality_overlay,
            complaint_detected=complaint_detected,
        )
        if not context:
            return MemoryContextBuildResult(context="", used=False, meta={})

        return MemoryContextBuildResult(
            context=context,
            used=True,
            meta={
                "space_id": chat.space_id,
                "facts_used": len(facts[:8]),
                "rules_used": len(rules[:6]),
                "episodes_used": len(episodes),
                "personality_base_used": personality_base is not None and personality_base.is_active,
                "personality_overlay_used": personality_overlay is not None,
            },
        )

    @staticmethod
    def _apply_fact_status_conflict_policy(facts: list[Any]) -> list[Any]:
        confirmed_keys = {item.key for item in facts if item.status == MemoryStatus.CONFIRMED}
        filtered: list[Any] = []
        for item in facts:
            if item.status in {MemoryStatus.FORBIDDEN, MemoryStatus.DELETED}:
                continue
            if item.status == MemoryStatus.OUTDATED and item.key in confirmed_keys:
                continue
            filtered.append(item)
        return filtered

    @staticmethod
    def _select_relevant_episodes(*, episodes: list[Any], user_message: str, limit: int) -> list[Any]:
        terms = {token for token in re.findall(r"\w+", user_message.lower()) if len(token) >= 4}
        if not terms:
            return episodes[:limit]

        scored: list[tuple[int, Any]] = []
        for item in episodes:
            summary = (item.summary or "").lower()
            score = sum(1 for term in terms if term in summary)
            scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        selected = [item for score, item in scored if score > 0][:limit]
        if len(selected) < limit:
            fallback = [item for _, item in scored if item not in selected]
            selected.extend(fallback[: limit - len(selected)])
        return selected[:limit]

    @staticmethod
    def _format_memory_context(
        *,
        facts: list[Any],
        rules: list[Any],
        episodes: list[Any],
        personality_base: Any,
        personality_overlay: Any,
        complaint_detected: bool,
    ) -> str:
        lines: list[str] = []
        if personality_base is not None and personality_base.is_active:
            lines.append("Профиль личности (base):")
            lines.append(f"- Имя ассистента: {personality_base.name}")
            lines.append(f"- Тон: {personality_base.tone}")
            lines.append(f"- Юмор: {ChatService._describe_level(personality_base.humor_level)}")
            lines.append(f"- Инициативность в чате: {ChatService._describe_level(personality_base.initiative_level)}")
            lines.append(f"- Мягкое возражение при рисках: {'да' if personality_base.can_gently_disagree else 'нет'}")
            lines.append(f"- Обращаться по имени пользователя: {'да' if personality_base.address_user_by_name else 'нет'}")
            if personality_base.style_notes:
                lines.append(f"- Заметки по стилю: {personality_base.style_notes[:220]}")
        if personality_overlay is not None:
            lines.append("Профиль личности (space overlay):")
            lines.append(f"- Имя ассистента: {personality_overlay.name}")
            lines.append(f"- Тон в пространстве: {personality_overlay.tone}")
            lines.append(f"- Юмор в пространстве: {ChatService._describe_level(personality_overlay.humor_level)}")
            lines.append(f"- Инициативность в пространстве: {ChatService._describe_level(personality_overlay.initiative_level)}")
            lines.append(
                f"- Мягкое возражение в пространстве: {'да' if personality_overlay.can_gently_disagree else 'нет'}"
            )
            lines.append(
                f"- Обращение по имени в пространстве: {'да' if personality_overlay.address_user_by_name else 'нет'}"
            )
            if personality_overlay.style_notes:
                lines.append(f"- Overlay заметки: {personality_overlay.style_notes[:220]}")
        if facts:
            lines.append("Факты о пользователе:")
            for item in facts:
                lines.append(f"- {item.key}: {item.value}")
        if rules:
            lines.append("Правила поведения:")
            for item in rules:
                lines.append(f"- {item.title}: {item.instruction[:220]}")
        if episodes:
            lines.append("Релевантные эпизоды:")
            for item in episodes:
                lines.append(f"- {item.summary[:260]}")
        if not lines:
            return ""
        lines.append("Ограничения: не имитируй сознание/эмоции, не играй роль терапевта, не морализируй.")
        if complaint_detected:
            lines.append(
                "Пользователь явно указывает на ошибку/неподходящий ответ: извинись кратко и предложи сохранить правило на будущее."
            )
        lines.append("Если память противоречит текущему явному запросу пользователя, приоритет у текущего запроса.")
        return "Контекст долговременной памяти (используй только если релевантно):\n" + "\n".join(lines)

    @staticmethod
    def _describe_level(value: int) -> str:
        mapping = {0: "низкий", 1: "средний", 2: "высокий"}
        return mapping.get(value, "средний")

    @staticmethod
    def _is_quality_complaint_message(text: str) -> bool:
        lowered = (text or "").lower()
        markers = (
            "ты ошиб",
            "асya ошиб",
            "asya ошиб",
            "ответила не так",
            "ответил не так",
            "это не то",
            "неправильн",
            "не так ответ",
        )
        return any(marker in lowered for marker in markers)

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
        except Exception:
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

    @staticmethod
    def _is_reasoning_model(model_id: str) -> bool:
        identifier = (model_id or "").lower()
        if not identifier:
            return False
        markers = ("deepseek-r1", "/o1", "/o3", "openai/o1", "openai/o3")
        if any(marker in identifier for marker in markers):
            return True
        suffix = identifier.rsplit("/", 1)[-1]
        suffix_markers = ("o1", "o3")
        return any(suffix == m or suffix.startswith(f"{m}-") for m in suffix_markers)

    def _get_runtime_settings(self):
        # Backward-compatible call: unit tests may provide fake services without user_id support.
        try:
            return self._settings_service.get_settings(user_id=self._current_user_id or None)
        except TypeError:
            return self._settings_service.get_settings()

    def _stream_reasoning_via_non_stream(
        self,
        session_id: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        model: str,
    ) -> Generator[bytes, None, None]:
        text, thinking, usage = self._request_non_stream_completion(
            payload=payload,
            headers=headers,
            model=model,
        )
        if thinking:
            for chunk_text in self._split_text_for_sse(thinking, chunk_size=80):
                yield self._sse_event("thinking", {"text": chunk_text})
        if text:
            self._append_message(
                chat_id=session_id,
                role=MessageRole.ASSISTANT.value,
                content=text,
                user_id=None,
            )
            self._record_memory_usage_event(chat_id=session_id)
            self._run_memory_extraction(
                chat_id=session_id,
                user_message=self._extract_last_user_text(payload),
                assistant_message=text,
            )
            for chunk_text in self._split_text_for_sse(text, chunk_size=80):
                yield self._sse_event("token", {"text": chunk_text})
        if self._usage_store is not None:
            self._usage_store.record_chat_usage(
                session_id=session_id,
                usage=usage if isinstance(usage, dict) else None,
            )
        if self._usage_recorder is not None:
            self._usage_recorder.record_chat_usage(
                session_id=session_id,
                usage=usage if isinstance(usage, dict) else None,
            )
        yield self._sse_event("done", {"usage": usage})

    def _run_memory_extraction(self, *, chat_id: str, user_message: str, assistant_message: str) -> None:
        if not self._settings.memory_extraction_enabled:
            return
        if not self._current_user_id or self._chat_repository is None or self._db_session is None:
            return
        if self._is_private_encrypted_chat(chat_id):
            return
        try:
            chat = self._chat_repository.get_for_user(chat_id, self._current_user_id)
            if chat is None:
                return
            extraction = self._memory_extraction_service
            if extraction is None:
                extraction = MemoryExtractionService(MemoryService(self._db_session))
            user = UserRepository(self._db_session).get_by_id(self._current_user_id)
            if user is None:
                return
            extraction.process_turn(
                user=user,
                chat_id=chat_id,
                user_message=user_message,
                assistant_message=assistant_message,
            )
        except Exception:
            # Extraction is best-effort and must never break chat response flow.
            return

    def _record_memory_usage_event(self, *, chat_id: str) -> None:
        if not self._last_memory_usage_meta:
            return
        if not self._db_session or not self._current_user_id:
            return
        try:
            chat = self._chat_repository.get_for_user(chat_id, self._current_user_id) if self._chat_repository else None
            ActivityLogRepository(self._db_session).create(
                user_id=self._current_user_id,
                space_id=(chat.space_id if chat else None),
                event_type=ActivityEventType.MEMORY_USED_IN_RESPONSE,
                entity_type=ActivityEntityType.MEMORY_CHANGE,
                entity_id=chat_id,
                summary="В ответе использован контекст долговременной памяти",
                meta=self._last_memory_usage_meta,
            )
        except Exception:
            return

    @staticmethod
    def _extract_last_user_text(payload: Dict[str, Any]) -> str:
        messages = payload.get("messages")
        if not isinstance(messages, list):
            return ""
        for item in reversed(messages):
            if not isinstance(item, dict):
                continue
            if item.get("role") != "user":
                continue
            content = item.get("content")
            if isinstance(content, str):
                return content
            return ""
        return ""

    def _build_history_payload(self, chat_id: str) -> List[Dict[str, Any]]:
        if self._session_store is not None:
            return self._session_store.get_messages(chat_id)
        if self._message_repository is None:
            return []
        messages = self._message_repository.list_for_chat(chat_id)
        result: List[Dict[str, Any]] = []
        password_hash = self._get_user_password_hash()
        salt = self._get_chat_private_salt(chat_id)
        for msg in messages:
            text = msg.content
            if not text and msg.content_encrypted and password_hash and salt:
                try:
                    text = decrypt_private_message(
                        password_hash=password_hash, salt=salt, content_encrypted=msg.content_encrypted
                    )
                except Exception:
                    text = ""
            result.append({"role": msg.role.value, "content": text})
        return result

    def _append_message(self, chat_id: str, role: str, content: str, user_id: Optional[str]) -> None:
        if self._session_store is not None:
            self._session_store.append_message(chat_id, role=role, content=content)
            return
        if self._message_repository is None:
            return
        if self._is_private_encrypted_chat(chat_id):
            password_hash = self._get_user_password_hash()
            salt = self._get_chat_private_salt(chat_id)
            if password_hash and salt:
                encrypted = encrypt_private_message(password_hash=password_hash, salt=salt, content=content)
                self._message_repository.create(
                    chat_id=chat_id,
                    user_id=user_id,
                    role=role,
                    content="",
                    content_encrypted=encrypted,
                    encryption_salt=salt,
                )
                return
        self._message_repository.create(chat_id=chat_id, user_id=user_id, role=role, content=content)

    def _session_exists_for_user(self, session_id: str) -> bool:
        if self._session_store is not None:
            return self._session_store.has_session(session_id)
        if self._chat_repository is None:
            return False
        return self._chat_repository.get_for_user(session_id, self._current_user_id) is not None

    def _get_chat(self, chat_id: str):
        if self._chat_repository is not None:
            return self._chat_repository.get_for_user(chat_id, self._current_user_id)
        return None

    def _is_private_encrypted_chat(self, chat_id: str) -> bool:
        if not self._current_user_id or self._chat_repository is None:
            return False
        chat = self._get_chat(chat_id)
        if chat is None:
            return False
        return chat.kind == ChatKind.PRIVATE_ENCRYPTED

    def _get_user_password_hash(self) -> str | None:
        if not self._current_user_id or self._db_session is None:
            return None
        user = UserRepository(self._db_session).get_by_id(self._current_user_id)
        return user.password_hash if user else None

    def _get_chat_private_salt(self, chat_id: str) -> str | None:
        chat = self._get_chat(chat_id)
        return chat.private_salt if chat else None

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

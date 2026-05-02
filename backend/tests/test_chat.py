import io
import tempfile
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from app.api.deps_auth import get_db_session
from app.main import app
from app.services.chat_service import ChatService
from app.services.vsellm_client import VseLLMClient, VseLLMError
from app.storage.file_store import SessionFileStore, StoredSessionFile
from app.storage.runtime import usage_store
from app.storage.session_store import SessionStore
from app.storage.vector_store import SessionVectorStore, StoredChunkVector
from tests.auth_helpers import override_db_session, setup_test_db


class FakeSettings:
    vsellm_api_key = "test-key"
    vsellm_base_url = "https://api.vsellm.ru/v1"
    default_chat_model = "openai/gpt-5"
    default_embedding_model = "text-embedding-3-small"
    default_system_prompt = "System prompt"
    sqlite_path = "/tmp/asya-test.sqlite3"


def _build_file_store() -> SessionFileStore:
    return SessionFileStore(base_tmp_dir=tempfile.mkdtemp(prefix="asya-chat-test-"))


def _make_png_bytes() -> bytes:
    image = Image.new("RGB", (4, 4), color=(255, 0, 0))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class FakeRuntimeSettings:
    system_prompt = "System prompt"
    selected_model = "openai/gpt-5"


class FakeSettingsService:
    def get_settings(self):
        return FakeRuntimeSettings()


def test_build_messages_payload_uses_system_prompt_and_session_context() -> None:
    store = SessionStore()
    vector_store = SessionVectorStore()
    session = store.create_session()
    session_id = session.session_id
    store.append_message(session_id, "user", "old user")
    store.append_message(session_id, "assistant", "old assistant")
    service = ChatService(
        settings=FakeSettings(),
        session_store=store,
        file_store=_build_file_store(),
        vector_store=vector_store,
        vsellm_client=VseLLMClient(FakeSettings()),
        settings_service=FakeSettingsService(),
    )

    messages = service.build_messages_payload(session_id=session_id, user_message="new message")

    assert messages[0] == {"role": "system", "content": "System prompt"}
    assert messages[1] == {"role": "user", "content": "old user"}
    assert messages[2] == {"role": "assistant", "content": "old assistant"}
    assert messages[3] == {"role": "user", "content": "new message"}


def test_stream_chat_returns_error_event_on_vsellm_validation_error() -> None:
    class NoKeySettings(FakeSettings):
        vsellm_api_key = ""

    store = SessionStore()
    vector_store = SessionVectorStore()
    session_id = store.create_session().session_id
    service = ChatService(
        settings=NoKeySettings(),
        session_store=store,
        file_store=_build_file_store(),
        vector_store=vector_store,
        vsellm_client=VseLLMClient(NoKeySettings()),
        settings_service=FakeSettingsService(),
    )
    chunks = list(service.stream_chat(session_id=session_id, user_message="Hello"))
    payload = b"".join(chunks).decode("utf-8")

    assert "event: error" in payload
    assert "VseLLM API-ключ не настроен на backend." in payload


def test_stream_chat_returns_error_when_session_missing() -> None:
    service = ChatService(
        settings=FakeSettings(),
        session_store=SessionStore(),
        file_store=_build_file_store(),
        vector_store=SessionVectorStore(),
        vsellm_client=VseLLMClient(FakeSettings()),
        settings_service=FakeSettingsService(),
    )
    chunks = list(service.stream_chat(session_id="missing", user_message="Hello"))
    payload = b"".join(chunks).decode("utf-8")
    assert "event: error" in payload
    assert "Сессия не найдена" in payload


def test_stream_chat_endpoint_streams_events(monkeypatch, tmp_path) -> None:
    class FakeService:
        def stream_chat(self, session_id: str, user_message: str, file_ids=None):
            yield b'event: token\ndata: {"text":"Hi"}\n\n'
            yield b'event: done\ndata: {"usage":null}\n\n'

    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)
    monkeypatch.setattr("app.api.routes_chat.get_chat_service", lambda *args, **kwargs: FakeService())
    client = TestClient(app)
    client.post(
        "/api/auth/register",
        json={"email": "chat@example.com", "display_name": "Chat", "password": "strong-pass-123"},
    )
    client.post("/api/auth/login", json={"email": "chat@example.com", "password": "strong-pass-123"})
    response = client.post("/api/chat/stream", json={"session_id": "s-1", "message": "hello"})
    text = response.text
    assert response.status_code == 200
    assert "event: token" in text
    assert "event: done" in text
    app.dependency_overrides.clear()


def test_status_mapper_for_rate_limit_error() -> None:
    error = ChatService._provider_status_error(status_code=429, model="openai/gpt-5", provider_reason=None)
    assert error.status_code == 429
    assert "ограничил частоту запросов" in error.user_message


def test_chunk_text_splits_long_text() -> None:
    text = " ".join(["token"] * 1200)
    from app.services.file_service import FileService

    chunked = FileService._chunk_text(text=text, chunk_size=500, overlap=100)
    assert len(chunked) > 1
    assert all(chunk.strip() for chunk in chunked)


def test_build_messages_payload_includes_retrieved_file_context() -> None:
    class FakeEmbeddingsClient:
        def get_embeddings(self, texts, model=None):
            return [[1.0, 0.0]]

    store = SessionStore()
    vector_store = SessionVectorStore()
    session = store.create_session()
    session_id = session.session_id
    store.bind_file(session_id=session_id, file_id="file-1")
    vector_store.upsert_file_chunks(
        session_id=session_id,
        file_id="file-1",
        chunks=[
            StoredChunkVector(
                chunk_id="c1",
                file_id="file-1",
                filename="doc.pdf",
                text="Нужный фрагмент про договор.",
                embedding=[1.0, 0.0],
            )
        ],
    )
    service = ChatService(
        settings=FakeSettings(),
        session_store=store,
        file_store=_build_file_store(),
        vector_store=vector_store,
        vsellm_client=FakeEmbeddingsClient(),
        settings_service=FakeSettingsService(),
    )

    messages = service.build_messages_payload(session_id=session_id, user_message="Что по договору?")
    assert messages[1]["role"] == "system"
    assert "Контекст из загруженных файлов" in messages[1]["content"]
    assert "doc.pdf" in messages[1]["content"]


def test_stream_chat_returns_embeddings_error_for_retrieval() -> None:
    class FakeEmbeddingsClient:
        def get_embeddings(self, texts, model=None):
            raise VseLLMError(status_code=502, user_message="Embeddings API недоступен.")

    store = SessionStore()
    vector_store = SessionVectorStore()
    session_id = store.create_session().session_id
    store.bind_file(session_id=session_id, file_id="file-1")
    vector_store.upsert_file_chunks(
        session_id=session_id,
        file_id="file-1",
        chunks=[StoredChunkVector(chunk_id="c1", file_id="file-1", filename="doc.pdf", text="x", embedding=[1.0])],
    )

    service = ChatService(
        settings=FakeSettings(),
        session_store=store,
        file_store=_build_file_store(),
        vector_store=vector_store,
        vsellm_client=FakeEmbeddingsClient(),
        settings_service=FakeSettingsService(),
    )
    payload = b"".join(service.stream_chat(session_id=session_id, user_message="question")).decode("utf-8")
    assert "event: error" in payload
    assert "Embeddings API недоступен." in payload


def test_build_messages_payload_with_attached_image_for_vision_model() -> None:
    class FakeVisionClient:
        def get_models(self):
            from app.models.schemas import ModelInfo

            return [ModelInfo(id="openai/gpt-5", supports_vision=True)]

        def get_embeddings(self, texts, model=None):
            return [[0.0, 1.0]]

    store = SessionStore()
    session_id = store.create_session().session_id
    file_store = _build_file_store()
    session_dir = file_store.session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    image_path = session_dir / "img.png"
    image_path.write_bytes(_make_png_bytes())
    file_store.register_files(
        session_id,
        [
            StoredSessionFile(
                file_id="img-1",
                session_id=session_id,
                filename="img.png",
                content_type="image/png",
                size_bytes=image_path.stat().st_size,
                path=str(image_path),
            )
        ],
    )
    store.bind_file(session_id, "img-1")
    service = ChatService(
        settings=FakeSettings(),
        session_store=store,
        file_store=file_store,
        vector_store=SessionVectorStore(),
        vsellm_client=FakeVisionClient(),
        settings_service=FakeSettingsService(),
    )
    messages = service.build_messages_payload(session_id=session_id, user_message="Что на фото?", file_ids=["img-1"])
    user_message = messages[-1]
    assert user_message["role"] == "user"
    assert isinstance(user_message["content"], list)
    assert user_message["content"][1]["type"] == "image_url"
    assert user_message["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_stream_chat_returns_error_when_model_has_no_vision_support() -> None:
    class FakeNoVisionClient:
        def get_models(self):
            from app.models.schemas import ModelInfo

            return [ModelInfo(id="openai/gpt-5", supports_vision=False)]

        def get_embeddings(self, texts, model=None):
            return [[0.0, 1.0]]

    store = SessionStore()
    session_id = store.create_session().session_id
    file_store = _build_file_store()
    session_dir = file_store.session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    image_path = session_dir / "img.png"
    image_path.write_bytes(_make_png_bytes())
    file_store.register_files(
        session_id,
        [
            StoredSessionFile(
                file_id="img-1",
                session_id=session_id,
                filename="img.png",
                content_type="image/png",
                size_bytes=image_path.stat().st_size,
                path=str(image_path),
            )
        ],
    )
    store.bind_file(session_id, "img-1")
    service = ChatService(
        settings=FakeSettings(),
        session_store=store,
        file_store=file_store,
        vector_store=SessionVectorStore(),
        vsellm_client=FakeNoVisionClient(),
        settings_service=FakeSettingsService(),
    )

    payload = b"".join(service.stream_chat(session_id=session_id, user_message="Опиши фото", file_ids=["img-1"])).decode("utf-8")
    assert "event: error" in payload
    assert "не поддерживает анализ изображений" in payload


def test_stream_chat_returns_clear_provider_reason_with_selected_model(monkeypatch) -> None:
    class FakeErrorResponse:
        status_code = 422

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"error":{"message":"Model does not support chat/completions"}}'

        def iter_lines(self):
            return []

    monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: FakeErrorResponse())

    store = SessionStore()
    session_id = store.create_session().session_id
    service = ChatService(
        settings=FakeSettings(),
        session_store=store,
        file_store=_build_file_store(),
        vector_store=SessionVectorStore(),
        vsellm_client=VseLLMClient(FakeSettings()),
        settings_service=FakeSettingsService(),
    )

    payload = b"".join(service.stream_chat(session_id=session_id, user_message="Привет")).decode("utf-8")
    assert "event: error" in payload
    assert "openai/gpt-5" in payload
    assert "Model does not support chat/completions" in payload
    assert "выберите другую chat-модель" in payload


def test_stream_chat_falls_back_to_non_stream_when_streaming_is_not_supported(monkeypatch) -> None:
    class FakeStreamingUnsupportedResponse:
        status_code = 422

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"error":{"message":"Streaming is not supported for this model"}}'

        def iter_lines(self):
            return []

    captured_stream_flags: list[bool] = []

    def fake_post(*args, **kwargs):
        captured_stream_flags.append(bool(kwargs["json"].get("stream")))
        request = httpx.Request("POST", "https://api.vsellm.ru/v1/chat/completions")
        return httpx.Response(
            status_code=200,
            request=request,
            json={
                "choices": [{"message": {"content": "Ответ без streaming от провайдера."}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
            },
        )

    monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: FakeStreamingUnsupportedResponse())
    monkeypatch.setattr("httpx.post", fake_post)

    store = SessionStore()
    session_id = store.create_session().session_id
    service = ChatService(
        settings=FakeSettings(),
        session_store=store,
        file_store=_build_file_store(),
        vector_store=SessionVectorStore(),
        vsellm_client=VseLLMClient(FakeSettings()),
        settings_service=FakeSettingsService(),
    )

    payload = b"".join(service.stream_chat(session_id=session_id, user_message="Привет")).decode("utf-8")
    assert "event: token" in payload
    assert "Ответ без streaming от провайдера." in payload
    assert "event: done" in payload
    assert "event: error" not in payload
    assert captured_stream_flags == [False]


def test_stream_chat_returns_error_when_model_metadata_disables_chat_support() -> None:
    class FakeNoChatClient:
        def get_models(self):
            from app.models.schemas import ModelInfo

            return [ModelInfo(id="openai/gpt-5", supports_chat=False)]

    store = SessionStore()
    session_id = store.create_session().session_id
    service = ChatService(
        settings=FakeSettings(),
        session_store=store,
        file_store=_build_file_store(),
        vector_store=SessionVectorStore(),
        vsellm_client=FakeNoChatClient(),
        settings_service=FakeSettingsService(),
    )

    payload = b"".join(service.stream_chat(session_id=session_id, user_message="Привет")).decode("utf-8")
    assert "event: error" in payload
    assert "не поддерживает chat/completions" in payload


def test_build_messages_payload_allows_image_when_vision_support_unknown() -> None:
    class FakeUnknownVisionClient:
        def get_models(self):
            from app.models.schemas import ModelInfo

            return [ModelInfo(id="openai/gpt-5", supports_vision=None)]

        def get_embeddings(self, texts, model=None):
            return [[0.0, 1.0]]

    store = SessionStore()
    session_id = store.create_session().session_id
    file_store = _build_file_store()
    session_dir = file_store.session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    image_path = session_dir / "img.png"
    image_path.write_bytes(_make_png_bytes())
    file_store.register_files(
        session_id,
        [
            StoredSessionFile(
                file_id="img-1",
                session_id=session_id,
                filename="img.png",
                content_type="image/png",
                size_bytes=image_path.stat().st_size,
                path=str(image_path),
            )
        ],
    )
    store.bind_file(session_id, "img-1")
    service = ChatService(
        settings=FakeSettings(),
        session_store=store,
        file_store=file_store,
        vector_store=SessionVectorStore(),
        vsellm_client=FakeUnknownVisionClient(),
        settings_service=FakeSettingsService(),
    )

    messages = service.build_messages_payload(session_id=session_id, user_message="Опиши фото", file_ids=["img-1"])
    user_message = messages[-1]
    assert user_message["role"] == "user"
    assert isinstance(user_message["content"], list)
    assert user_message["content"][1]["type"] == "image_url"


def test_build_messages_payload_allows_image_when_model_is_not_found() -> None:
    class FakeNoMatchingModelClient:
        def get_models(self):
            from app.models.schemas import ModelInfo

            return [ModelInfo(id="another-model", supports_vision=True)]

        def get_embeddings(self, texts, model=None):
            return [[0.0, 1.0]]

    store = SessionStore()
    session_id = store.create_session().session_id
    file_store = _build_file_store()
    session_dir = file_store.session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    image_path = session_dir / "img.png"
    image_path.write_bytes(_make_png_bytes())
    file_store.register_files(
        session_id,
        [
            StoredSessionFile(
                file_id="img-1",
                session_id=session_id,
                filename="img.png",
                content_type="image/png",
                size_bytes=image_path.stat().st_size,
                path=str(image_path),
            )
        ],
    )
    store.bind_file(session_id, "img-1")
    service = ChatService(
        settings=FakeSettings(),
        session_store=store,
        file_store=file_store,
        vector_store=SessionVectorStore(),
        vsellm_client=FakeNoMatchingModelClient(),
        settings_service=FakeSettingsService(),
    )

    messages = service.build_messages_payload(session_id=session_id, user_message="Опиши фото", file_ids=["img-1"])
    user_message = messages[-1]
    assert user_message["role"] == "user"
    assert isinstance(user_message["content"], list)
    assert user_message["content"][1]["type"] == "image_url"


def test_stream_chat_emits_thinking_events_when_provider_returns_reasoning_delta(monkeypatch) -> None:
    class FakeReasoningStreamResponse:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_lines(self):
            yield 'data: {"choices":[{"delta":{"reasoning_content":"шаг 1"}}]}'
            yield 'data: {"choices":[{"delta":{"reasoning_content":" шаг 2"}}]}'
            yield 'data: {"choices":[{"delta":{"content":"Ответ"}}]}'
            yield "data: [DONE]"

    monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: FakeReasoningStreamResponse())

    store = SessionStore()
    session_id = store.create_session().session_id
    service = ChatService(
        settings=FakeSettings(),
        session_store=store,
        file_store=_build_file_store(),
        vector_store=SessionVectorStore(),
        vsellm_client=VseLLMClient(FakeSettings()),
        settings_service=FakeSettingsService(),
    )

    payload = b"".join(service.stream_chat(session_id=session_id, user_message="Привет")).decode("utf-8")
    assert "event: thinking" in payload
    assert "шаг 1" in payload
    assert "шаг 2" in payload
    assert "event: token" in payload
    assert "Ответ" in payload
    assert payload.find("event: thinking") < payload.find("event: token")

    history = store.get_messages(session_id)
    assistant_messages = [item for item in history if item["role"] == "assistant"]
    assert assistant_messages == [{"role": "assistant", "content": "Ответ"}]


def test_stream_chat_falls_back_to_non_stream_with_reasoning_content(monkeypatch) -> None:
    class FakeStreamingUnsupportedResponse:
        status_code = 422

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"error":{"message":"Streaming is not supported for this model"}}'

        def iter_lines(self):
            return []

    def fake_post(*args, **kwargs):
        request = httpx.Request("POST", "https://api.vsellm.ru/v1/chat/completions")
        return httpx.Response(
            status_code=200,
            request=request,
            json={
                "choices": [
                    {
                        "message": {
                            "reasoning_content": "Размышляю об ответе.",
                            "content": "Финальный ответ.",
                        }
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            },
        )

    monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: FakeStreamingUnsupportedResponse())
    monkeypatch.setattr("httpx.post", fake_post)

    store = SessionStore()
    session_id = store.create_session().session_id
    service = ChatService(
        settings=FakeSettings(),
        session_store=store,
        file_store=_build_file_store(),
        vector_store=SessionVectorStore(),
        vsellm_client=VseLLMClient(FakeSettings()),
        settings_service=FakeSettingsService(),
    )

    payload = b"".join(service.stream_chat(session_id=session_id, user_message="Привет")).decode("utf-8")
    assert "event: thinking" in payload
    assert "Размышляю об ответе." in payload
    assert "event: token" in payload
    assert "Финальный ответ." in payload
    assert payload.find("event: thinking") < payload.find("event: token")

    history = store.get_messages(session_id)
    assistant_messages = [item for item in history if item["role"] == "assistant"]
    assert assistant_messages == [{"role": "assistant", "content": "Финальный ответ."}]


def test_stream_chat_uses_non_stream_for_reasoning_models_and_emits_thinking(monkeypatch) -> None:
    class ReasoningRuntimeSettings:
        system_prompt = "System prompt"
        selected_model = "deepseek/deepseek-r1-distill-llama-70b"

    class ReasoningSettingsService:
        def get_settings(self):
            return ReasoningRuntimeSettings()

    captured_payloads: list[dict] = []

    def fake_post(*args, **kwargs):
        captured_payloads.append(kwargs["json"])
        request = httpx.Request("POST", "https://api.vsellm.ru/v1/chat/completions")
        return httpx.Response(
            status_code=200,
            request=request,
            json={
                "choices": [
                    {
                        "message": {
                            "reasoning_content": "Я размышляю поэтапно об ответе." * 4,
                            "content": "Финальный ответ модели." * 4,
                        }
                    }
                ],
                "usage": {"prompt_tokens": 7, "completion_tokens": 11, "total_tokens": 18},
            },
        )

    def fake_stream(*args, **kwargs):
        raise AssertionError("httpx.stream must not be called for reasoning models")

    monkeypatch.setattr("httpx.post", fake_post)
    monkeypatch.setattr("httpx.stream", fake_stream)

    store = SessionStore()
    session_id = store.create_session().session_id
    service = ChatService(
        settings=FakeSettings(),
        session_store=store,
        file_store=_build_file_store(),
        vector_store=SessionVectorStore(),
        vsellm_client=VseLLMClient(FakeSettings()),
        settings_service=ReasoningSettingsService(),
    )

    payload = b"".join(service.stream_chat(session_id=session_id, user_message="Сколько 17*19?")).decode("utf-8")
    assert "event: thinking" in payload
    assert "Я размышляю поэтапно" in payload
    assert "event: token" in payload
    assert "Финальный ответ модели." in payload
    assert payload.find("event: thinking") < payload.find("event: token")

    history = store.get_messages(session_id)
    assistant_messages = [item for item in history if item["role"] == "assistant"]
    assert assistant_messages == [{"role": "assistant", "content": "Финальный ответ модели." * 4}]
    assert captured_payloads and captured_payloads[0]["stream"] is False
    assert captured_payloads[0]["model"] == "deepseek/deepseek-r1-distill-llama-70b"


def test_is_reasoning_model_heuristic() -> None:
    assert ChatService._is_reasoning_model("deepseek/deepseek-r1-distill-llama-70b") is True
    assert ChatService._is_reasoning_model("openai/o1-preview") is True
    assert ChatService._is_reasoning_model("openai/o3-deep-research") is True
    assert ChatService._is_reasoning_model("o1") is True
    assert ChatService._is_reasoning_model("o3-mini") is True
    assert ChatService._is_reasoning_model("gpt-5-mini") is False
    assert ChatService._is_reasoning_model("qwen/qwen3-max-thinking") is False
    assert ChatService._is_reasoning_model("") is False


def test_stream_chat_collects_usage_in_runtime_store(monkeypatch) -> None:
    usage_store.reset()

    class FakeStreamResponse:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"Привет"}}]}'
            yield 'data: {"usage":{"prompt_tokens":4,"completion_tokens":3,"total_tokens":7}}'
            yield "data: [DONE]"

    monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: FakeStreamResponse())

    store = SessionStore()
    session_id = store.create_session().session_id
    service = ChatService(
        settings=FakeSettings(),
        session_store=store,
        file_store=_build_file_store(),
        vector_store=SessionVectorStore(),
        vsellm_client=VseLLMClient(FakeSettings()),
        settings_service=FakeSettingsService(),
        usage_store=usage_store,
    )

    payload = b"".join(service.stream_chat(session_id=session_id, user_message="Привет")).decode("utf-8")
    assert "event: done" in payload
    collected = usage_store.get_chat_for_session(session_id)
    assert collected.prompt_tokens == 4
    assert collected.completion_tokens == 3
    assert collected.total_tokens == 7
    assert collected.requests_count == 1


def test_build_messages_payload_collects_embeddings_usage_for_retrieval() -> None:
    usage_store.reset()

    class FakeEmbeddingResult:
        vectors = [[1.0, 0.0]]
        usage = {"prompt_tokens": 6, "total_tokens": 6}

    class FakeEmbeddingsWithUsageClient:
        def get_embeddings_with_usage(self, texts, model=None):
            return FakeEmbeddingResult()

    store = SessionStore()
    vector_store = SessionVectorStore()
    session = store.create_session()
    session_id = session.session_id
    store.bind_file(session_id=session_id, file_id="file-1")
    vector_store.upsert_file_chunks(
        session_id=session_id,
        file_id="file-1",
        chunks=[
            StoredChunkVector(
                chunk_id="c1",
                file_id="file-1",
                filename="doc.pdf",
                text="Нужный фрагмент про договор.",
                embedding=[1.0, 0.0],
            )
        ],
    )

    service = ChatService(
        settings=FakeSettings(),
        session_store=store,
        file_store=_build_file_store(),
        vector_store=vector_store,
        vsellm_client=FakeEmbeddingsWithUsageClient(),
        settings_service=FakeSettingsService(),
        usage_store=usage_store,
    )
    messages = service.build_messages_payload(session_id=session_id, user_message="Что по договору?")
    assert messages[1]["role"] == "system"
    collected = usage_store.get_embeddings_for_session(session_id)
    assert collected.input_tokens == 6
    assert collected.total_tokens == 6
    assert collected.requests_count == 1

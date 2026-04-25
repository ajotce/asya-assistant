import io
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.chat_service import ChatService
from app.services.vsellm_client import VseLLMClient, VseLLMError
from app.storage.file_store import SessionFileStore, StoredSessionFile
from app.storage.session_store import SessionStore
from app.storage.vector_store import SessionVectorStore, StoredChunkVector


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


def test_stream_chat_endpoint_streams_events(monkeypatch) -> None:
    class FakeService:
        def stream_chat(self, session_id: str, user_message: str, file_ids=None):
            yield b'event: token\ndata: {"text":"Hi"}\n\n'
            yield b'event: done\ndata: {"usage":null}\n\n'

    monkeypatch.setattr("app.api.routes_chat.get_chat_service", lambda: FakeService())
    client = TestClient(app)
    response = client.post("/api/chat/stream", json={"session_id": "s-1", "message": "hello"})
    text = response.text
    assert response.status_code == 200
    assert "event: token" in text
    assert "event: done" in text


def test_status_mapper_for_rate_limit_error() -> None:
    try:
        ChatService._raise_for_status(429)
        assert False, "Expected VseLLMError"
    except VseLLMError as exc:
        assert exc.status_code == 429
        assert "ограничил частоту запросов" in exc.user_message


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

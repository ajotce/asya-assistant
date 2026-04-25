from fastapi.testclient import TestClient

from app.main import app
from app.services.chat_service import ChatService
from app.services.vsellm_client import VseLLMError
from app.storage.session_store import SessionStore


class FakeSettings:
    vsellm_api_key = "test-key"
    vsellm_base_url = "https://api.vsellm.ru/v1"
    default_chat_model = "openai/gpt-5"
    default_system_prompt = "System prompt"


def test_build_messages_payload_uses_system_prompt_and_session_context() -> None:
    store = SessionStore()
    store.append_message("s-1", "user", "old user")
    store.append_message("s-1", "assistant", "old assistant")
    service = ChatService(settings=FakeSettings(), session_store=store)

    messages = service.build_messages_payload(session_id="s-1", user_message="new message")

    assert messages[0] == {"role": "system", "content": "System prompt"}
    assert messages[1] == {"role": "user", "content": "old user"}
    assert messages[2] == {"role": "assistant", "content": "old assistant"}
    assert messages[3] == {"role": "user", "content": "new message"}


def test_stream_chat_returns_error_event_on_vsellm_validation_error() -> None:
    class NoKeySettings(FakeSettings):
        vsellm_api_key = ""

    service = ChatService(settings=NoKeySettings(), session_store=SessionStore())
    chunks = list(service.stream_chat(session_id="s-1", user_message="Hello"))
    payload = b"".join(chunks).decode("utf-8")

    assert "event: error" in payload
    assert "VseLLM API-ключ не настроен на backend." in payload


def test_stream_chat_endpoint_streams_events(monkeypatch) -> None:
    class FakeService:
        def stream_chat(self, session_id: str, user_message: str):
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

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import ModelInfo
from app.services.vsellm_client import VseLLMClient, VseLLMError


def test_get_models_returns_id_only_when_only_id_available(monkeypatch) -> None:
    class FakeClient:
        def get_models(self) -> list[ModelInfo]:
            return [ModelInfo(id="openai/gpt-5")]

    monkeypatch.setattr("app.api.routes_models.get_vsellm_client", lambda: FakeClient())

    response = TestClient(app).get("/api/models")
    assert response.status_code == 200
    assert response.json() == [{"id": "openai/gpt-5"}]


def test_get_models_maps_vsellm_error_to_http_error(monkeypatch) -> None:
    class FakeClient:
        def get_models(self) -> list[ModelInfo]:
            raise VseLLMError(status_code=429, user_message="Сервис VseLLM временно ограничил частоту запросов. Попробуйте позже.")

    monkeypatch.setattr("app.api.routes_models.get_vsellm_client", lambda: FakeClient())

    response = TestClient(app).get("/api/models")
    assert response.status_code == 429
    assert response.json()["detail"] == "Сервис VseLLM временно ограничил частоту запросов. Попробуйте позже."


def test_vsellm_client_normalizes_data_payload(monkeypatch) -> None:
    class FakeSettings:
        vsellm_api_key = "test-key"
        vsellm_base_url = "https://api.vsellm.ru/v1"

    def fake_get(*args, **kwargs):
        request = httpx.Request("GET", "https://api.vsellm.ru/v1/models")
        return httpx.Response(
            status_code=200,
            request=request,
            json={"data": [{"id": "openai/gpt-5"}, {"id": "model-2", "description": "Demo"}]},
        )

    monkeypatch.setattr("app.services.vsellm_client.httpx.get", fake_get)

    models = VseLLMClient(FakeSettings()).get_models()
    assert len(models) == 2
    assert models[0].id == "openai/gpt-5"
    assert models[0].description is None
    assert models[1].id == "model-2"
    assert models[1].description == "Demo"


def test_vsellm_client_handles_auth_error(monkeypatch) -> None:
    class FakeSettings:
        vsellm_api_key = "test-key"
        vsellm_base_url = "https://api.vsellm.ru/v1"

    def fake_get(*args, **kwargs):
        request = httpx.Request("GET", "https://api.vsellm.ru/v1/models")
        return httpx.Response(status_code=401, request=request, json={"error": "unauthorized"})

    monkeypatch.setattr("app.services.vsellm_client.httpx.get", fake_get)

    try:
        VseLLMClient(FakeSettings()).get_models()
        assert False, "Expected VseLLMError"
    except VseLLMError as exc:
        assert exc.status_code == 401
        assert "авторизации" in exc.user_message


def test_vsellm_client_normalizes_chat_and_stream_capabilities_from_explicit_fields() -> None:
    model = VseLLMClient._normalize_model(
        {
            "id": "model-chat",
            "supports_chat": True,
            "supports_stream": False,
            "supports_vision": True,
        }
    )
    assert model is not None
    assert model.supports_chat is True
    assert model.supports_stream is False
    assert model.supports_vision is True


def test_vsellm_client_marks_model_as_non_chat_when_capabilities_explicitly_disable_chat() -> None:
    model = VseLLMClient._normalize_model(
        {
            "id": "model-no-chat",
            "capabilities": {
                "chat_completions": False,
                "vision": True,
            },
        }
    )
    assert model is not None
    assert model.supports_chat is False
    assert model.supports_vision is True


def test_vsellm_client_detects_chat_support_from_endpoints() -> None:
    model = VseLLMClient._normalize_model(
        {
            "id": "model-endpoint-chat",
            "endpoints": ["/v1/chat/completions", "/v1/embeddings"],
        }
    )
    assert model is not None
    assert model.supports_chat is True

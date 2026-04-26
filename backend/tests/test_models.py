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


def test_is_likely_reasoning_model_matches_known_patterns() -> None:
    from app.services.vsellm_client import is_likely_reasoning_model

    assert is_likely_reasoning_model("qwen/qwen3-vl-235b-a22b-thinking") is True
    assert is_likely_reasoning_model("deepseek-r1-distill-llama-70b") is True
    assert is_likely_reasoning_model("openai/o3-deep-research") is True
    assert is_likely_reasoning_model("model-with-reasoning-in-name") is True
    assert is_likely_reasoning_model("gpt-5-mini") is False
    assert is_likely_reasoning_model("text-embedding-3-small") is False


def test_probe_reasoning_streaming_detects_reasoning_chunks(monkeypatch) -> None:
    class FakeStreamResponse:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_lines(self):
            yield 'data: {"choices":[{"delta":{"reasoning_content":"шаг"}}]}'
            yield 'data: {"choices":[{"delta":{"content":"ответ"}}]}'
            yield "data: [DONE]"

    monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: FakeStreamResponse())

    class FakeSettings:
        vsellm_api_key = "test-key"
        vsellm_base_url = "https://api.vsellm.ru/v1"

    result = VseLLMClient(FakeSettings()).probe_reasoning_streaming("some-thinking-model")
    assert result.streams_reasoning is True
    assert result.error is None


def test_probe_reasoning_streaming_returns_false_when_no_reasoning_chunks(monkeypatch) -> None:
    class FakeStreamResponse:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"ответ без размышлений"}}]}'
            yield "data: [DONE]"

    monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: FakeStreamResponse())

    class FakeSettings:
        vsellm_api_key = "test-key"
        vsellm_base_url = "https://api.vsellm.ru/v1"

    result = VseLLMClient(FakeSettings()).probe_reasoning_streaming("plain-model")
    assert result.streams_reasoning is False
    assert result.error is None


def test_probe_endpoint_uses_cache_and_filters_heuristic_candidates(monkeypatch) -> None:
    from app.services.vsellm_client import ReasoningProbeResult
    from app.storage.runtime import reasoning_probe_cache

    reasoning_probe_cache.reset()

    probe_calls: list[str] = []

    class FakeClient:
        def get_models(self) -> list[ModelInfo]:
            return [
                ModelInfo(id="gpt-5-mini"),
                ModelInfo(id="qwen/qwen3-vl-235b-a22b-thinking"),
                ModelInfo(id="deepseek-r1-distill-llama-70b"),
            ]

        def probe_reasoning_streaming(self, model_id: str, timeout: float = 15.0):
            from datetime import datetime, timezone

            probe_calls.append(model_id)
            return ReasoningProbeResult(
                model_id=model_id,
                streams_reasoning=model_id.endswith("thinking"),
                checked_at=datetime.now(timezone.utc),
            )

    monkeypatch.setattr("app.api.routes_models.get_vsellm_client", lambda: FakeClient())

    client = TestClient(app)
    response = client.post("/api/models/probe-reasoning", json={})
    assert response.status_code == 200
    body = response.json()
    ids = sorted(item["id"] for item in body["results"])
    assert ids == ["deepseek-r1-distill-llama-70b", "qwen/qwen3-vl-235b-a22b-thinking"]
    streams_for = {item["id"]: item["streams_reasoning"] for item in body["results"]}
    assert streams_for["qwen/qwen3-vl-235b-a22b-thinking"] is True
    assert streams_for["deepseek-r1-distill-llama-70b"] is False
    assert sorted(probe_calls) == ids

    probe_calls.clear()
    response2 = client.post("/api/models/probe-reasoning", json={})
    assert response2.status_code == 200
    assert probe_calls == []  # served from cache

    probe_calls.clear()
    response3 = client.post("/api/models/probe-reasoning", json={"force": True})
    assert response3.status_code == 200
    assert sorted(probe_calls) == ids  # forced refresh hits provider again

    cache_response = client.get("/api/models/reasoning-cache")
    assert cache_response.status_code == 200
    cache_ids = sorted(item["id"] for item in cache_response.json()["results"])
    assert cache_ids == ids


def test_probe_endpoint_accepts_explicit_model_ids(monkeypatch) -> None:
    from app.services.vsellm_client import ReasoningProbeResult
    from app.storage.runtime import reasoning_probe_cache

    reasoning_probe_cache.reset()

    class FakeClient:
        def get_models(self) -> list[ModelInfo]:
            raise AssertionError("get_models must not be called when ids are provided")

        def probe_reasoning_streaming(self, model_id: str, timeout: float = 15.0):
            from datetime import datetime, timezone

            return ReasoningProbeResult(
                model_id=model_id,
                streams_reasoning=False,
                checked_at=datetime.now(timezone.utc),
            )

    monkeypatch.setattr("app.api.routes_models.get_vsellm_client", lambda: FakeClient())

    response = TestClient(app).post(
        "/api/models/probe-reasoning",
        json={"model_ids": ["gpt-5-mini", "any-model"], "force": False},
    )
    assert response.status_code == 200
    ids = sorted(item["id"] for item in response.json()["results"])
    assert ids == ["any-model", "gpt-5-mini"]

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.models.schemas import (
    ModelInfo,
    ReasoningProbeItem,
    ReasoningProbeRequest,
    ReasoningProbeResponse,
)
from app.services.vsellm_client import (
    ReasoningProbeResult,
    VseLLMClient,
    VseLLMError,
    is_likely_reasoning_model,
)
from app.storage.runtime import reasoning_probe_cache

router = APIRouter(tags=["models"])

_PROBE_LIMIT = 10


def get_vsellm_client() -> VseLLMClient:
    return VseLLMClient(get_settings())


@router.get("/models", response_model=list[ModelInfo], response_model_exclude_none=True)
def get_models() -> list[ModelInfo]:
    client = get_vsellm_client()
    try:
        return client.get_models()
    except VseLLMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.user_message) from exc


@router.post("/models/probe-reasoning", response_model=ReasoningProbeResponse)
def probe_reasoning(request: ReasoningProbeRequest) -> ReasoningProbeResponse:
    client = get_vsellm_client()
    if request.model_ids:
        candidates = [model_id for model_id in request.model_ids if model_id.strip()]
    else:
        try:
            all_models = client.get_models()
        except VseLLMError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.user_message) from exc
        candidates = [model.id for model in all_models if is_likely_reasoning_model(model.id)]

    candidates = candidates[:_PROBE_LIMIT]
    results: list[ReasoningProbeResult] = []
    for model_id in candidates:
        cached = None if request.force else reasoning_probe_cache.get(model_id)
        if cached is not None:
            results.append(cached)
            continue
        result = client.probe_reasoning_streaming(model_id)
        reasoning_probe_cache.set(result)
        results.append(result)

    return ReasoningProbeResponse(results=[_to_item(result) for result in results])


@router.get("/models/reasoning-cache", response_model=ReasoningProbeResponse)
def get_reasoning_cache() -> ReasoningProbeResponse:
    fresh = reasoning_probe_cache.all_fresh()
    return ReasoningProbeResponse(results=[_to_item(result) for result in fresh])


def _to_item(result: ReasoningProbeResult) -> ReasoningProbeItem:
    return ReasoningProbeItem(
        id=result.model_id,
        streams_reasoning=result.streams_reasoning,
        checked_at=result.checked_at.isoformat(),
        error=result.error,
    )

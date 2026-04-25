from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.models.schemas import ModelInfo
from app.services.vsellm_client import VseLLMClient, VseLLMError

router = APIRouter(tags=["models"])


def get_vsellm_client() -> VseLLMClient:
    return VseLLMClient(get_settings())


@router.get("/models", response_model=list[ModelInfo], response_model_exclude_none=True)
def get_models() -> list[ModelInfo]:
    client = get_vsellm_client()
    try:
        return client.get_models()
    except VseLLMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.user_message) from exc

from typing import Optional

from pydantic import BaseModel


class VseLLMHealth(BaseModel):
    api_key_configured: bool
    base_url: str


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    vsellm: VseLLMHealth


class ModelInfo(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    context_window: Optional[int] = None
    input_price: Optional[float] = None
    output_price: Optional[float] = None
    supports_vision: Optional[bool] = None

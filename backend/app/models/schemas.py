from pydantic import BaseModel


class VseLLMHealth(BaseModel):
    api_key_configured: bool
    base_url: str


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    vsellm: VseLLMHealth

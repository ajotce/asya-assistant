from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class VseLLMHealth(BaseModel):
    api_key_configured: bool
    base_url: str
    reachable: Optional[bool] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    vsellm: VseLLMHealth
    model: "HealthModelInfo"
    files: "HealthFilesInfo"
    session: "HealthSessionInfo"
    last_error: Optional[str] = None


class HealthModelInfo(BaseModel):
    selected: str


class HealthFilesInfo(BaseModel):
    enabled: bool
    status: str


class HealthSessionInfo(BaseModel):
    enabled: bool
    active_sessions: int


class ModelInfo(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    context_window: Optional[int] = None
    input_price: Optional[float] = None
    output_price: Optional[float] = None
    supports_vision: Optional[bool] = None


class ChatStreamRequest(BaseModel):
    session_id: str
    message: str


class SessionCreateResponse(BaseModel):
    session_id: str
    created_at: str


class SessionStateResponse(BaseModel):
    session_id: str
    created_at: str
    message_count: int
    file_ids: list[str]


class SessionUploadedFileInfo(BaseModel):
    file_id: str
    filename: str
    content_type: str
    size_bytes: int


class SessionFilesUploadResponse(BaseModel):
    session_id: str
    files: list[SessionUploadedFileInfo]
    file_ids: list[str]


class SettingsResponse(BaseModel):
    assistant_name: str
    system_prompt: str
    selected_model: str
    api_key_configured: bool


class SettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assistant_name: str = Field(min_length=1, max_length=120)
    system_prompt: str = Field(min_length=1, max_length=12000)
    selected_model: str = Field(min_length=1, max_length=200)

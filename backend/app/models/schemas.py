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
    uptime_seconds: int
    vsellm: VseLLMHealth
    model: "HealthModelInfo"
    files: "HealthFilesInfo"
    embeddings: "HealthEmbeddingsInfo"
    storage: "HealthStorageInfo"
    session: "HealthSessionInfo"
    last_error: Optional[str] = None


class HealthModelInfo(BaseModel):
    selected: str


class HealthFilesInfo(BaseModel):
    enabled: bool
    status: str


class HealthEmbeddingsInfo(BaseModel):
    enabled: bool
    model: str
    status: str
    last_error: Optional[str] = None


class HealthStorageInfo(BaseModel):
    session_store: str
    file_store: str
    tmp_dir: str
    writable: bool


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
    supports_chat: Optional[bool] = None
    supports_stream: Optional[bool] = None
    supports_vision: Optional[bool] = None


class ReasoningProbeItem(BaseModel):
    id: str
    streams_reasoning: bool
    checked_at: str
    error: Optional[str] = None


class ReasoningProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_ids: Optional[list[str]] = None
    force: bool = False


class ReasoningProbeResponse(BaseModel):
    results: list[ReasoningProbeItem]


class ChatStreamRequest(BaseModel):
    session_id: str
    message: str
    file_ids: list[str] = Field(default_factory=list)


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


class ChatListItemResponse(BaseModel):
    id: str
    title: str
    kind: str
    is_archived: bool
    created_at: str
    updated_at: str
    message_count: int


class ChatCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)


class ChatRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)


class ChatMessageItemResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


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


class UsageTokensInfo(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    status: str
    note: Optional[str] = None


class UsageEmbeddingsInfo(BaseModel):
    input_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    status: str
    note: Optional[str] = None


class UsageCostInfo(BaseModel):
    currency: Optional[str] = None
    total_cost: Optional[float] = None
    status: str
    note: Optional[str] = None


class UsageRuntimeInfo(BaseModel):
    active_sessions: int
    selected_model: str
    embedding_model: str


class UsageOverviewResponse(BaseModel):
    chat: UsageTokensInfo
    embeddings: UsageEmbeddingsInfo
    cost: UsageCostInfo
    runtime: UsageRuntimeInfo


class UsageSessionRuntimeInfo(BaseModel):
    session_id: str
    created_at: str
    message_count: int
    user_messages: int
    assistant_messages: int
    file_count: int
    chunks_indexed: int


class UsageSessionResponse(BaseModel):
    chat: UsageTokensInfo
    embeddings: UsageEmbeddingsInfo
    cost: UsageCostInfo
    runtime: UsageSessionRuntimeInfo


class AuthRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=200)


class AuthLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)


class AuthUserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    status: str
    preferred_chat_id: Optional[str] = None


class AuthRegisterResponse(BaseModel):
    status: str
    user: Optional[AuthUserResponse] = None
    detail: Optional[str] = None


class AccessRequestSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=120)


class AccessRequestResponse(BaseModel):
    id: str
    email: str
    display_name: str
    status: str
    approved_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    created_at: str
    updated_at: str


class AccessRequestSubmitResponse(BaseModel):
    status: str
    request: AccessRequestResponse


class AccessRequestApproveResponse(BaseModel):
    status: str
    request: AccessRequestResponse
    user: AuthUserResponse

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
    space_id: Optional[str] = None
    is_archived: bool
    created_at: str
    updated_at: str
    message_count: int


class ChatCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    space_id: Optional[str] = Field(default=None, min_length=1, max_length=36)


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
    reason: str = Field(min_length=3, max_length=1000)


class AccessRequestResponse(BaseModel):
    id: str
    email: str
    display_name: str
    reason: str
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


class SpaceListItemResponse(BaseModel):
    id: str
    name: str
    is_default: bool
    is_admin_only: bool
    is_archived: bool
    created_at: str
    updated_at: str


class SpaceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)


class SpaceRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)


class SpaceMemorySettingsResponse(BaseModel):
    space_id: str
    memory_read_enabled: bool
    memory_write_enabled: bool
    behavior_rules_enabled: bool
    personality_overlay_enabled: bool
    created_at: str
    updated_at: str


class SpaceMemorySettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_read_enabled: bool
    memory_write_enabled: bool
    behavior_rules_enabled: bool
    personality_overlay_enabled: bool


class IntegrationConnectionResponse(BaseModel):
    provider: str
    status: str
    scopes: list[str]
    connected_at: Optional[str] = None
    last_refresh_at: Optional[str] = None
    last_sync_at: Optional[str] = None
    safe_error_metadata: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MemoryFactItemResponse(BaseModel):
    id: str
    key: str
    value: str
    status: str
    source: str
    space_id: Optional[str] = None
    created_at: str
    updated_at: str


class MemoryFactCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=4000)
    status: str = Field(min_length=1, max_length=32)
    source: str = Field(default="user", min_length=1, max_length=120)
    space_id: Optional[str] = Field(default=None, min_length=1, max_length=36)


class MemoryFactUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=4000)
    source: Optional[str] = Field(default=None, min_length=1, max_length=120)


class MemoryFactStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1, max_length=32)


class BehaviorRuleItemResponse(BaseModel):
    id: str
    title: str
    instruction: str
    scope: str
    strictness: str
    source: str
    status: str
    space_id: Optional[str] = None
    created_at: str
    updated_at: str


class BehaviorRuleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    instruction: str = Field(min_length=1, max_length=6000)
    scope: str = Field(min_length=1, max_length=32)
    strictness: str = Field(min_length=1, max_length=32)
    source: str = Field(min_length=1, max_length=32)
    status: str = Field(default="active", min_length=1, max_length=32)
    space_id: Optional[str] = Field(default=None, min_length=1, max_length=36)


class BehaviorRuleUpdateRequest(BehaviorRuleCreateRequest):
    pass


class MemoryEpisodeItemResponse(BaseModel):
    id: str
    chat_id: str
    summary: str
    status: str
    source: str
    space_id: Optional[str] = None
    created_at: str
    updated_at: str


class MemoryChangeItemResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    change_kind: str
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    space_id: Optional[str] = None
    created_at: str


class ActivityLogItemResponse(BaseModel):
    id: str
    event_type: str
    entity_type: str
    entity_id: str
    summary: str
    meta: Optional[dict] = None
    space_id: Optional[str] = None
    created_at: str


class MemorySnapshotCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=200)
    space_id: Optional[str] = Field(default=None, min_length=1, max_length=36)


class MemorySnapshotItemResponse(BaseModel):
    id: str
    label: str
    space_id: Optional[str] = None
    created_at: str
    updated_at: str


class MemorySnapshotSummaryResponse(MemorySnapshotItemResponse):
    facts_count: int
    rules_count: int
    episodes_count: int
    personality_profiles_count: int
    space_settings_count: int


class PersonalityProfileResponse(BaseModel):
    id: str
    scope: str
    space_id: Optional[str] = None
    name: str
    tone: str
    style_notes: str
    humor_level: int
    initiative_level: int
    can_gently_disagree: bool
    address_user_by_name: bool
    is_active: bool
    created_at: str
    updated_at: str


class PersonalityProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    tone: str = Field(min_length=1, max_length=120)
    style_notes: str = Field(default="", max_length=6000)
    humor_level: int = Field(default=1, ge=0, le=2)
    initiative_level: int = Field(default=1, ge=0, le=2)
    can_gently_disagree: bool = True
    address_user_by_name: bool = True
    is_active: bool = True

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
    kind: str = Field(default="regular", min_length=1, max_length=64)


class ChatRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)


class ChatMessageItemResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class DiarySettingsResponse(BaseModel):
    briefing_enabled: bool
    search_enabled: bool
    memories_enabled: bool
    evening_prompt_enabled: bool
    created_at: str
    updated_at: str


class DiarySettingsPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    briefing_enabled: bool
    search_enabled: bool
    memories_enabled: bool
    evening_prompt_enabled: bool


class DiaryEntryItemResponse(BaseModel):
    id: str
    title: str
    content: str
    transcript: str
    topics: list[str]
    decisions: list[str]
    mentions: list[str]
    source_audio_path: Optional[str] = None
    processing_status: str
    processing_error: Optional[str] = None
    created_at: str
    updated_at: str


class DiaryEntryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="Запись дневника", min_length=1, max_length=255)
    content: str = Field(default="", max_length=20000)


class DiaryEntryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    content: str = Field(default="", max_length=20000)


class ObservationRuleItemResponse(BaseModel):
    id: str
    detector: str
    enabled: bool
    threshold_config: dict
    description: Optional[str] = None
    created_at: str
    updated_at: str


class ObservationRuleUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detector: str = Field(min_length=1, max_length=64)
    enabled: bool = True
    threshold_config: dict = Field(default_factory=dict)
    description: Optional[str] = Field(default=None, max_length=2000)


class ObservationItemResponse(BaseModel):
    id: str
    detector: str
    title: str
    details: str
    severity: str
    status: str
    context_payload: dict
    observed_at: str
    postponed_until: Optional[str] = None
    created_at: str
    updated_at: str


class ObservationPostponeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    postponed_until: str


class SettingsResponse(BaseModel):
    assistant_name: str
    system_prompt: str
    selected_model: str
    default_storage_provider: str
    default_storage_folders: dict[str, str]
    api_key_configured: bool


class SettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assistant_name: str = Field(min_length=1, max_length=120)
    system_prompt: str = Field(min_length=1, max_length=12000)
    selected_model: str = Field(min_length=1, max_length=200)
    default_storage_provider: str = Field(min_length=1, max_length=64)
    default_storage_folders: dict[str, str] = Field(default_factory=dict)


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


class DocumentTemplateFieldSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=255)
    type: str = Field(min_length=1, max_length=64)
    required: bool = False
    validation: Optional[str] = Field(default=None, max_length=1024)


class DocumentTemplateOutputSettingsSchema(BaseModel):
    model_config = ConfigDict(extra="allow")


class DocumentTemplateItemResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    provider: str
    file_id: str
    fields: list[DocumentTemplateFieldSchema]
    output_settings: dict
    created_at: str
    updated_at: str


class DocumentTemplateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    provider: str = Field(min_length=1, max_length=64)
    file_id: str = Field(min_length=1, max_length=512)
    fields: list[DocumentTemplateFieldSchema] = Field(default_factory=list)
    output_settings: dict = Field(default_factory=dict)


class DocumentTemplateUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    provider: str = Field(min_length=1, max_length=64)
    file_id: str = Field(min_length=1, max_length=512)
    fields: list[DocumentTemplateFieldSchema] = Field(default_factory=list)
    output_settings: dict = Field(default_factory=dict)


class DocumentTemplateFillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: dict[str, str] = Field(default_factory=dict)
    preview_only: bool = False


class DocumentTemplateFillPreviewResponse(BaseModel):
    missing_fields: list[str] = Field(default_factory=list)
    invalid_fields: dict[str, str] = Field(default_factory=dict)
    ready: bool


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
    setup_link: str


class AuthSetupPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=24, max_length=255)
    password: str = Field(min_length=8, max_length=200)


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


class StorageProviderInfoResponse(BaseModel):
    provider: str
    supports_search: bool
    supports_move: bool
    supports_share: bool


class StorageItemResponse(BaseModel):
    provider: str
    id: str
    name: str
    path: str
    kind: str
    size_bytes: Optional[int] = None
    modified_at: Optional[str] = None
    mime_type: Optional[str] = None


class TelegramLinkTokenResponse(BaseModel):
    one_time_token: str
    expires_at: str
    bot_start_url: str


class TelegramLinkStatusResponse(BaseModel):
    is_linked: bool
    telegram_user_id: Optional[str] = None
    telegram_username: Optional[str] = None
    telegram_chat_id: Optional[str] = None


class TelegramUnlinkResponse(BaseModel):
    status: str
    unlinked: bool


class VoiceSettingsResponse(BaseModel):
    assistant_name: str
    voice_gender: str
    stt_provider: str
    tts_provider: str
    tts_enabled: bool


class VoiceSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assistant_name: str = Field(min_length=1, max_length=120)
    voice_gender: str = Field(min_length=1, max_length=16)
    stt_provider: str = Field(min_length=1, max_length=64)
    tts_provider: str = Field(min_length=1, max_length=64)
    tts_enabled: bool


class VoiceSTTResponse(BaseModel):
    text: str
    provider: str


class VoiceTTSRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=12000)


class VoiceTTSResponse(BaseModel):
    provider: str
    mime_type: str


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


class ActionEventItemResponse(BaseModel):
    id: str
    provider: str
    operation: str
    target_id: Optional[str] = None
    reversible: bool
    rollback_status: str
    rollback_strategy: Optional[str] = None
    rollback_deadline: Optional[str] = None
    rollback_notes: Optional[str] = None
    previous_state: Optional[dict] = None
    safe_metadata: Optional[dict] = None
    created_at: str
    updated_at: str


class RollbackPreviewResponse(BaseModel):
    action_event_id: str
    provider: str
    operation: str
    target_id: Optional[str] = None
    reversible: bool
    rollback_strategy: Optional[str] = None
    rollback_deadline: Optional[str] = None
    rollback_notes: Optional[str] = None
    previous_state: Optional[dict] = None
    safe_metadata: Optional[dict] = None


class RollbackExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: bool = False


class RollbackExecuteResponse(BaseModel):
    action_event_id: str
    status: str
    message: str


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


class DocumentFilePayload(BaseModel):
    filename: str
    content_type: str
    content_base64: str


class DocumentFillResponse(BaseModel):
    output: str
    files: list[DocumentFilePayload]


class DocumentConvertResponse(BaseModel):
    file: DocumentFilePayload


class BriefingSettingsResponse(BaseModel):
    morning_enabled: bool
    evening_enabled: bool
    delivery_in_app: bool
    delivery_telegram: bool
    created_at: str
    updated_at: str


class BriefingSettingsPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    morning_enabled: bool
    evening_enabled: bool
    delivery_in_app: bool
    delivery_telegram: bool


class BriefingGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(pattern="^(morning|evening)$")


class BriefingArchiveItemResponse(BaseModel):
    id: str
    kind: str
    title: str
    delivered_in_app: bool
    delivered_telegram: bool
    created_at: str


class BriefingItemResponse(BaseModel):
    id: str
    kind: str
    title: str
    content_markdown: str
    delivered_in_app: bool
    delivered_telegram: bool
    created_at: str
    updated_at: str

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  uptime_seconds: number;
  vsellm: {
    api_key_configured: boolean;
    base_url: string;
    reachable?: boolean | null;
  };
  model: {
    selected: string;
  };
  files: {
    enabled: boolean;
    status: string;
  };
  embeddings: {
    enabled: boolean;
    model: string;
    status: string;
    last_error?: string | null;
  };
  storage: {
    session_store: string;
    file_store: string;
    tmp_dir: string;
    writable: boolean;
  };
  session: {
    enabled: boolean;
    active_sessions: number;
  };
  last_error?: string | null;
}

export interface SettingsResponse {
  assistant_name: string;
  system_prompt: string;
  selected_model: string;
  api_key_configured: boolean;
}

export interface SettingsUpdateRequest {
  assistant_name: string;
  system_prompt: string;
  selected_model: string;
}

export interface ReasoningProbeItem {
  id: string;
  streams_reasoning: boolean;
  checked_at: string;
  error?: string | null;
}

export interface ReasoningProbeResponse {
  results: ReasoningProbeItem[];
}

export interface ReasoningProbeRequest {
  model_ids?: string[];
  force?: boolean;
}

export interface ModelInfo {
  id: string;
  name?: string;
  description?: string;
  context_window?: number;
  input_price?: number;
  output_price?: number;
  supports_chat?: boolean;
  supports_stream?: boolean;
  supports_vision?: boolean;
}

export interface SessionCreateResponse {
  session_id: string;
  created_at: string;
}

export interface SessionStateResponse {
  session_id: string;
  created_at: string;
  message_count: number;
  file_ids: string[];
}

export interface ChatStreamRequest {
  session_id: string;
  message: string;
  file_ids?: string[];
}

export interface ChatListItem {
  id: string;
  title: string;
  kind: string;
  space_id?: string | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatCreateRequest {
  title: string;
  space_id?: string | null;
}

export interface ChatRenameRequest {
  title: string;
}

export interface ChatMessageItem {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

export type ChatStreamEvent =
  | { event: "token"; data: { text: string } }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: { usage: unknown } };

export interface SessionUploadedFileInfo {
  file_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
}

export interface SessionFilesUploadResponse {
  session_id: string;
  files: SessionUploadedFileInfo[];
  file_ids: string[];
}

export interface UsageOverviewResponse {
  chat: {
    prompt_tokens?: number | null;
    completion_tokens?: number | null;
    total_tokens?: number | null;
    status: string;
    note?: string | null;
  };
  embeddings: {
    input_tokens?: number | null;
    total_tokens?: number | null;
    status: string;
    note?: string | null;
  };
  cost: {
    currency?: string | null;
    total_cost?: number | null;
    status: string;
    note?: string | null;
  };
  runtime: {
    active_sessions: number;
    selected_model: string;
    embedding_model: string;
  };
}

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: string;
  status: string;
  preferred_chat_id?: string | null;
}

export interface AuthLoginRequest {
  email: string;
  password: string;
}

export interface AuthRegisterRequest {
  email: string;
  display_name: string;
  password: string;
}

export interface AuthRegisterResponse {
  status: string;
  user?: AuthUser | null;
  detail?: string | null;
}

export interface AuthSetupPasswordRequest {
  token: string;
  password: string;
}

export interface AccessRequestSubmitRequest {
  email: string;
  display_name: string;
  reason: string;
}

export interface AccessRequestResponse {
  id: string;
  email: string;
  display_name: string;
  reason: string;
  status: string;
  approved_by?: string | null;
  reviewed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccessRequestSubmitResponse {
  status: string;
  request: AccessRequestResponse;
}

export interface AccessRequestApproveResponse {
  status: string;
  request: AccessRequestResponse;
  user: AuthUser;
  setup_link: string;
}

export interface SpaceListItem {
  id: string;
  name: string;
  is_default: boolean;
  is_admin_only: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface SpaceCreateRequest {
  name: string;
}

export interface SpaceRenameRequest {
  name: string;
}

export interface SpaceMemorySettingsResponse {
  space_id: string;
  memory_read_enabled: boolean;
  memory_write_enabled: boolean;
  behavior_rules_enabled: boolean;
  personality_overlay_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface SpaceMemorySettingsUpdateRequest {
  memory_read_enabled: boolean;
  memory_write_enabled: boolean;
  behavior_rules_enabled: boolean;
  personality_overlay_enabled: boolean;
}

export interface MemoryFactItem {
  id: string;
  key: string;
  value: string;
  status: string;
  source: string;
  space_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemoryFactCreateRequest {
  key: string;
  value: string;
  status: string;
  source: string;
  space_id?: string | null;
}

export interface MemoryFactUpdateRequest {
  key: string;
  value: string;
  source?: string;
}

export interface MemoryFactStatusUpdateRequest {
  status: string;
}

export interface BehaviorRuleItem {
  id: string;
  title: string;
  instruction: string;
  scope: string;
  strictness: string;
  source: string;
  status: string;
  space_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BehaviorRuleCreateRequest {
  title: string;
  instruction: string;
  scope: string;
  strictness: string;
  source: string;
  status: string;
  space_id?: string | null;
}

export interface BehaviorRuleUpdateRequest {
  title: string;
  instruction: string;
  scope: string;
  strictness: string;
  source: string;
  status: string;
  space_id?: string | null;
}

export interface MemoryEpisodeItem {
  id: string;
  chat_id: string;
  summary: string;
  status: string;
  source: string;
  space_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PersonalityProfile {
  id: string;
  scope: string;
  space_id?: string | null;
  name: string;
  tone: string;
  style_notes: string;
  humor_level: number;
  initiative_level: number;
  can_gently_disagree: boolean;
  address_user_by_name: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PersonalityProfileUpdateRequest {
  name: string;
  tone: string;
  style_notes: string;
  humor_level: number;
  initiative_level: number;
  can_gently_disagree: boolean;
  address_user_by_name: boolean;
  is_active: boolean;
}

export interface ActivityLogItem {
  id: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  summary: string;
  meta?: Record<string, unknown> | null;
  space_id?: string | null;
  created_at: string;
}

export interface ActivityLogListRequest {
  limit?: number;
  event_type?: string;
  entity_type?: string;
  space_id?: string;
  date_from?: string;
  date_to?: string;
}

export interface MemorySnapshotCreateRequest {
  label: string;
  space_id?: string | null;
}

export interface MemorySnapshotItem {
  id: string;
  label: string;
  space_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemorySnapshotSummary extends MemorySnapshotItem {
  facts_count: number;
  rules_count: number;
  episodes_count: number;
  personality_profiles_count: number;
  space_settings_count: number;
}

export interface DiarySettingsResponse {
  briefing_enabled: boolean;
  search_enabled: boolean;
  memories_enabled: boolean;
  evening_prompt_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface DiarySettingsPatchRequest {
  briefing_enabled: boolean;
  search_enabled: boolean;
  memories_enabled: boolean;
  evening_prompt_enabled: boolean;
}

export interface DiaryEntryItem {
  id: string;
  title: string;
  content: string;
  transcript: string;
  topics: string[];
  decisions: string[];
  mentions: string[];
  source_audio_path?: string | null;
  processing_status: string;
  processing_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DiaryEntryCreateRequest {
  title?: string;
  content?: string;
}

export interface DiaryEntryUpdateRequest {
  title: string;
  content: string;
}

export interface ObservationRuleItem {
  id: string;
  detector: string;
  enabled: boolean;
  threshold_config: Record<string, unknown>;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ObservationRuleUpsertRequest {
  detector: string;
  enabled: boolean;
  threshold_config?: Record<string, unknown>;
  description?: string | null;
}

export interface ObservationItem {
  id: string;
  detector: string;
  title: string;
  details: string;
  severity: string;
  status: string;
  context_payload: Record<string, unknown>;
  observed_at: string;
  postponed_until?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ObservationPostponeRequest {
  postponed_until: string;
}

export interface VoiceSettings {
  assistant_name: string;
  voice_gender: string;
  stt_provider: string;
  tts_provider: string;
  tts_enabled: boolean;
}

export interface VoiceSettingsUpdateRequest {
  assistant_name: string;
  voice_gender: string;
  stt_provider: string;
  tts_provider: string;
  tts_enabled: boolean;
}

export interface VoiceSTTResponse {
  text: string;
  provider: string;
}

export interface VoiceTTSRequest {
  text: string;
}

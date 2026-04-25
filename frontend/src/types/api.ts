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

export interface ModelInfo {
  id: string;
  name?: string;
  description?: string;
  context_window?: number;
  input_price?: number;
  output_price?: number;
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

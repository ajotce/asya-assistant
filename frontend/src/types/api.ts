export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  vsellm: {
    api_key_configured: boolean;
    base_url: string;
  };
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

export type ChatStreamEvent =
  | { event: "token"; data: { text: string } }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: { usage: unknown } };

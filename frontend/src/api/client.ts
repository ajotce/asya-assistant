import type {
  AccessRequestApproveResponse,
  AccessRequestResponse,
  ActivityLogItem,
  ActivityLogListRequest,
  AccessRequestSubmitRequest,
  AccessRequestSubmitResponse,
  AuthLoginRequest,
  AuthRegisterRequest,
  AuthRegisterResponse,
  AuthUser,
  ChatCreateRequest,
  ChatListItem,
  ChatMessageItem,
  ChatRenameRequest,
  ChatStreamRequest,
  DiaryEntryItem,
  DiaryEntryCreateRequest,
  DiaryEntryUpdateRequest,
  DiarySettingsPatchRequest,
  DiarySettingsResponse,
  ObservationItem,
  ObservationPostponeRequest,
  ObservationRuleItem,
  ObservationRuleUpsertRequest,
  BehaviorRuleCreateRequest,
  BehaviorRuleItem,
  BehaviorRuleUpdateRequest,
  HealthResponse,
  MemoryEpisodeItem,
  MemoryFactCreateRequest,
  MemoryFactItem,
  MemoryFactStatusUpdateRequest,
  MemoryFactUpdateRequest,
  MemorySnapshotCreateRequest,
  MemorySnapshotItem,
  MemorySnapshotSummary,
  ModelInfo,
  PersonalityProfile,
  PersonalityProfileUpdateRequest,
  ReasoningProbeRequest,
  ReasoningProbeResponse,
  SessionCreateResponse,
  SessionFilesUploadResponse,
  SettingsResponse,
  SettingsUpdateRequest,
  SpaceCreateRequest,
  SpaceListItem,
  SpaceMemorySettingsResponse,
  SpaceMemorySettingsUpdateRequest,
  SpaceRenameRequest,
  UsageOverviewResponse,
  VoiceSettings,
  VoiceSettingsUpdateRequest,
  VoiceSTTResponse,
} from "../types/api";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, `Ошибка запроса (${response.status})`));
  }

  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/health");
}

export function getUsage(): Promise<UsageOverviewResponse> {
  return apiFetch<UsageOverviewResponse>("/api/usage");
}

export function getModels(): Promise<ModelInfo[]> {
  return apiFetch<ModelInfo[]>("/api/models");
}

export function getReasoningCache(): Promise<ReasoningProbeResponse> {
  return apiFetch<ReasoningProbeResponse>("/api/models/reasoning-cache");
}

export function probeReasoningModels(body: ReasoningProbeRequest = {}): Promise<ReasoningProbeResponse> {
  return apiFetch<ReasoningProbeResponse>("/api/models/probe-reasoning", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getSettings(): Promise<SettingsResponse> {
  return apiFetch<SettingsResponse>("/api/settings");
}

export function updateSettings(body: SettingsUpdateRequest): Promise<SettingsResponse> {
  return apiFetch<SettingsResponse>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function createSession(): Promise<SessionCreateResponse> {
  return apiFetch<SessionCreateResponse>("/api/session", {
    method: "POST",
  });
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`/api/session/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, `Ошибка удаления сессии (${response.status})`));
  }
}

export async function uploadSessionFiles(sessionId: string, files: File[]): Promise<SessionFilesUploadResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  const response = await fetch(`/api/session/${encodeURIComponent(sessionId)}/files`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, `Ошибка загрузки файлов (${response.status})`));
  }
  return (await response.json()) as SessionFilesUploadResponse;
}

interface StreamHandlers {
  onToken: (text: string) => void;
  onThinking?: (text: string) => void;
  onError: (message: string) => void;
  onDone: () => void;
}

export async function streamChat(request: ChatStreamRequest, handlers: StreamHandlers): Promise<void> {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok || !response.body) {
    throw new Error(await extractErrorMessage(response, `Ошибка запроса (${response.status})`));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      parseSseEvent(rawEvent, handlers);
      boundary = buffer.indexOf("\n\n");
    }
  }
}

export function listChats(): Promise<ChatListItem[]> {
  return apiFetch<ChatListItem[]>("/api/chats");
}

export function createChat(body: ChatCreateRequest): Promise<ChatListItem> {
  return apiFetch<ChatListItem>("/api/chats", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function renameChat(chatId: string, body: ChatRenameRequest): Promise<ChatListItem> {
  return apiFetch<ChatListItem>(`/api/chats/${encodeURIComponent(chatId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function archiveChat(chatId: string): Promise<ChatListItem> {
  return apiFetch<ChatListItem>(`/api/chats/${encodeURIComponent(chatId)}/archive`, {
    method: "POST",
  });
}

export async function deleteChat(chatId: string): Promise<void> {
  const response = await fetch(`/api/chats/${encodeURIComponent(chatId)}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, `Ошибка удаления чата (${response.status})`));
  }
}

export function getChatMessages(chatId: string): Promise<ChatMessageItem[]> {
  return apiFetch<ChatMessageItem[]>(`/api/chats/${encodeURIComponent(chatId)}/messages`);
}

export function listSpaces(): Promise<SpaceListItem[]> {
  return apiFetch<SpaceListItem[]>("/api/spaces");
}

export function createSpace(body: SpaceCreateRequest): Promise<SpaceListItem> {
  return apiFetch<SpaceListItem>("/api/spaces", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function renameSpace(spaceId: string, body: SpaceRenameRequest): Promise<SpaceListItem> {
  return apiFetch<SpaceListItem>(`/api/spaces/${encodeURIComponent(spaceId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function archiveSpace(spaceId: string): Promise<SpaceListItem> {
  return apiFetch<SpaceListItem>(`/api/spaces/${encodeURIComponent(spaceId)}/archive`, {
    method: "POST",
  });
}

export function getSpaceSettings(spaceId: string): Promise<SpaceMemorySettingsResponse> {
  return apiFetch<SpaceMemorySettingsResponse>(`/api/spaces/${encodeURIComponent(spaceId)}/settings`);
}

export function updateSpaceSettings(
  spaceId: string,
  body: SpaceMemorySettingsUpdateRequest
): Promise<SpaceMemorySettingsResponse> {
  return apiFetch<SpaceMemorySettingsResponse>(`/api/spaces/${encodeURIComponent(spaceId)}/settings`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function listMemoryFacts(activeOnly = true): Promise<MemoryFactItem[]> {
  return apiFetch<MemoryFactItem[]>(`/api/memory/facts?active_only=${activeOnly ? "true" : "false"}`);
}

export function createMemoryFact(body: MemoryFactCreateRequest): Promise<MemoryFactItem> {
  return apiFetch<MemoryFactItem>("/api/memory/facts", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateMemoryFact(factId: string, body: MemoryFactUpdateRequest): Promise<MemoryFactItem> {
  return apiFetch<MemoryFactItem>(`/api/memory/facts/${encodeURIComponent(factId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function updateMemoryFactStatus(factId: string, body: MemoryFactStatusUpdateRequest): Promise<MemoryFactItem> {
  return apiFetch<MemoryFactItem>(`/api/memory/facts/${encodeURIComponent(factId)}/status`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function forbidMemoryFact(factId: string): Promise<MemoryFactItem> {
  return apiFetch<MemoryFactItem>(`/api/memory/facts/${encodeURIComponent(factId)}/forbid`, {
    method: "POST",
  });
}

export function listMemoryRules(activeOnly = false): Promise<BehaviorRuleItem[]> {
  return apiFetch<BehaviorRuleItem[]>(`/api/memory/rules?active_only=${activeOnly ? "true" : "false"}`);
}

export function createMemoryRule(body: BehaviorRuleCreateRequest): Promise<BehaviorRuleItem> {
  return apiFetch<BehaviorRuleItem>("/api/memory/rules", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateMemoryRule(ruleId: string, body: BehaviorRuleUpdateRequest): Promise<BehaviorRuleItem> {
  return apiFetch<BehaviorRuleItem>(`/api/memory/rules/${encodeURIComponent(ruleId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function disableMemoryRule(ruleId: string): Promise<BehaviorRuleItem> {
  return apiFetch<BehaviorRuleItem>(`/api/memory/rules/${encodeURIComponent(ruleId)}/disable`, {
    method: "POST",
  });
}

export function listMemoryEpisodes(activeOnly = true): Promise<MemoryEpisodeItem[]> {
  return apiFetch<MemoryEpisodeItem[]>(`/api/memory/episodes?active_only=${activeOnly ? "true" : "false"}`);
}

export function getPersonalityProfile(): Promise<PersonalityProfile> {
  return apiFetch<PersonalityProfile>("/api/personality");
}

export function updatePersonalityProfile(body: PersonalityProfileUpdateRequest): Promise<PersonalityProfile> {
  return apiFetch<PersonalityProfile>("/api/personality", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function listActivityLog(filters: ActivityLogListRequest = {}): Promise<ActivityLogItem[]> {
  const params = new URLSearchParams();
  if (filters.limit !== undefined) {
    params.set("limit", String(filters.limit));
  }
  if (filters.event_type) {
    params.set("event_type", filters.event_type);
  }
  if (filters.entity_type) {
    params.set("entity_type", filters.entity_type);
  }
  if (filters.space_id) {
    params.set("space_id", filters.space_id);
  }
  if (filters.date_from) {
    params.set("date_from", filters.date_from);
  }
  if (filters.date_to) {
    params.set("date_to", filters.date_to);
  }
  const query = params.toString();
  const path = query ? `/api/activity-log?${query}` : "/api/activity-log";
  return apiFetch<ActivityLogItem[]>(path);
}

export function createMemorySnapshot(body: MemorySnapshotCreateRequest): Promise<MemorySnapshotItem> {
  return apiFetch<MemorySnapshotItem>("/api/memory/snapshots", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listMemorySnapshots(spaceId?: string): Promise<MemorySnapshotItem[]> {
  const query = spaceId ? `?space_id=${encodeURIComponent(spaceId)}` : "";
  return apiFetch<MemorySnapshotItem[]>(`/api/memory/snapshots${query}`);
}

export function getMemorySnapshotSummary(snapshotId: string): Promise<MemorySnapshotSummary> {
  return apiFetch<MemorySnapshotSummary>(`/api/memory/snapshots/${encodeURIComponent(snapshotId)}`);
}

export function rollbackMemorySnapshot(snapshotId: string): Promise<MemorySnapshotItem> {
  return apiFetch<MemorySnapshotItem>(`/api/memory/snapshots/${encodeURIComponent(snapshotId)}/rollback`, {
    method: "POST",
  });
}

export function authMe(): Promise<AuthUser> {
  return apiFetch<AuthUser>("/api/auth/me");
}

export function authLogin(body: AuthLoginRequest): Promise<AuthUser> {
  return apiFetch<AuthUser>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function authLogout(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/api/auth/logout", {
    method: "POST",
  });
}

export function authRegister(body: AuthRegisterRequest): Promise<AuthRegisterResponse> {
  return apiFetch<AuthRegisterResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function submitAccessRequest(body: AccessRequestSubmitRequest): Promise<AccessRequestSubmitResponse> {
  return apiFetch<AccessRequestSubmitResponse>("/api/access-requests", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listAdminAccessRequests(): Promise<AccessRequestResponse[]> {
  return apiFetch<AccessRequestResponse[]>("/api/admin/access-requests");
}

export function approveAdminAccessRequest(requestId: string): Promise<AccessRequestApproveResponse> {
  return apiFetch<AccessRequestApproveResponse>(`/api/admin/access-requests/${encodeURIComponent(requestId)}/approve`, {
    method: "POST",
  });
}

export function rejectAdminAccessRequest(requestId: string): Promise<AccessRequestSubmitResponse> {
  return apiFetch<AccessRequestSubmitResponse>(`/api/admin/access-requests/${encodeURIComponent(requestId)}/reject`, {
    method: "POST",
  });
}

async function extractErrorMessage(response: Response, fallbackMessage: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string; message?: string };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
    if (typeof payload.message === "string" && payload.message.trim()) {
      return payload.message;
    }
  } catch {
    return fallbackMessage;
  }
  return fallbackMessage;
}

export function getVoiceSettings(): Promise<VoiceSettings> {
  return apiFetch<VoiceSettings>("/api/voice/settings");
}

export function updateVoiceSettings(body: VoiceSettingsUpdateRequest): Promise<VoiceSettings> {
  return apiFetch<VoiceSettings>("/api/voice/settings", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function sendVoiceSTT(audioBlob: Blob): Promise<VoiceSTTResponse> {
  const response = await fetch("/api/voice/stt", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "audio/webm" },
    body: audioBlob,
  });
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, "Ошибка распознавания речи"));
  }
  return (await response.json()) as VoiceSTTResponse;
}

export async function synthesizeVoiceText(body: { text: string }): Promise<ArrayBuffer> {
  const response = await fetch("/api/voice/tts", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, "Ошибка синтеза речи"));
  }
  return response.arrayBuffer();
}

export interface TelegramLinkTokenResponse {
  one_time_token: string;
  expires_at: string;
  bot_start_url: string;
}

export interface TelegramLinkStatusResponse {
  is_linked: boolean;
  telegram_user_id?: string | null;
  telegram_username?: string | null;
  telegram_chat_id?: string | null;
}

export function getTelegramStatus(): Promise<TelegramLinkStatusResponse> {
  return apiFetch<TelegramLinkStatusResponse>("/api/integrations/telegram/status");
}

export function createTelegramLinkToken(): Promise<TelegramLinkTokenResponse> {
  return apiFetch<TelegramLinkTokenResponse>("/api/integrations/telegram/link-token", {
    method: "POST",
  });
}

export function unlinkTelegram(): Promise<{ status: string; unlinked: boolean }> {
  return apiFetch<{ status: string; unlinked: boolean }>("/api/integrations/telegram/unlink", {
    method: "POST",
  });
}

function parseSseEvent(rawEvent: string, handlers: StreamHandlers) {
  const lines = rawEvent.split("\n");
  let eventName = "";
  let dataValue = "";

  for (const line of lines) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataValue += line.slice("data:".length).trim();
    }
  }

  if (!eventName || !dataValue) {
    return;
  }

  try {
    const payload = JSON.parse(dataValue) as { text?: string; message?: string };
    if (eventName === "token" && typeof payload.text === "string") {
      handlers.onToken(payload.text);
      return;
    }
    if (eventName === "thinking" && typeof payload.text === "string") {
      handlers.onThinking?.(payload.text);
      return;
    }
    if (eventName === "error" && typeof payload.message === "string") {
      handlers.onError(payload.message);
      return;
    }
    if (eventName === "done") {
      handlers.onDone();
    }
  } catch {
    if (eventName === "done") {
      handlers.onDone();
    }
  }
}

export function getDiarySettings(): Promise<DiarySettingsResponse> {
  return apiFetch<DiarySettingsResponse>("/api/diary/settings");
}

export function patchDiarySettings(body: DiarySettingsPatchRequest): Promise<DiarySettingsResponse> {
  return apiFetch<DiarySettingsResponse>("/api/diary/settings", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function listDiaryEntries(query?: string, limit?: number): Promise<DiaryEntryItem[]> {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (limit !== undefined) params.set("limit", String(limit));
  const qs = params.toString();
  return apiFetch<DiaryEntryItem[]>(`/api/diary/entries${qs ? `?${qs}` : ""}`);
}

export function createDiaryEntry(body: DiaryEntryCreateRequest): Promise<DiaryEntryItem> {
  return apiFetch<DiaryEntryItem>("/api/diary/entries", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function createDiaryEntryAudio(
  audio: Blob,
  title?: string,
  content?: string,
): Promise<DiaryEntryItem> {
  const formData = new FormData();
  formData.append("audio", audio, "entry.webm");
  formData.append("title", title || "Голосовая запись");
  formData.append("content", content || "");
  const response = await fetch("/api/diary/entries/audio", {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, `Ошибка загрузки аудио (${response.status})`));
  }
  return (await response.json()) as DiaryEntryItem;
}

export function getDiaryEntry(entryId: string): Promise<DiaryEntryItem> {
  return apiFetch<DiaryEntryItem>(`/api/diary/entries/${encodeURIComponent(entryId)}`);
}

export function updateDiaryEntry(entryId: string, body: DiaryEntryUpdateRequest): Promise<DiaryEntryItem> {
  return apiFetch<DiaryEntryItem>(`/api/diary/entries/${encodeURIComponent(entryId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteDiaryEntry(entryId: string): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`/api/diary/entries/${encodeURIComponent(entryId)}`, {
    method: "DELETE",
  });
}

export function listObserverRules(): Promise<ObservationRuleItem[]> {
  return apiFetch<ObservationRuleItem[]>("/api/observer/rules");
}

export function upsertObserverRule(body: ObservationRuleUpsertRequest): Promise<ObservationRuleItem> {
  return apiFetch<ObservationRuleItem>("/api/observer/rules", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function listObservations(
  status?: string,
  detector?: string,
  limit?: number,
): Promise<ObservationItem[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (detector) params.set("detector", detector);
  if (limit !== undefined) params.set("limit", String(limit));
  const qs = params.toString();
  return apiFetch<ObservationItem[]>(`/api/observer/observations${qs ? `?${qs}` : ""}`);
}

export function runObserver(): Promise<{ created: number }> {
  return apiFetch<{ created: number }>("/api/observer/observations/run", {
    method: "POST",
  });
}

export function dismissObservation(observationId: string): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(
    `/api/observer/observations/${encodeURIComponent(observationId)}/dismiss`,
    { method: "POST" },
  );
}

export function actionedObservation(observationId: string): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(
    `/api/observer/observations/${encodeURIComponent(observationId)}/actioned`,
    { method: "POST" },
  );
}

export function postponeObservation(
  observationId: string,
  body: ObservationPostponeRequest,
): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(
    `/api/observer/observations/${encodeURIComponent(observationId)}/postpone`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

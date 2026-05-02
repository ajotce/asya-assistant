import type {
  AccessRequestApproveResponse,
  AccessRequestResponse,
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
  HealthResponse,
  ModelInfo,
  ReasoningProbeRequest,
  ReasoningProbeResponse,
  SessionCreateResponse,
  SessionFilesUploadResponse,
  SettingsResponse,
  SettingsUpdateRequest,
  UsageOverviewResponse,
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

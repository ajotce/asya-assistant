import type {
  ChatStreamRequest,
  HealthResponse,
  SessionCreateResponse,
  SettingsResponse,
  SettingsUpdateRequest,
} from "../types/api";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const fallbackMessage = `Ошибка запроса (${response.status})`;
    let detail = fallbackMessage;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (typeof payload.detail === "string" && payload.detail.trim()) {
        detail = payload.detail;
      }
    } catch {
      detail = fallbackMessage;
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/health");
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
  const response = await fetch(`/api/session/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
  if (!response.ok) {
    const fallbackMessage = `Ошибка удаления сессии (${response.status})`;
    let detail = fallbackMessage;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (typeof payload.detail === "string" && payload.detail.trim()) {
        detail = payload.detail;
      }
    } catch {
      detail = fallbackMessage;
    }
    throw new Error(detail);
  }
}

interface StreamHandlers {
  onToken: (text: string) => void;
  onError: (message: string) => void;
  onDone: () => void;
}

export async function streamChat(request: ChatStreamRequest, handlers: StreamHandlers): Promise<void> {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok || !response.body) {
    const fallbackMessage = `Ошибка запроса (${response.status})`;
    throw new Error(fallbackMessage);
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

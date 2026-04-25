import type {
  HealthResponse,
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

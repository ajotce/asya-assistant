import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import {
  createSession,
  getHealth,
  getModels,
  getSettings,
  getUsage,
  streamChat,
  updateSettings,
  uploadSessionFiles,
} from "./api/client";

vi.mock("./api/client", () => ({
  createSession: vi.fn(),
  deleteSession: vi.fn(),
  streamChat: vi.fn(),
  uploadSessionFiles: vi.fn(),
  getSettings: vi.fn(),
  getModels: vi.fn(),
  updateSettings: vi.fn(),
  getHealth: vi.fn(),
  getUsage: vi.fn(),
}));

describe("App routing", () => {
  beforeEach(() => {
    window.history.pushState(null, "", "/");

    vi.mocked(createSession).mockReset();
    vi.mocked(streamChat).mockReset();
    vi.mocked(uploadSessionFiles).mockReset();
    vi.mocked(getSettings).mockReset();
    vi.mocked(getModels).mockReset();
    vi.mocked(updateSettings).mockReset();
    vi.mocked(getHealth).mockReset();
    vi.mocked(getUsage).mockReset();

    vi.mocked(createSession).mockResolvedValue({
      session_id: "session-12345678",
      created_at: "2026-04-25T00:00:00Z",
    });
    vi.mocked(uploadSessionFiles).mockResolvedValue({
      session_id: "session-12345678",
      files: [],
      file_ids: [],
    });
    vi.mocked(getSettings).mockResolvedValue({
      assistant_name: "Asya",
      selected_model: "openai/gpt-5",
      system_prompt: "System prompt",
      api_key_configured: true,
    });
    vi.mocked(getModels).mockResolvedValue([{ id: "openai/gpt-5" }]);
    vi.mocked(updateSettings).mockImplementation(async (payload) => ({
      ...payload,
      api_key_configured: true,
    }));
    vi.mocked(getHealth).mockResolvedValue({
      status: "ok",
      version: "0.1.0",
      environment: "local",
      uptime_seconds: 10,
      vsellm: {
        api_key_configured: true,
        base_url: "https://api.vsellm.ru/v1",
        reachable: true,
      },
      model: { selected: "openai/gpt-5" },
      files: { enabled: true, status: "готов" },
      embeddings: {
        enabled: true,
        model: "text-embedding-3-small",
        status: "готов",
        last_error: null,
      },
      storage: {
        session_store: "готов",
        file_store: "готов",
        tmp_dir: "/app/tmp",
        writable: true,
      },
      session: { enabled: true, active_sessions: 0 },
      last_error: null,
    });
    vi.mocked(getUsage).mockResolvedValue({
      chat: { status: "unavailable" },
      embeddings: { status: "unavailable" },
      cost: { status: "unavailable" },
      runtime: {
        active_sessions: 0,
        selected_model: "openai/gpt-5",
        embedding_model: "text-embedding-3-small",
      },
    });
  });

  it("сохраняет chat runtime-state при переключении вкладок и не пересоздает сессию", async () => {
    vi.mocked(streamChat).mockImplementation(async (_request, handlers) => {
      handlers.onToken("Привет!");
      handlers.onDone();
    });

    render(<App />);

    await screen.findByRole("heading", { name: "Чат" });
    fireEvent.change(screen.getByPlaceholderText("Введите сообщение"), { target: { value: "Тестовый запрос" } });
    fireEvent.click(screen.getByRole("button", { name: "Отправить" }));

    expect(await screen.findByText("Тестовый запрос")).toBeInTheDocument();
    expect(await screen.findByText("Привет!")).toBeInTheDocument();
    expect(createSession).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Настройки" }));
    await screen.findByRole("heading", { name: "Настройки" });

    fireEvent.click(screen.getByRole("button", { name: "Чат" }));
    await screen.findByRole("heading", { name: "Чат" });

    expect(createSession).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Тестовый запрос")).toBeInTheDocument();
    expect(screen.getByText("Привет!")).toBeInTheDocument();
  });

  it("открывает страницу состояния при прямом URL /status без инициализации chat-сессии", async () => {
    window.history.pushState(null, "", "/status");

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Состояние Asya" })).toBeInTheDocument();
    });
    expect(createSession).not.toHaveBeenCalled();
  });
});

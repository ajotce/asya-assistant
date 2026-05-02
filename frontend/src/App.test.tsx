import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import {
  authLogin,
  authMe,
  authRegister,
  authLogout,
  listAdminAccessRequests,
  approveAdminAccessRequest,
  rejectAdminAccessRequest,
  createSession,
  listChats,
  getChatMessages,
  getHealth,
  getModels,
  getSettings,
  getUsage,
  submitAccessRequest,
  streamChat,
  updateSettings,
  uploadSessionFiles,
} from "./api/client";

vi.mock("./api/client", () => ({
  authLogin: vi.fn(),
  authMe: vi.fn(),
  authRegister: vi.fn(),
  authLogout: vi.fn(),
  submitAccessRequest: vi.fn(),
  listAdminAccessRequests: vi.fn(),
  approveAdminAccessRequest: vi.fn(),
  rejectAdminAccessRequest: vi.fn(),
  createSession: vi.fn(),
  listChats: vi.fn(),
  getChatMessages: vi.fn(),
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
    vi.mocked(listChats).mockReset();
    vi.mocked(getChatMessages).mockReset();
    vi.mocked(authMe).mockReset();
    vi.mocked(authLogin).mockReset();
    vi.mocked(authRegister).mockReset();
    vi.mocked(authLogout).mockReset();
    vi.mocked(submitAccessRequest).mockReset();
    vi.mocked(listAdminAccessRequests).mockReset();
    vi.mocked(approveAdminAccessRequest).mockReset();
    vi.mocked(rejectAdminAccessRequest).mockReset();
    vi.mocked(streamChat).mockReset();
    vi.mocked(uploadSessionFiles).mockReset();
    vi.mocked(getSettings).mockReset();
    vi.mocked(getModels).mockReset();
    vi.mocked(updateSettings).mockReset();
    vi.mocked(getHealth).mockReset();
    vi.mocked(getUsage).mockReset();

    vi.mocked(authMe).mockResolvedValue({
      id: "user-1",
      email: "user@example.com",
      display_name: "User",
      role: "user",
      status: "active",
      preferred_chat_id: "base-chat-1",
    });
    vi.mocked(authLogin).mockResolvedValue({
      id: "user-1",
      email: "user@example.com",
      display_name: "User",
      role: "user",
      status: "active",
      preferred_chat_id: "base-chat-1",
    });
    vi.mocked(authRegister).mockResolvedValue({ status: "registered" });
    vi.mocked(authLogout).mockResolvedValue({ status: "ok" });
    vi.mocked(submitAccessRequest).mockResolvedValue({
      status: "pending",
      request: {
        id: "request-1",
        email: "user@example.com",
        display_name: "User",
        reason: "Хочу протестировать",
        status: "pending",
        created_at: "2026-05-02T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
      },
    });
    vi.mocked(listAdminAccessRequests).mockResolvedValue([]);
    vi.mocked(approveAdminAccessRequest).mockResolvedValue({
      status: "approved",
      request: {
        id: "request-1",
        email: "user@example.com",
        display_name: "User",
        reason: "Хочу протестировать",
        status: "approved",
        approved_by: "admin-1",
        reviewed_at: "2026-05-02T00:00:00Z",
        created_at: "2026-05-02T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
      },
      user: {
        id: "user-2",
        email: "user@example.com",
        display_name: "User",
        role: "user",
        status: "active",
        preferred_chat_id: "base-chat-2",
      },
    });
    vi.mocked(rejectAdminAccessRequest).mockResolvedValue({
      status: "rejected",
      request: {
        id: "request-1",
        email: "user@example.com",
        display_name: "User",
        reason: "Хочу протестировать",
        status: "rejected",
        created_at: "2026-05-02T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
      },
    });

    vi.mocked(createSession).mockResolvedValue({
      session_id: "session-12345678",
      created_at: "2026-04-25T00:00:00Z",
    });
    vi.mocked(listChats).mockResolvedValue([
      {
        id: "base-chat-1",
        title: "Base-chat",
        kind: "base",
        is_archived: false,
        created_at: "2026-05-02T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
        message_count: 0,
      },
    ]);
    vi.mocked(getChatMessages).mockResolvedValue([]);
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

  it("сохраняет chat runtime-state при переключении вкладок и использует preferred chat после login", async () => {
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
    expect(createSession).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Настройки" }));
    await screen.findByRole("heading", { name: "Настройки" });

    fireEvent.click(screen.getByRole("button", { name: "Чат" }));
    await screen.findByRole("heading", { name: "Чат" });

    expect(createSession).not.toHaveBeenCalled();
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

  it("показывает auth-экран без сессии и логинит пользователя", async () => {
    vi.mocked(authMe).mockRejectedValue(new Error("Ошибка запроса (401)"));
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Вход в Asya" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } });
    fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "strong-pass-123" } });
    fireEvent.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByRole("heading", { name: "Чат" })).toBeInTheDocument();
    expect(authLogin).toHaveBeenCalledTimes(1);
  });

  it("показывает admin-раздел заявок только для admin", async () => {
    vi.mocked(authMe).mockResolvedValue({
      id: "admin-1",
      email: "admin@example.com",
      display_name: "Admin",
      role: "admin",
      status: "active",
      preferred_chat_id: "base-chat-1",
    });
    vi.mocked(listAdminAccessRequests).mockResolvedValue([
      {
        id: "req-1",
        email: "beta@example.com",
        display_name: "Beta",
          reason: "Нужно раннее тестирование",
          status: "pending",
        created_at: "2026-05-02T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
      },
    ]);

    render(<App />);
    await screen.findByRole("heading", { name: "Чат" });
    fireEvent.click(screen.getByRole("button", { name: "Настройки" }));
    expect(await screen.findByText("Admin: Заявки на доступ")).toBeInTheDocument();
    expect(await screen.findByText("beta@example.com")).toBeInTheDocument();
  });
});

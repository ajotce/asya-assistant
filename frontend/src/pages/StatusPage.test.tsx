import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getHealth, getIntegrations, getUsage } from "../api/client";
import StatusPage from "./StatusPage";

vi.mock("../api/client", () => ({
  getHealth: vi.fn(),
  getUsage: vi.fn(),
  getIntegrations: vi.fn(),
}));

describe("StatusPage", () => {
  beforeEach(() => {
    vi.mocked(getHealth).mockReset();
    vi.mocked(getUsage).mockReset();
    vi.mocked(getIntegrations).mockReset();
  });

  it("показывает карточки с понятными статусами и раскрывает детали", async () => {
    vi.mocked(getHealth).mockResolvedValue({
      status: "ok",
      version: "0.1.0",
      environment: "local",
      uptime_seconds: 125,
      vsellm: {
        api_key_configured: true,
        base_url: "https://api.vsellm.ru/v1",
        reachable: true,
      },
      model: { selected: "gpt-4o" },
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
      chat: {
        prompt_tokens: null,
        completion_tokens: null,
        total_tokens: null,
        status: "unavailable",
        note: "Данные usage по chat пока не собраны.",
      },
      embeddings: {
        input_tokens: 122,
        total_tokens: 122,
        status: "available",
        note: null,
      },
      cost: {
        currency: null,
        total_cost: null,
        status: "unavailable",
        note: "Стоимость не рассчитывается.",
      },
      runtime: {
        active_sessions: 0,
        selected_model: "gpt-4o",
        embedding_model: "text-embedding-3-small",
      },
    });
    vi.mocked(getIntegrations).mockResolvedValue([
      { provider: "yandex_disk", status: "connected", scopes: ["disk.read"], last_sync_at: null },
      { provider: "onedrive", status: "not_connected", scopes: [], last_sync_at: null },
      { provider: "icloud_drive", status: "not_connected", scopes: [], last_sync_at: null },
    ]);

    render(<StatusPage />);

    expect(await screen.findByText("Работает")).toBeInTheDocument();
    expect(screen.getByText("Доступен")).toBeInTheDocument();
    expect(screen.getByText("Настроен")).toBeInTheDocument();
    expect(screen.getByText("gpt-4o")).toBeInTheDocument();
    expect(screen.getByText("Модуль: готов")).toBeInTheDocument();
    expect(screen.getByText("готов")).toBeInTheDocument();
    expect(screen.getByText("Активных сессий: 0")).toBeInTheDocument();
    expect(screen.getByText("Данные usage доступны")).toBeInTheDocument();
    expect(screen.getByText("Готово к записи")).toBeInTheDocument();
    expect(screen.getByText("Yandex.Disk integration")).toBeInTheDocument();
    expect(screen.getByText("OneDrive integration")).toBeInTheDocument();
    expect(screen.getByText("iCloud Drive integration")).toBeInTheDocument();
    expect(screen.getByTestId("status-last-updated")).toHaveTextContent("Последнее обновление:");
    expect(screen.getByLabelText("Автообновление (15 сек)")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Backend: Работает/i }));
    expect(await screen.findByText("Версия: 0.1.0")).toBeInTheDocument();
    expect(screen.getByText("Окружение: local")).toBeInTheDocument();
  });

  it("показывает понятную ошибку при недоступном /api/health", async () => {
    vi.mocked(getHealth).mockRejectedValue(new Error("Backend недоступен"));
    vi.mocked(getUsage).mockResolvedValue({
      chat: { status: "unavailable" },
      embeddings: { status: "unavailable" },
      cost: { status: "unavailable" },
      runtime: {
        active_sessions: 0,
        selected_model: "",
        embedding_model: "",
      },
    });
    vi.mocked(getIntegrations).mockResolvedValue([]);

    render(<StatusPage />);

    expect(await screen.findByRole("button", { name: /Backend: Недоступен/i })).toBeInTheDocument();
    expect(screen.getByText("Недоступен")).toBeInTheDocument();
  });

  it("не ломает health-карточки, если /api/usage вернул ошибку", async () => {
    vi.mocked(getHealth).mockResolvedValue({
      status: "ok",
      version: "0.1.0",
      environment: "local",
      uptime_seconds: 125,
      vsellm: {
        api_key_configured: true,
        base_url: "https://api.vsellm.ru/v1",
        reachable: true,
      },
      model: { selected: "gpt-4o" },
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
    vi.mocked(getUsage).mockRejectedValue(new Error("Usage endpoint недоступен"));
    vi.mocked(getIntegrations).mockResolvedValue([]);

    render(<StatusPage />);

    expect(await screen.findByText("Работает")).toBeInTheDocument();
    expect(screen.getByText("Ошибка получения usage")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Usage: Ошибка получения usage/i }));
    expect(await screen.findByText("Usage endpoint недоступен")).toBeInTheDocument();
  });
});

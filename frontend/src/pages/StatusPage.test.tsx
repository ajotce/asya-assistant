import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getHealth, getUsage } from "../api/client";
import StatusPage from "./StatusPage";

vi.mock("../api/client", () => ({
  getHealth: vi.fn(),
  getUsage: vi.fn(),
}));

describe("StatusPage", () => {
  beforeEach(() => {
    vi.mocked(getHealth).mockReset();
    vi.mocked(getUsage).mockReset();
  });

  it("рендерит ключевые карточки состояния из /api/health", async () => {
    vi.mocked(getHealth).mockResolvedValue({
      status: "ok",
      version: "0.1.0",
      environment: "local",
      uptime_seconds: 125,
      vsellm: {
        api_key_configured: true,
        base_url: "https://api.vsellm.ru/v1",
        reachable: true
      },
      model: { selected: "gpt-4o" },
      files: { enabled: true, status: "готов" },
      embeddings: {
        enabled: true,
        model: "text-embedding-3-small",
        status: "готов",
        last_error: null
      },
      storage: {
        session_store: "готов",
        file_store: "готов",
        tmp_dir: "/app/tmp",
        writable: true
      },
      session: { enabled: true, active_sessions: 0 },
      last_error: null
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

    render(<StatusPage />);

    expect(await screen.findByText("online")).toBeInTheDocument();
    expect(screen.getByText("2 мин")).toBeInTheDocument();
    expect(screen.getByText("доступен (https://api.vsellm.ru/v1)")).toBeInTheDocument();
    expect(screen.getByText("gpt-4o")).toBeInTheDocument();
    expect(screen.getByText("настроен")).toBeInTheDocument();
    expect(screen.getByText("включены, готов")).toBeInTheDocument();
    expect(screen.getByText("готов (text-embedding-3-small)")).toBeInTheDocument();
    expect(screen.getByText("включены, активных: 0")).toBeInTheDocument();
    expect(screen.getByText("chat: unavailable, embeddings: 122 embedding tokens, cost: unavailable")).toBeInTheDocument();
    expect(screen.getByText("sessions: готов, files: готов, доступно для записи")).toBeInTheDocument();
    expect(screen.getByText("/app/tmp")).toBeInTheDocument();
  });

  it("показывает ошибку при недоступном /api/health", async () => {
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

    render(<StatusPage />);

    expect(await screen.findByText("Backend недоступен")).toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getHealth } from "../api/client";
import StatusPage from "./StatusPage";

vi.mock("../api/client", () => ({
  getHealth: vi.fn()
}));

describe("StatusPage", () => {
  beforeEach(() => {
    vi.mocked(getHealth).mockReset();
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

    render(<StatusPage />);

    expect(await screen.findByText("online")).toBeInTheDocument();
    expect(screen.getByText("2 мин")).toBeInTheDocument();
    expect(screen.getByText("gpt-4o")).toBeInTheDocument();
    expect(screen.getByText("настроен")).toBeInTheDocument();
    expect(screen.getByText("готов (text-embedding-3-small)")).toBeInTheDocument();
    expect(screen.getByText("sessions: готов, files: готов, доступно для записи")).toBeInTheDocument();
    expect(screen.getByText("/app/tmp")).toBeInTheDocument();
  });
});

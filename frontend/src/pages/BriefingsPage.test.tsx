import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  generateBriefing,
  getBriefingItem,
  getBriefingSettings,
  listBriefingsArchive,
  patchBriefingSettings,
} from "../api/client";
import BriefingsPage from "./BriefingsPage";

vi.mock("../api/client", () => ({
  getBriefingSettings: vi.fn(),
  listBriefingsArchive: vi.fn(),
  getBriefingItem: vi.fn(),
  patchBriefingSettings: vi.fn(),
  generateBriefing: vi.fn(),
}));

describe("BriefingsPage", () => {
  beforeEach(() => {
    vi.mocked(getBriefingSettings).mockResolvedValue({
      morning_enabled: true,
      evening_enabled: true,
      delivery_in_app: true,
      delivery_telegram: false,
      created_at: "2026-05-04T12:00:00Z",
      updated_at: "2026-05-04T12:00:00Z",
    });
    vi.mocked(listBriefingsArchive).mockResolvedValue([
      {
        id: "b-1",
        kind: "morning",
        title: "Утренний брифинг",
        delivered_in_app: true,
        delivered_telegram: false,
        created_at: "2026-05-04T08:00:00Z",
      },
    ]);
    vi.mocked(getBriefingItem).mockResolvedValue({
      id: "b-1",
      kind: "morning",
      title: "Утренний брифинг",
      content_markdown: "# Утро\n\n## Главное\n- Тест",
      delivered_in_app: true,
      delivered_telegram: false,
      created_at: "2026-05-04T08:00:00Z",
      updated_at: "2026-05-04T08:00:00Z",
    });
    vi.mocked(patchBriefingSettings).mockImplementation(async (body) => ({
      ...body,
      created_at: "2026-05-04T12:00:00Z",
      updated_at: "2026-05-04T12:10:00Z",
    }));
    vi.mocked(generateBriefing).mockResolvedValue({
      status: "ok",
      briefing: {
        id: "b-2",
        kind: "evening",
        title: "Вечерний итог",
        content_markdown: "# Вечер",
        delivered_in_app: true,
        delivered_telegram: true,
        created_at: "2026-05-04T20:00:00Z",
        updated_at: "2026-05-04T20:00:00Z",
      },
    });
  });

  it("показывает архив и контент markdown без raw JSON", async () => {
    render(<BriefingsPage />);

    expect(await screen.findByRole("heading", { name: "Брифинги" })).toBeInTheDocument();
    expect(await screen.findByText("Архив последних брифингов")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Утренний брифинг" })).toBeInTheDocument();
    expect(screen.getByText((value) => value.includes("## Главное"))).toBeInTheDocument();
    expect(screen.queryByText(/\{\s*"/)).not.toBeInTheDocument();
  });

  it("позволяет менять настройки и запускать ручную генерацию", async () => {
    render(<BriefingsPage />);
    await screen.findByLabelText("Доставка в Telegram");

    fireEvent.click(screen.getByLabelText("Доставка в Telegram"));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить настройки" }));

    await waitFor(() => {
      expect(patchBriefingSettings).toHaveBeenCalledWith(
        expect.objectContaining({ delivery_telegram: true })
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "Сгенерировать вечерний" }));
    await waitFor(() => {
      expect(generateBriefing).toHaveBeenCalledWith("evening");
    });
    expect(await screen.findByText("# Вечер")).toBeInTheDocument();
  });
});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getModels,
  getReasoningCache,
  getSettings,
  probeReasoningModels,
  updateSettings,
} from "../api/client";
import SettingsPage from "./SettingsPage";

vi.mock("../api/client", () => ({
  getModels: vi.fn(),
  getReasoningCache: vi.fn(),
  getSettings: vi.fn(),
  probeReasoningModels: vi.fn(),
  updateSettings: vi.fn(),
}));

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.mocked(getSettings).mockReset();
    vi.mocked(getModels).mockReset();
    vi.mocked(getReasoningCache).mockReset();
    vi.mocked(probeReasoningModels).mockReset();
    vi.mocked(updateSettings).mockReset();

    vi.mocked(getSettings).mockResolvedValue({
      assistant_name: "Asya",
      selected_model: "gpt-4o",
      system_prompt: "Базовый промт",
      api_key_configured: true,
    });
    vi.mocked(getModels).mockResolvedValue([{ id: "gpt-4o" }, { id: "openai/gpt-5" }]);
    vi.mocked(getReasoningCache).mockResolvedValue({ results: [] });
    vi.mocked(probeReasoningModels).mockResolvedValue({ results: [] });
    vi.mocked(updateSettings).mockImplementation(async (payload) => ({
      ...payload,
      api_key_configured: true,
    }));
  });

  it("показывает настройки модели и список доступных моделей", async () => {
    render(<SettingsPage />);

    expect(await screen.findByRole("heading", { name: "Настройки" })).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "gpt-4o" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "openai/gpt-5" })).toBeInTheDocument();
  });

  it("позволяет изменить системный промт и сохранить настройки", async () => {
    render(<SettingsPage />);
    await screen.findByLabelText("Глобально выбранная модель");

    fireEvent.change(screen.getByLabelText("Глобально выбранная модель"), { target: { value: "openai/gpt-5" } });
    fireEvent.change(screen.getByLabelText("Системный промт"), { target: { value: "Новый системный промт" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));

    await waitFor(() => {
      expect(updateSettings).toHaveBeenCalledWith({
        assistant_name: "Asya",
        selected_model: "openai/gpt-5",
        system_prompt: "Новый системный промт",
      });
    });
    expect(await screen.findByText("Настройки сохранены.")).toBeInTheDocument();
  });

  it("показывает heuristic-бейдж 🧠 у reasoning-моделей и подтверждённый ✅ после probe", async () => {
    vi.mocked(getModels).mockResolvedValue([
      { id: "gpt-4o" },
      { id: "qwen/qwen3-vl-235b-a22b-thinking" },
    ]);
    vi.mocked(probeReasoningModels).mockResolvedValue({
      results: [
        {
          id: "qwen/qwen3-vl-235b-a22b-thinking",
          streams_reasoning: true,
          checked_at: "2026-04-26T10:00:00+00:00",
        },
      ],
    });

    render(<SettingsPage />);

    expect(await screen.findByRole("option", { name: "🧠 qwen/qwen3-vl-235b-a22b-thinking" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "gpt-4o" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Проверить reasoning у моделей" }));

    expect(
      await screen.findByRole("option", { name: "✅ qwen/qwen3-vl-235b-a22b-thinking" })
    ).toBeInTheDocument();
    expect(probeReasoningModels).toHaveBeenCalledWith({ force: false });
    const probeList = screen.getByTestId("reasoning-probe-results");
    expect(probeList).toHaveTextContent("qwen/qwen3-vl-235b-a22b-thinking");
  });

  it("показывает предупреждение и disabled option для модели без chat/completions", async () => {
    vi.mocked(getSettings).mockResolvedValue({
      assistant_name: "Asya",
      selected_model: "embed-only",
      system_prompt: "Базовый промт",
      api_key_configured: true,
    });
    vi.mocked(getModels).mockResolvedValue([
      { id: "embed-only", supports_chat: false },
      { id: "openai/gpt-5", supports_chat: true },
    ]);

    render(<SettingsPage />);

    expect(await screen.findByText(/не поддерживает chat\/completions/i)).toBeInTheDocument();
    const unsupportedOption = await screen.findByRole("option", { name: "embed-only (без chat/completions)" });
    expect(unsupportedOption).toBeDisabled();
    expect(screen.getByRole("button", { name: "Сохранить" })).toBeDisabled();
  });
});

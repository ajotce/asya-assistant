import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getModels, getSettings, updateSettings } from "../api/client";
import SettingsPage from "./SettingsPage";

vi.mock("../api/client", () => ({
  getModels: vi.fn(),
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
}));

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.mocked(getSettings).mockReset();
    vi.mocked(getModels).mockReset();
    vi.mocked(updateSettings).mockReset();

    vi.mocked(getSettings).mockResolvedValue({
      assistant_name: "Asya",
      selected_model: "gpt-4o",
      system_prompt: "Базовый промт",
      api_key_configured: true,
    });
    vi.mocked(getModels).mockResolvedValue([{ id: "gpt-4o" }, { id: "openai/gpt-5" }]);
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
    await screen.findByRole("heading", { name: "Настройки" });

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
});

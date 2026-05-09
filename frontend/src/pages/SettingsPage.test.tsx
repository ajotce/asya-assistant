import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  connectImap,
  disconnectImap,
  getImapMessage,
  getGitHubStatus,
  getBriefingSettings,
  getIntegrations,
  getModels,
  getReasoningCache,
  getSettings,
  listImapFolders,
  listImapMessages,
  listGitHubIssues,
  listGitHubPulls,
  listGitHubRepos,
  markImapAsRead,
  getUserExportStatus,
  startUserExport,
  probeReasoningModels,
  prepareDeleteMe,
  confirmDeleteMe,
  readGitHubFile,
  searchImapMessages,
  testImapConnection,
  patchBriefingSettings,
  updateSettings,
} from "../api/client";
import { type ThemePreference } from "../hooks/useTheme";
import SettingsPage from "./SettingsPage";

function renderSettingsPage(initialPreference: ThemePreference = "system") {
  const onChange = vi.fn();
  function Harness() {
    const [pref, setPref] = useState<ThemePreference>(initialPreference);
    return (
      <SettingsPage
        themePreference={pref}
        onThemePreferenceChange={(next) => {
          onChange(next);
          setPref(next);
        }}
      />
    );
  }
  return { onChange, ...render(<Harness />) };
}

vi.mock("../api/client", () => ({
  getModels: vi.fn(),
  getReasoningCache: vi.fn(),
  getSettings: vi.fn(),
  getIntegrations: vi.fn(),
  getGitHubStatus: vi.fn(),
  getBriefingSettings: vi.fn(),
  testImapConnection: vi.fn(),
  patchBriefingSettings: vi.fn(),
  connectImap: vi.fn(),
  disconnectImap: vi.fn(),
  listImapFolders: vi.fn(),
  listImapMessages: vi.fn(),
  searchImapMessages: vi.fn(),
  getImapMessage: vi.fn(),
  markImapAsRead: vi.fn(),
  getUserExportStatus: vi.fn(),
  startUserExport: vi.fn(),
  listGitHubRepos: vi.fn(),
  listGitHubIssues: vi.fn(),
  listGitHubPulls: vi.fn(),
  readGitHubFile: vi.fn(),
  probeReasoningModels: vi.fn(),
  prepareDeleteMe: vi.fn(),
  confirmDeleteMe: vi.fn(),
  updateSettings: vi.fn(),
}));

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.mocked(getSettings).mockReset();
    vi.mocked(getModels).mockReset();
    vi.mocked(getReasoningCache).mockReset();
    vi.mocked(getIntegrations).mockReset();
    vi.mocked(getGitHubStatus).mockReset();
    vi.mocked(getBriefingSettings).mockReset();
    vi.mocked(testImapConnection).mockReset();
    vi.mocked(patchBriefingSettings).mockReset();
    vi.mocked(connectImap).mockReset();
    vi.mocked(disconnectImap).mockReset();
    vi.mocked(listImapFolders).mockReset();
    vi.mocked(listImapMessages).mockReset();
    vi.mocked(searchImapMessages).mockReset();
    vi.mocked(getImapMessage).mockReset();
    vi.mocked(markImapAsRead).mockReset();
    vi.mocked(getUserExportStatus).mockReset();
    vi.mocked(startUserExport).mockReset();
    vi.mocked(listGitHubRepos).mockReset();
    vi.mocked(listGitHubIssues).mockReset();
    vi.mocked(listGitHubPulls).mockReset();
    vi.mocked(readGitHubFile).mockReset();
    vi.mocked(probeReasoningModels).mockReset();
    vi.mocked(prepareDeleteMe).mockReset();
    vi.mocked(confirmDeleteMe).mockReset();
    vi.mocked(updateSettings).mockReset();

    vi.mocked(getSettings).mockResolvedValue({
      assistant_name: "Asya",
      selected_model: "gpt-4o",
      system_prompt: "Базовый промт",
      wakeword_enabled: false,
      wakeword_phrase: "ася",
      wakeword_sensitivity: 0.5,
      api_key_configured: true,
    });
    vi.mocked(getModels).mockResolvedValue([{ id: "gpt-4o" }, { id: "openai/gpt-5" }]);
    vi.mocked(getReasoningCache).mockResolvedValue({ results: [] });
    vi.mocked(getIntegrations).mockResolvedValue([
      { provider: "bitrix24", status: "not_connected", scopes: [] },
      { provider: "github", status: "not_connected", scopes: [] },
      { provider: "imap", status: "not_connected", scopes: [] },
    ]);
    vi.mocked(getGitHubStatus).mockResolvedValue({ provider: "github", status: "not_connected", scopes: [] });
    vi.mocked(getBriefingSettings).mockResolvedValue({
      timezone: "Europe/Moscow",
      morning_enabled: true,
      evening_enabled: true,
      morning_time: "08:00",
      evening_time: "19:00",
      channel_in_app: true,
      channel_telegram: false,
      created_at: "2026-05-09T00:00:00Z",
      updated_at: "2026-05-09T00:00:00Z",
    });
    vi.mocked(testImapConnection).mockResolvedValue({ ok: true, folders: ["INBOX"] });
    vi.mocked(patchBriefingSettings).mockResolvedValue({
      timezone: "Europe/Moscow",
      morning_enabled: true,
      evening_enabled: true,
      morning_time: "08:00",
      evening_time: "19:00",
      channel_in_app: true,
      channel_telegram: false,
      created_at: "2026-05-09T00:00:00Z",
      updated_at: "2026-05-09T00:00:00Z",
    });
    vi.mocked(connectImap).mockResolvedValue({ provider: "imap", status: "connected", scopes: ["mail.read"] });
    vi.mocked(disconnectImap).mockResolvedValue({ provider: "imap", status: "revoked", scopes: [] });
    vi.mocked(listImapFolders).mockResolvedValue({ folders: ["INBOX"] });
    vi.mocked(listImapMessages).mockResolvedValue([]);
    vi.mocked(searchImapMessages).mockResolvedValue([]);
    vi.mocked(getImapMessage).mockResolvedValue({
      uid: "1",
      subject: "s",
      from_name: "n",
      from_email: "e@example.com",
      date: null,
      is_unread: true,
      to: [],
      cc: [],
      text_body: "body",
    });
    vi.mocked(markImapAsRead).mockResolvedValue({ status: "ok" });
    vi.mocked(startUserExport).mockResolvedValue({ export_id: "exp-1", status: "pending" });
    vi.mocked(getUserExportStatus).mockResolvedValue({ export_id: "exp-1", status: "ready", download_url: "/api/me/export/download/token-1" });
    vi.mocked(listGitHubRepos).mockResolvedValue([]);
    vi.mocked(listGitHubIssues).mockResolvedValue([]);
    vi.mocked(listGitHubPulls).mockResolvedValue([]);
    vi.mocked(readGitHubFile).mockResolvedValue({
      content: "",
      encoding: "base64",
      path: "README.md",
      sha: "x",
      size: 0,
      html_url: null,
    });
    vi.mocked(probeReasoningModels).mockResolvedValue({ results: [] });
    vi.mocked(prepareDeleteMe).mockResolvedValue({ confirmation_token: "confirm-1", expires_at: "2026-05-09T00:00:00Z" });
    vi.mocked(confirmDeleteMe).mockResolvedValue({ status: "deleted", export_id: "exp-1", download_url: null, expires_at: null });
    vi.mocked(updateSettings).mockImplementation(async (payload) => ({
      ...payload,
      api_key_configured: true,
    }));
  });

  it("показывает настройки модели и список доступных моделей", async () => {
    renderSettingsPage();

    expect(await screen.findByRole("heading", { name: "Настройки" })).toBeInTheDocument();
    expect(await screen.findByTestId("bitrix24-status")).toHaveTextContent("Bitrix24 (read-only): not_connected");
    expect(await screen.findByTestId("github-status")).toHaveTextContent("GitHub (read-only): not_connected");
    expect(await screen.findByTestId("imap-status")).toHaveTextContent("IMAP: not_connected");
    expect(await screen.findByRole("option", { name: "gpt-4o" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "openai/gpt-5" })).toBeInTheDocument();
  });

  it("позволяет изменить системный промт и сохранить настройки", async () => {
    renderSettingsPage();
    await screen.findByLabelText("Глобально выбранная модель");

    fireEvent.change(screen.getByLabelText("Глобально выбранная модель"), { target: { value: "openai/gpt-5" } });
    fireEvent.change(screen.getByLabelText("Системный промт"), { target: { value: "Новый системный промт" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));

    await waitFor(() => {
      expect(updateSettings).toHaveBeenCalledWith({
        assistant_name: "Asya",
        selected_model: "openai/gpt-5",
        system_prompt: "Новый системный промт",
        wakeword_enabled: false,
        wakeword_phrase: "ася",
        wakeword_sensitivity: 0.5,
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

    renderSettingsPage();

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

  it("отображает сегментированный переключатель темы и сообщает о выборе", async () => {
    const { onChange } = renderSettingsPage("system");
    await screen.findByRole("heading", { name: "Настройки" });

    const lightButton = screen.getByRole("button", { name: "Светлая" });
    const darkButton = screen.getByRole("button", { name: "Тёмная" });
    const systemButton = screen.getByRole("button", { name: "Системная" });

    expect(systemButton).toHaveAttribute("aria-pressed", "true");
    expect(lightButton).toHaveAttribute("aria-pressed", "false");
    expect(darkButton).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(darkButton);

    expect(onChange).toHaveBeenCalledWith("dark");
    expect(screen.getByRole("button", { name: "Тёмная" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Системная" })).toHaveAttribute("aria-pressed", "false");
  });

  it("показывает предупреждение и disabled option для модели без chat/completions", async () => {
    vi.mocked(getSettings).mockResolvedValue({
      assistant_name: "Asya",
      selected_model: "embed-only",
      system_prompt: "Базовый промт",
      wakeword_enabled: false,
      wakeword_phrase: "ася",
      wakeword_sensitivity: 0.5,
      api_key_configured: true,
    });
    vi.mocked(getModels).mockResolvedValue([
      { id: "embed-only", supports_chat: false },
      { id: "openai/gpt-5", supports_chat: true },
    ]);

    renderSettingsPage();

    expect(await screen.findByText(/не поддерживает chat\/completions/i)).toBeInTheDocument();
    const unsupportedOption = await screen.findByRole("option", { name: "embed-only (без chat/completions)" });
    expect(unsupportedOption).toBeDisabled();
    expect(screen.getByRole("button", { name: "Сохранить" })).toBeDisabled();
  });

  it("позволяет протестировать и подключить IMAP", async () => {
    renderSettingsPage();
    await screen.findByTestId("imap-status");

    fireEvent.change(screen.getByPlaceholderText("email"), { target: { value: "imap@example.com" } });
    fireEvent.change(screen.getByPlaceholderText("username"), { target: { value: "imap@example.com" } });
    fireEvent.change(screen.getByPlaceholderText("password/app password"), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Test" }));
    expect(await screen.findByText(/Проверка успешна/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Connect" }));
    await waitFor(() => expect(connectImap).toHaveBeenCalled());
  });

  it("запускает экспорт и получает статус ready", async () => {
    renderSettingsPage();
    await screen.findByRole("heading", { name: "Настройки" });

    fireEvent.click(screen.getByRole("button", { name: "Скачать мои данные" }));
    await waitFor(() => expect(startUserExport).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "Обновить статус" }));
    await waitFor(() => expect(getUserExportStatus).toHaveBeenCalledWith("exp-1"));
    expect(await screen.findByText("Статус экспорта: ready")).toBeInTheDocument();
  });

  it("открывает модал удаления и выполняет двухшаговое подтверждение", async () => {
    renderSettingsPage();
    await screen.findByRole("heading", { name: "Настройки" });

    fireEvent.click(screen.getByRole("button", { name: "Открыть подтверждение удаления" }));
    expect(screen.getByRole("dialog", { name: "Удаление учётки" })).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Введите пароль"), { target: { value: "strong-pass-123" } });
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить пароль" }));
    await waitFor(() => expect(prepareDeleteMe).toHaveBeenCalledWith({ password: "strong-pass-123" }));

    fireEvent.click(screen.getByRole("button", { name: "Удалить учётку" }));
    await waitFor(() => expect(confirmDeleteMe).toHaveBeenCalledWith("confirm-1"));
  });
});

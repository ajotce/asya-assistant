import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getChatMessages,
  getSpaceSettings,
  listChats,
  listSpaces,
  streamChat,
  updateSpaceSettings,
  uploadSessionFiles,
} from "../api/client";
import ChatPage from "./ChatPage";

vi.mock("../api/client", () => ({
  listChats: vi.fn(),
  listSpaces: vi.fn(),
  getSpaceSettings: vi.fn(),
  updateSpaceSettings: vi.fn(),
  createSpace: vi.fn(),
  renameSpace: vi.fn(),
  archiveSpace: vi.fn(),
  createChat: vi.fn(),
  renameChat: vi.fn(),
  archiveChat: vi.fn(),
  deleteChat: vi.fn(),
  getChatMessages: vi.fn(),
  streamChat: vi.fn(),
  uploadSessionFiles: vi.fn(),
}));

describe("ChatPage", () => {
  beforeEach(() => {
    vi.mocked(listChats).mockReset();
    vi.mocked(listSpaces).mockReset();
    vi.mocked(getSpaceSettings).mockReset();
    vi.mocked(updateSpaceSettings).mockReset();
    vi.mocked(getChatMessages).mockReset();
    vi.mocked(streamChat).mockReset();
    vi.mocked(uploadSessionFiles).mockReset();

    vi.mocked(listSpaces).mockResolvedValue([
      {
        id: "space-default-1",
        name: "Default",
        is_default: true,
        is_admin_only: false,
        is_archived: false,
        created_at: "2026-05-02T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
      },
    ]);
    vi.mocked(listChats).mockResolvedValue([
      {
        id: "base-chat-1",
        title: "Base-chat",
        kind: "base",
        space_id: "space-default-1",
        is_archived: false,
        created_at: "2026-05-02T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
        message_count: 0,
      },
    ]);
    vi.mocked(getSpaceSettings).mockResolvedValue({
      space_id: "space-default-1",
      memory_read_enabled: true,
      memory_write_enabled: true,
      behavior_rules_enabled: true,
      personality_overlay_enabled: true,
      created_at: "2026-05-02T00:00:00Z",
      updated_at: "2026-05-02T00:00:00Z",
    });
    vi.mocked(getChatMessages).mockResolvedValue([]);
    vi.mocked(uploadSessionFiles).mockResolvedValue({ session_id: "session-12345678", files: [], file_ids: [] });
  });

  it("рендерит главный экран чата и блок пространств", async () => {
    render(<ChatPage />);

    expect(await screen.findByRole("heading", { name: "Чат" })).toBeInTheDocument();
    expect(await screen.findByText("Пространства")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Base-chat (базовый)" })).toBeInTheDocument();
    expect(screen.getByText("Сообщений пока нет. Напишите первый запрос.")).toBeInTheDocument();
  });

  it("отправляет сообщение и отображает ответ", async () => {
    vi.mocked(streamChat).mockImplementation(async (_request, handlers) => {
      handlers.onToken("Привет!");
      handlers.onDone();
    });

    render(<ChatPage />);
    await screen.findByRole("button", { name: "Base-chat (базовый)" });

    fireEvent.change(screen.getByPlaceholderText("Введите сообщение"), { target: { value: "Тестовый запрос" } });
    fireEvent.click(screen.getByRole("button", { name: "Отправить" }));

    expect(await screen.findByText("Тестовый запрос")).toBeInTheDocument();
    expect(await screen.findByText("Привет!")).toBeInTheDocument();
    expect(streamChat).toHaveBeenCalledTimes(1);
  });

  it("показывает loading/error для пространств и настроек", async () => {
    vi.mocked(getSpaceSettings).mockRejectedValueOnce(new Error("settings error"));
    render(<ChatPage />);

    expect(await screen.findByText("Пространства")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/settings error/i)).toBeInTheDocument();
    });
  });

  it("скрывает Asya-dev для обычного пользователя и показывает для admin", async () => {
    vi.mocked(listSpaces).mockResolvedValue([
      {
        id: "space-default-1",
        name: "Default",
        is_default: true,
        is_admin_only: false,
        is_archived: false,
        created_at: "2026-05-02T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
      },
      {
        id: "space-admin-1",
        name: "Asya-dev",
        is_default: false,
        is_admin_only: true,
        is_archived: false,
        created_at: "2026-05-02T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
      },
    ]);

    const { rerender } = render(<ChatPage currentUserRole="user" />);
    await screen.findByText("Пространства");
    await waitFor(() => {
      expect(screen.queryByText(/Asya-dev/)).not.toBeInTheDocument();
    });

    rerender(<ChatPage currentUserRole="admin" />);
    await waitFor(() => {
      expect(screen.getByText(/Asya-dev/)).toBeInTheDocument();
    });
  });
});

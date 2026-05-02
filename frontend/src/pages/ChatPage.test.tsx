import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getChatMessages, listChats, streamChat, uploadSessionFiles } from "../api/client";
import ChatPage from "./ChatPage";

vi.mock("../api/client", () => ({
  listChats: vi.fn(),
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
    vi.mocked(getChatMessages).mockReset();
    vi.mocked(streamChat).mockReset();
    vi.mocked(uploadSessionFiles).mockReset();
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
    vi.mocked(uploadSessionFiles).mockResolvedValue({ session_id: "session-12345678", files: [], file_ids: [] });
  });

  it("рендерит главный экран чата", async () => {
    render(<ChatPage />);

    expect(await screen.findByRole("heading", { name: "Чат" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Base-chat" })).toBeInTheDocument();
    expect(screen.getByText("Сообщений пока нет. Напишите первый запрос.")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Введите сообщение")).toBeInTheDocument();
    expect(screen.getByText("Файлы не выбраны.")).toBeInTheDocument();
  });

  it("отправляет сообщение и отображает ответ", async () => {
    vi.mocked(streamChat).mockImplementation(async (_request, handlers) => {
      handlers.onToken("Привет!");
      handlers.onDone();
    });

    render(<ChatPage />);
    await screen.findByRole("button", { name: "Base-chat" });

    fireEvent.change(screen.getByPlaceholderText("Введите сообщение"), { target: { value: "Тестовый запрос" } });
    fireEvent.click(screen.getByRole("button", { name: "Отправить" }));

    expect(await screen.findByText("Тестовый запрос")).toBeInTheDocument();
    expect(await screen.findByText("Привет!")).toBeInTheDocument();
    expect(streamChat).toHaveBeenCalledTimes(1);
  });

  it("показывает streaming-состояние во время генерации", async () => {
    vi.mocked(streamChat).mockImplementation(
      async (_request, handlers) =>
        await new Promise<void>((resolve) => {
          setTimeout(() => {
            handlers.onDone();
            resolve();
          }, 60);
        })
    );

    render(<ChatPage />);
    await screen.findByRole("button", { name: "Base-chat" });

    fireEvent.change(screen.getByPlaceholderText("Введите сообщение"), { target: { value: "Проверка стриминга" } });
    fireEvent.click(screen.getByRole("button", { name: "Отправить" }));

    expect(await screen.findByText("Печатает...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Генерация..." })).toBeInTheDocument();
  });

  it("отображает блок размышлений, когда модель прислала reasoning", async () => {
    vi.mocked(streamChat).mockImplementation(async (_request, handlers) => {
      handlers.onThinking?.("шаг рассуждения");
      handlers.onToken("Ответ");
      handlers.onDone();
    });

    render(<ChatPage />);
    await screen.findByRole("button", { name: "Base-chat" });

    fireEvent.change(screen.getByPlaceholderText("Введите сообщение"), {
      target: { value: "Запрос с размышлением" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Отправить" }));

    const summary = await screen.findByText("Размышления модели");
    expect(summary).toBeInTheDocument();
    fireEvent.click(summary);
    expect(await screen.findByText("шаг рассуждения")).toBeInTheDocument();
    expect(await screen.findByText("Ответ")).toBeInTheDocument();
  });

  it("не показывает блок размышлений, если модель не прислала reasoning", async () => {
    vi.mocked(streamChat).mockImplementation(async (_request, handlers) => {
      handlers.onToken("Обычный ответ");
      handlers.onDone();
    });

    render(<ChatPage />);
    await screen.findByRole("button", { name: "Base-chat" });

    fireEvent.change(screen.getByPlaceholderText("Введите сообщение"), {
      target: { value: "Без размышлений" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Отправить" }));

    expect(await screen.findByText("Обычный ответ")).toBeInTheDocument();
    expect(screen.queryByText("Размышления модели")).not.toBeInTheDocument();
  });

  it("отображает понятную ошибку выбранной модели, если stream вернул событие error", async () => {
    vi.mocked(streamChat).mockImplementation(async (_request, handlers) => {
      handlers.onError(
        "Модель 'openai/gpt-5' не приняла chat/completions-запрос. Причина провайдера: Model does not support chat/completions."
      );
    });

    render(<ChatPage />);
    await screen.findByRole("button", { name: "Base-chat" });

    fireEvent.change(screen.getByPlaceholderText("Введите сообщение"), { target: { value: "Тест ошибки" } });
    fireEvent.click(screen.getByRole("button", { name: "Отправить" }));

    await waitFor(() => {
      expect(screen.getByText(/model does not support chat\/completions/i)).toBeInTheDocument();
      expect(screen.getByText(/openai\/gpt-5/i)).toBeInTheDocument();
    });
  });
});

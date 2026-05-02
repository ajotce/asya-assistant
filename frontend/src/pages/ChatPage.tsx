import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

import {
  archiveChat,
  createChat,
  deleteChat,
  getChatMessages,
  listChats,
  renameChat,
  streamChat,
  uploadSessionFiles,
} from "../api/client";
import type { ChatListItem } from "../types/api";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  thinking?: string;
  streaming?: boolean;
}

const MAX_FILES_PER_MESSAGE = 10;
const MAX_FILE_SIZE_MB = 256;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const ALLOWED_DOCUMENT_EXTENSIONS = new Set([".pdf", ".docx", ".xlsx"]);
const ALLOWED_IMAGE_EXTENSIONS = new Set([
  ".jpg",
  ".jpeg",
  ".png",
  ".gif",
  ".bmp",
  ".webp",
  ".tif",
  ".tiff",
  ".heic",
]);

interface ChatPageProps {
  initialSessionId?: string | null;
}

export default function ChatPage({ initialSessionId = null }: ChatPageProps) {
  const [chats, setChats] = useState<ChatListItem[]>([]);
  const [chatsLoading, setChatsLoading] = useState(true);
  const [chatsError, setChatsError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [messagesError, setMessagesError] = useState<string | null>(null);

  const [input, setInput] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasMessages = messages.length > 0;
  const canSend = !isGenerating && Boolean(sessionId);

  useEffect(() => {
    let active = true;

    async function loadChatsOnStart() {
      setChatsLoading(true);
      setChatsError(null);
      try {
        const list = await listChats();
        if (!active) {
          return;
        }
        setChats(list);

        const selected = pickInitialChatId(list, initialSessionId);
        if (selected) {
          setSessionId(selected);
        }
      } catch (loadError) {
        if (!active) {
          return;
        }
        setChatsError(getErrorMessage(loadError));
      } finally {
        if (active) {
          setChatsLoading(false);
        }
      }
    }

    void loadChatsOnStart();
    return () => {
      active = false;
    };
  }, [initialSessionId]);

  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }

    let active = true;

    async function loadMessages(chatId: string) {
      setMessagesLoading(true);
      setMessagesError(null);
      try {
        const items = await getChatMessages(chatId);
        if (!active) {
          return;
        }
        setMessages(
          items
            .filter((item) => item.role === "user" || item.role === "assistant")
            .map((item) => ({
              id: item.id,
              role: item.role as "user" | "assistant",
              text: item.content,
            }))
        );
      } catch (loadError) {
        if (!active) {
          return;
        }
        setMessages([]);
        setMessagesError(getErrorMessage(loadError));
      } finally {
        if (active) {
          setMessagesLoading(false);
        }
      }
    }

    void loadMessages(sessionId);
    return () => {
      active = false;
    };
  }, [sessionId]);

  function handleSelectFiles(event: ChangeEvent<HTMLInputElement>) {
    const incoming = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!incoming.length || isGenerating) {
      return;
    }

    const next = [...selectedFiles];
    let firstError: string | null = null;
    for (const file of incoming) {
      if (next.length >= MAX_FILES_PER_MESSAGE) {
        firstError = `Можно прикрепить не более ${MAX_FILES_PER_MESSAGE} файлов к одному сообщению.`;
        break;
      }

      const validationMessage = validateSelectedFile(file);
      if (validationMessage) {
        if (!firstError) {
          firstError = validationMessage;
        }
        continue;
      }

      if (next.some((existing) => isSameFile(existing, file))) {
        continue;
      }
      next.push(file);
    }

    setSelectedFiles(next);
    setError(firstError);
  }

  function removeSelectedFile(index: number) {
    if (isGenerating) {
      return;
    }
    setSelectedFiles((prev) => prev.filter((_, itemIndex) => itemIndex !== index));
  }

  async function handleCreateChat() {
    if (isGenerating) {
      return;
    }
    setError(null);
    try {
      const chat = await createChat({ title: "Новый чат" });
      setChats((prev) => [...prev, chat]);
      setSessionId(chat.id);
      setMessages([]);
      setSelectedFiles([]);
      setInput("");
    } catch (createError) {
      setError(getErrorMessage(createError));
    }
  }

  async function handleRenameChat(chat: ChatListItem) {
    if (chat.kind === "base" || isGenerating) {
      return;
    }
    const nextTitle = window.prompt("Новое название чата", chat.title)?.trim();
    if (!nextTitle) {
      return;
    }
    try {
      const updated = await renameChat(chat.id, { title: nextTitle });
      setChats((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    } catch (renameError) {
      setError(getErrorMessage(renameError));
    }
  }

  async function handleArchiveChat(chat: ChatListItem) {
    if (chat.kind === "base" || isGenerating) {
      return;
    }
    if (!window.confirm(`Архивировать чат '${chat.title}'?`)) {
      return;
    }
    try {
      await archiveChat(chat.id);
      const refreshed = await listChats();
      setChats(refreshed);
      if (sessionId === chat.id) {
        const next = pickInitialChatId(refreshed, null);
        setSessionId(next);
      }
    } catch (archiveError) {
      setError(getErrorMessage(archiveError));
    }
  }

  async function handleDeleteChat(chat: ChatListItem) {
    if (chat.kind === "base" || isGenerating) {
      return;
    }
    if (!window.confirm(`Удалить чат '${chat.title}'?`)) {
      return;
    }
    try {
      await deleteChat(chat.id);
      const refreshed = await listChats();
      setChats(refreshed);
      if (sessionId === chat.id) {
        const next = pickInitialChatId(refreshed, null);
        setSessionId(next);
      }
    } catch (deleteError) {
      setError(getErrorMessage(deleteError));
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || !sessionId) {
      return;
    }

    const filesToSend = [...selectedFiles];
    setInput("");
    await sendUserMessageInSession(sessionId, text, filesToSend);
  }

  async function sendUserMessageInSession(currentSessionId: string, text: string, filesToUpload: File[]) {
    setError(null);
    setIsGenerating(true);

    let uploadedImageFileIds: string[] = [];
    if (filesToUpload.length > 0) {
      try {
        const uploaded = await uploadSessionFiles(currentSessionId, filesToUpload);
        uploadedImageFileIds = uploaded.files
          .map((uploadedFile, index) => ({ uploadedFile, sourceFile: filesToUpload[index] }))
          .filter(({ uploadedFile, sourceFile }) => isImageUpload(sourceFile, uploadedFile.content_type))
          .map(({ uploadedFile }) => uploadedFile.file_id);
      } catch (uploadError) {
        setError(normalizeUploadError(uploadError));
        setIsGenerating(false);
        return;
      }
    }

    const userId = makeId("user");
    const assistantId = makeId("assistant");

    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", text },
      { id: assistantId, role: "assistant", text: "", thinking: "", streaming: true },
    ]);

    let streamFailed = false;

    try {
      await streamChat(
        {
          session_id: currentSessionId,
          message: text,
          file_ids: uploadedImageFileIds.length > 0 ? uploadedImageFileIds : undefined,
        },
        {
          onToken: (token) => {
            setMessages((prev) =>
              prev.map((message) =>
                message.id === assistantId ? { ...message, text: `${message.text}${token}`, streaming: true } : message
              )
            );
          },
          onThinking: (chunk) => {
            setMessages((prev) =>
              prev.map((message) =>
                message.id === assistantId
                  ? { ...message, thinking: `${message.thinking ?? ""}${chunk}`, streaming: true }
                  : message
              )
            );
          },
          onError: (message) => {
            streamFailed = true;
            setError(normalizeChatError(message));
            setMessages((prev) =>
              prev.map((item) =>
                item.id === assistantId
                  ? { ...item, text: item.text || "Не удалось получить ответ от Asya.", streaming: false }
                  : item
              )
            );
          },
          onDone: () => {
            setMessages((prev) => prev.map((item) => (item.id === assistantId ? { ...item, streaming: false } : item)));
          },
        }
      );
    } catch (streamError) {
      streamFailed = true;
      setError(getErrorMessage(streamError));
      setMessages((prev) =>
        prev.map((item) =>
          item.id === assistantId
            ? { ...item, text: item.text || "Ошибка streaming-ответа. Проверьте backend.", streaming: false }
            : item
        )
      );
    } finally {
      if (!streamFailed && filesToUpload.length > 0) {
        setSelectedFiles([]);
      }
      setIsGenerating(false);
    }
  }

  const sessionStatusText = useMemo(() => {
    if (!sessionId) {
      return "Чат: не выбран";
    }
    return `Чат: ${sessionId.slice(0, 8)}...`;
  }, [sessionId]);

  return (
    <section className="page" aria-label="Чат Asya">
      <div className="page__row">
        <h2 className="page__title">Чат</h2>
        <button type="button" className="chat-action-button" onClick={handleCreateChat} disabled={isGenerating || chatsLoading}>
          Новый чат
        </button>
      </div>

      <div className="chat-layout">
        <aside className="chat-sidebar" aria-label="Список чатов">
          <p className="status-text">{sessionStatusText}</p>
          {chatsLoading ? <p className="status-text">Загрузка чатов...</p> : null}
          {chatsError ? <p className="status-text status-text--error">{chatsError}</p> : null}

          <ul className="chat-sidebar__list">
            {chats.map((chat) => {
              const isActive = chat.id === sessionId;
              const isBase = chat.kind === "base";
              return (
                <li key={chat.id} className="chat-sidebar__item">
                  <button
                    type="button"
                    className={`chat-sidebar__select${isActive ? " chat-sidebar__select--active" : ""}`}
                    onClick={() => setSessionId(chat.id)}
                    disabled={isGenerating}
                  >
                    {isBase ? "Base-chat" : chat.title}
                  </button>
                  {!isBase ? (
                    <div className="chat-sidebar__actions">
                      <button type="button" className="chat-edit-button" onClick={() => void handleRenameChat(chat)} disabled={isGenerating}>
                        Переим.
                      </button>
                      <button type="button" className="chat-edit-button" onClick={() => void handleArchiveChat(chat)} disabled={isGenerating}>
                        Архив
                      </button>
                      <button type="button" className="chat-edit-button" onClick={() => void handleDeleteChat(chat)} disabled={isGenerating}>
                        Удалить
                      </button>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </aside>

        <div className="chat-main">
          {error ? <p className="status-text status-text--error">{error}</p> : null}
          {messagesError ? <p className="status-text status-text--error">{messagesError}</p> : null}
          {messagesLoading ? <p className="status-text">Загрузка истории...</p> : null}

          <div className="chat-list">
            {!hasMessages && !messagesLoading ? <p className="status-text">Сообщений пока нет. Напишите первый запрос.</p> : null}
            {messages.map((message) => (
              <article
                key={message.id}
                className={`chat-bubble ${message.role === "user" ? "chat-bubble--user" : "chat-bubble--assistant"}`}
              >
                <div className="chat-bubble__header">
                  <p className="chat-bubble__role">{message.role === "user" ? "Вы" : "Asya"}</p>
                </div>
                {message.role === "assistant" && message.thinking?.trim() ? (
                  <details className="chat-bubble__thinking" open={Boolean(message.streaming)}>
                    <summary className="chat-bubble__thinking-summary">Размышления модели</summary>
                    <p className="chat-bubble__thinking-text">{message.thinking}</p>
                  </details>
                ) : null}
                <p className="chat-bubble__text">{message.text}</p>
                {message.streaming ? <p className="chat-bubble__streaming">Печатает...</p> : null}
              </article>
            ))}
          </div>

          <form className="chat-form" onSubmit={handleSubmit}>
            <div className="chat-files">
              <label className="settings-form__label" htmlFor="chat-files-input">
                Файлы к сообщению (до {MAX_FILES_PER_MESSAGE})
              </label>
              <input
                id="chat-files-input"
                className="chat-files__input"
                type="file"
                multiple
                onChange={handleSelectFiles}
                disabled={isGenerating || !sessionId}
              />
              {selectedFiles.length ? (
                <ul className="chat-files__list" aria-label="Выбранные файлы">
                  {selectedFiles.map((file, index) => (
                    <li key={makeFileKey(file)} className="chat-files__item">
                      <span className="chat-files__name">
                        {file.name} ({formatSize(file.size)})
                      </span>
                      <button
                        type="button"
                        className="chat-edit-button"
                        onClick={() => removeSelectedFile(index)}
                        disabled={isGenerating}
                      >
                        Удалить
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="status-text">Файлы не выбраны.</p>
              )}
            </div>

            <label className="sr-only" htmlFor="chat-input">
              Сообщение
            </label>
            <textarea
              id="chat-input"
              className="chat-form__input"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              rows={3}
              placeholder="Введите сообщение"
            />
            <button type="submit" className="chat-form__submit" disabled={!canSend || !input.trim()}>
              {isGenerating ? "Генерация..." : "Отправить"}
            </button>
          </form>
        </div>
      </div>
    </section>
  );
}

function pickInitialChatId(chats: ChatListItem[], initialSessionId: string | null): string | null {
  if (initialSessionId && chats.some((chat) => chat.id === initialSessionId && !chat.is_archived)) {
    return initialSessionId;
  }
  const base = chats.find((chat) => chat.kind === "base" && !chat.is_archived);
  if (base) {
    return base.id;
  }
  const first = chats.find((chat) => !chat.is_archived);
  return first?.id ?? null;
}

function makeId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function makeFileKey(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function isSameFile(left: File, right: File): boolean {
  return (
    left.name === right.name &&
    left.size === right.size &&
    left.lastModified === right.lastModified &&
    left.type === right.type
  );
}

function validateSelectedFile(file: File): string | null {
  const extension = getFileExtension(file.name);
  const isDocument = ALLOWED_DOCUMENT_EXTENSIONS.has(extension);
  const isImage = ALLOWED_IMAGE_EXTENSIONS.has(extension) || file.type.toLowerCase().startsWith("image/");

  if (!isDocument && !isImage) {
    return `Файл '${file.name}' не поддерживается. Разрешены PDF, DOCX, XLSX и изображения.`;
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return `Файл '${file.name}' превышает лимит ${MAX_FILE_SIZE_MB} МБ.`;
  }

  return null;
}

function normalizeUploadError(error: unknown): string {
  const raw = getErrorMessage(error);
  const lower = raw.toLowerCase();

  if (lower.includes("не более") && lower.includes("файл")) {
    return `Можно прикрепить не более ${MAX_FILES_PER_MESSAGE} файлов к одному сообщению.`;
  }
  if (lower.includes("превышает лимит")) {
    return `Размер файла превышает лимит ${MAX_FILE_SIZE_MB} МБ.`;
  }
  if (lower.includes("не поддерживается") || lower.includes("разрешены типы")) {
    return "Неподдерживаемый тип файла. Разрешены PDF, DOCX, XLSX и изображения.";
  }

  return raw;
}

function normalizeChatError(message: string): string {
  const lower = message.toLowerCase();
  if (lower.includes("не поддерживает анализ изображений")) {
    return "Выбранная модель не поддерживает изображения. Откройте Настройки и выберите vision-модель.";
  }
  return message;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} Б`;
  }
  const kb = bytes / 1024;
  if (kb < 1024) {
    return `${kb.toFixed(1)} КБ`;
  }
  const mb = kb / 1024;
  return `${mb.toFixed(1)} МБ`;
}

function getFileExtension(filename: string): string {
  const dotIndex = filename.lastIndexOf(".");
  if (dotIndex < 0) {
    return "";
  }
  return filename.slice(dotIndex).toLowerCase();
}

function isImageUpload(file: File | undefined, uploadedContentType: string): boolean {
  if (uploadedContentType.toLowerCase().startsWith("image/")) {
    return true;
  }
  if (!file) {
    return false;
  }
  const extension = getFileExtension(file.name);
  return ALLOWED_IMAGE_EXTENSIONS.has(extension) || file.type.toLowerCase().startsWith("image/");
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Произошла ошибка. Попробуйте позже.";
}

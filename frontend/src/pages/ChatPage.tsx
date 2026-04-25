import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

import { createSession, deleteSession, streamChat, uploadSessionFiles } from "../api/client";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
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

export default function ChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState("");

  const hasMessages = messages.length > 0;
  const canSend = !isGenerating && Boolean(sessionId);

  useEffect(() => {
    let active = true;

    async function initSession() {
      try {
        const created = await createSession();
        if (active) {
          setSessionId(created.session_id);
        }
      } catch (initError) {
        if (active) {
          setError(getErrorMessage(initError));
        }
      }
    }

    initSession();
    return () => {
      active = false;
    };
  }, []);

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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text) {
      return;
    }

    const filesToSend = [...selectedFiles];
    setInput("");
    await sendUserMessage(text, filesToSend);
  }

  async function sendUserMessage(text: string, filesToUpload: File[]): Promise<void> {
    const currentSessionId = await ensureSession();
    if (!currentSessionId) {
      setError("Не удалось создать backend-сессию.");
      return;
    }

    setError(null);
    setIsGenerating(true);

    let uploadedFileIds: string[] = [];
    if (filesToUpload.length > 0) {
      try {
        const uploaded = await uploadSessionFiles(currentSessionId, filesToUpload);
        uploadedFileIds = uploaded.files.map((file) => file.file_id);
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
      { id: assistantId, role: "assistant", text: "", streaming: true },
    ]);

    let streamFailed = false;

    try {
      await streamChat(
        { session_id: currentSessionId, message: text, file_ids: uploadedFileIds },
        {
          onToken: (token) => {
            setMessages((prev) =>
              prev.map((message) =>
                message.id === assistantId
                  ? { ...message, text: `${message.text}${token}`, streaming: true }
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
            setMessages((prev) =>
              prev.map((item) => (item.id === assistantId ? { ...item, streaming: false } : item))
            );
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

  async function ensureSession(): Promise<string | null> {
    if (sessionId) {
      return sessionId;
    }
    try {
      const created = await createSession();
      setSessionId(created.session_id);
      return created.session_id;
    } catch {
      return null;
    }
  }

  async function handleClearSession() {
    if (isGenerating) {
      return;
    }
    setError(null);
    try {
      if (sessionId) {
        await deleteSession(sessionId);
      }
      const created = await createSession();
      setSessionId(created.session_id);
      setMessages([]);
      setSelectedFiles([]);
      setEditingId(null);
      setEditingText("");
    } catch (clearError) {
      setError(getErrorMessage(clearError));
    }
  }

  function startEdit(message: ChatMessage) {
    if (message.role !== "user" || isGenerating) {
      return;
    }
    setEditingId(message.id);
    setEditingText(message.text);
    setError(null);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditingText("");
  }

  async function saveEdit() {
    const nextText = editingText.trim();
    if (!editingId || !nextText || isGenerating) {
      return;
    }

    const targetIndex = messages.findIndex((message) => message.id === editingId && message.role === "user");
    if (targetIndex < 0) {
      cancelEdit();
      return;
    }

    const head = messages.slice(0, targetIndex).filter((item) => item.role === "user").map((item) => item.text);
    const replayUserMessages = [...head, nextText];

    setEditingId(null);
    setEditingText("");
    setSelectedFiles([]);
    setMessages([]);
    setIsGenerating(true);
    setError(null);

    try {
      if (sessionId) {
        await deleteSession(sessionId);
      }
      const created = await createSession();
      setSessionId(created.session_id);

      for (const userText of replayUserMessages) {
        await sendUserMessageInSession(created.session_id, userText);
      }
    } catch (editError) {
      setError(getErrorMessage(editError));
    } finally {
      setIsGenerating(false);
    }
  }

  async function sendUserMessageInSession(currentSessionId: string, text: string) {
    const userId = makeId("user");
    const assistantId = makeId("assistant");

    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", text },
      { id: assistantId, role: "assistant", text: "", streaming: true },
    ]);

    await streamChat(
      { session_id: currentSessionId, message: text },
      {
        onToken: (token) => {
          setMessages((prev) =>
            prev.map((message) =>
              message.id === assistantId
                ? { ...message, text: `${message.text}${token}`, streaming: true }
                : message
            )
          );
        },
        onError: (message) => {
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
          setMessages((prev) =>
            prev.map((item) => (item.id === assistantId ? { ...item, streaming: false } : item))
          );
        },
      }
    );
  }

  const sessionStatusText = useMemo(() => {
    if (!sessionId) {
      return "Сессия: создаётся...";
    }
    return `Сессия: ${sessionId.slice(0, 8)}...`;
  }, [sessionId]);

  return (
    <section className="page" aria-label="Чат Asya">
      <div className="page__row">
        <h2 className="page__title">Чат</h2>
        <button type="button" className="chat-action-button" onClick={handleClearSession} disabled={isGenerating}>
          Очистить сессию
        </button>
      </div>
      <p className="status-text">{sessionStatusText}</p>
      {error ? <p className="status-text status-text--error">{error}</p> : null}

      <div className="chat-list">
        {!hasMessages ? <p className="status-text">Сообщений пока нет. Напишите первый запрос.</p> : null}
        {messages.map((message) => (
          <article
            key={message.id}
            className={`chat-bubble ${message.role === "user" ? "chat-bubble--user" : "chat-bubble--assistant"}`}
          >
            <div className="chat-bubble__header">
              <p className="chat-bubble__role">{message.role === "user" ? "Вы" : "Asya"}</p>
              {message.role === "user" ? (
                <button
                  type="button"
                  className="chat-edit-button"
                  onClick={() => startEdit(message)}
                  disabled={isGenerating}
                >
                  Редактировать
                </button>
              ) : null}
            </div>
            <p className="chat-bubble__text">{message.text}</p>
            {message.streaming ? <p className="chat-bubble__streaming">Печатает...</p> : null}
          </article>
        ))}
      </div>

      {editingId ? (
        <div className="chat-edit-panel">
          <label className="settings-form__label" htmlFor="chat-edit-input">
            Редактирование сообщения
          </label>
          <textarea
            id="chat-edit-input"
            className="chat-form__input"
            value={editingText}
            onChange={(event) => setEditingText(event.target.value)}
            rows={3}
          />
          <div className="chat-edit-panel__actions">
            <button type="button" className="chat-form__submit" onClick={saveEdit} disabled={isGenerating}>
              Сохранить и получить новый ответ
            </button>
            <button type="button" className="chat-action-button" onClick={cancelEdit} disabled={isGenerating}>
              Отмена
            </button>
          </div>
        </div>
      ) : null}

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
    </section>
  );
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

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Произошла ошибка. Попробуйте позже.";
}

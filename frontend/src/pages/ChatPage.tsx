import { FormEvent, useEffect, useMemo, useState } from "react";

import { createSession, deleteSession, streamChat } from "../api/client";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  streaming?: boolean;
}

export default function ChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text) {
      return;
    }
    setInput("");
    await sendUserMessage(text);
  }

  async function sendUserMessage(text: string): Promise<void> {
    const currentSessionId = await ensureSession();
    if (!currentSessionId) {
      setError("Не удалось создать backend-сессию.");
      return;
    }

    setError(null);
    setIsGenerating(true);

    const userId = makeId("user");
    const assistantId = makeId("assistant");

    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", text },
      { id: assistantId, role: "assistant", text: "", streaming: true },
    ]);

    try {
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
            setError(message);
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
      setError(getErrorMessage(streamError));
      setMessages((prev) =>
        prev.map((item) =>
          item.id === assistantId
            ? { ...item, text: item.text || "Ошибка streaming-ответа. Проверьте backend.", streaming: false }
            : item
        )
      );
    } finally {
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
          setError(message);
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

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Произошла ошибка. Попробуйте позже.";
}

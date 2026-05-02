import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

import {
  archiveSpace,
  archiveChat,
  createSpace,
  createChat,
  deleteChat,
  getSpaceSettings,
  getChatMessages,
  getVoiceSettings,
  listSpaces,
  listChats,
  renameSpace,
  renameChat,
  sendVoiceSTT,
  streamChat,
  synthesizeVoiceText,
  updateSpaceSettings,
  uploadSessionFiles,
} from "../api/client";
import type { ChatListItem, SpaceListItem, SpaceMemorySettingsResponse, VoiceSettings } from "../types/api";
import { useVoiceRecorder } from "../hooks/useVoiceRecorder";

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
  currentUserRole?: string;
}

export default function ChatPage({ initialSessionId = null, currentUserRole = "user" }: ChatPageProps) {
  const [chats, setChats] = useState<ChatListItem[]>([]);
  const [chatsLoading, setChatsLoading] = useState(true);
  const [chatsError, setChatsError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId);
  const [spaces, setSpaces] = useState<SpaceListItem[]>([]);
  const [spacesLoading, setSpacesLoading] = useState(true);
  const [spacesError, setSpacesError] = useState<string | null>(null);
  const [selectedSpaceId, setSelectedSpaceId] = useState<string | null>(null);
  const [spaceSettings, setSpaceSettings] = useState<SpaceMemorySettingsResponse | null>(null);
  const [spaceSettingsLoading, setSpaceSettingsLoading] = useState(false);
  const [spaceSettingsError, setSpaceSettingsError] = useState<string | null>(null);
  const [spaceSettingsSaving, setSpaceSettingsSaving] = useState(false);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [messagesError, setMessagesError] = useState<string | null>(null);

  const [input, setInput] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [voiceSettings, setVoiceSettings] = useState<VoiceSettings | null>(null);
  const voiceRecorder = useVoiceRecorder();

  const hasMessages = messages.length > 0;
  const canSend = !isGenerating && Boolean(sessionId);

  useEffect(() => {
    let active = true;

    async function loadInitialData() {
      setChatsLoading(true);
      setSpacesLoading(true);
      setChatsError(null);
      setSpacesError(null);
      try {
        const [chatList, spaceList] = await Promise.all([listChats(), listSpaces()]);
        if (!active) {
          return;
        }
        const visibleSpaces = filterSpacesForUser(spaceList, currentUserRole);
        setSpaces(visibleSpaces);
        setChats(chatList);

        const selected = pickInitialChatId(chatList, initialSessionId);
        if (selected) {
          setSessionId(selected);
        }
        const initialSpace = pickInitialSpaceId(chatList, visibleSpaces, selected, initialSessionId);
        setSelectedSpaceId(initialSpace);
      } catch (loadError) {
        if (!active) {
          return;
        }
        const message = getErrorMessage(loadError);
        setChatsError(message);
        setSpacesError(message);
      } finally {
        if (active) {
          setChatsLoading(false);
          setSpacesLoading(false);
        }
      }
    }

    void loadInitialData();
    return () => {
      active = false;
    };
  }, [initialSessionId, currentUserRole]);

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

  useEffect(() => {
    if (!selectedSpaceId) {
      setSpaceSettings(null);
      return;
    }
    let active = true;

    async function loadSettings(spaceId: string) {
      setSpaceSettingsLoading(true);
      setSpaceSettingsError(null);
      try {
        const data = await getSpaceSettings(spaceId);
        if (!active) {
          return;
        }
        setSpaceSettings(data);
      } catch (loadError) {
        if (!active) {
          return;
        }
        setSpaceSettings(null);
        setSpaceSettingsError(getErrorMessage(loadError));
      } finally {
        if (active) {
          setSpaceSettingsLoading(false);
        }
      }
    }

    void loadSettings(selectedSpaceId);
    return () => {
      active = false;
    };
  }, [selectedSpaceId]);

  useEffect(() => {
    let active = true;
    async function loadVoice() {
      try {
        const data = await getVoiceSettings();
        if (!active) return;
        setVoiceSettings(data);
      } catch {
        if (!active) return;
        setVoiceSettings(null);
      }
    }
    void loadVoice();
    return () => { active = false; };
  }, []);

  const visibleChats = useMemo(() => {
    if (!selectedSpaceId) {
      return chats.filter((chat) => !chat.is_archived);
    }
    return chats.filter((chat) => !chat.is_archived && chat.space_id === selectedSpaceId);
  }, [chats, selectedSpaceId]);

  useEffect(() => {
    if (!visibleChats.length) {
      return;
    }
    if (sessionId && visibleChats.some((chat) => chat.id === sessionId)) {
      return;
    }
    const fallback = pickInitialChatId(visibleChats, null);
    setSessionId(fallback);
  }, [visibleChats, sessionId]);

  async function handleVoiceToggle() {
    if (isGenerating || !canSend) return;
    if (voiceRecorder.isRecording) {
      const blob = await voiceRecorder.stop();
      if (!blob) return;
      try {
        setError(null);
        const stt = await sendVoiceSTT(blob);
        const text = (stt.text || "").trim();
        if (text) {
          await sendUserMessageInSession(sessionId!, text, []);
        }
      } catch (sttError) {
        setError(getErrorMessage(sttError));
      }
    } else {
      await voiceRecorder.start();
    }
  }

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
      const chat = await createChat({ title: "Новый чат", space_id: selectedSpaceId });
      setChats((prev) => [...prev.filter((item) => item.id !== chat.id), chat]);
      setSessionId(chat.id);
      setMessages([]);
      setSelectedFiles([]);
      setInput("");
    } catch (createError) {
      setError(getErrorMessage(createError));
    }
  }

  async function refreshSpacesAndChats(preserveSessionId: string | null) {
    const [nextSpacesRaw, nextChats] = await Promise.all([listSpaces(), listChats()]);
    const nextSpaces = filterSpacesForUser(nextSpacesRaw, currentUserRole);
    setSpaces(nextSpaces);
    setChats(nextChats);
    if (selectedSpaceId && !nextSpaces.some((space) => space.id === selectedSpaceId)) {
      const fallbackSpace = nextSpaces[0]?.id ?? null;
      setSelectedSpaceId(fallbackSpace);
    }
    if (preserveSessionId && nextChats.some((chat) => chat.id === preserveSessionId && !chat.is_archived)) {
      setSessionId(preserveSessionId);
      return;
    }
    const nextActiveChats = selectedSpaceId
      ? nextChats.filter((chat) => !chat.is_archived && chat.space_id === selectedSpaceId)
      : nextChats.filter((chat) => !chat.is_archived);
    setSessionId(pickInitialChatId(nextActiveChats, null));
  }

  async function handleCreateSpace() {
    if (isGenerating) {
      return;
    }
    const name = window.prompt("Название пространства", "Новое пространство")?.trim();
    if (!name) {
      return;
    }
    try {
      const created = await createSpace({ name });
      setSpaces((prev) => [...prev, created]);
      setSelectedSpaceId(created.id);
      setError(null);
    } catch (createError) {
      setError(getErrorMessage(createError));
    }
  }

  async function handleRenameSpace(space: SpaceListItem) {
    if (isGenerating) {
      return;
    }
    const nextName = window.prompt("Новое название пространства", space.name)?.trim();
    if (!nextName) {
      return;
    }
    try {
      const updated = await renameSpace(space.id, { name: nextName });
      setSpaces((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setError(null);
    } catch (renameError) {
      setError(getErrorMessage(renameError));
    }
  }

  async function handleArchiveSpace(space: SpaceListItem) {
    if (isGenerating) {
      return;
    }
    if (!window.confirm(`Архивировать пространство '${space.name}'?`)) {
      return;
    }
    try {
      await archiveSpace(space.id);
      await refreshSpacesAndChats(sessionId);
      setError(null);
    } catch (archiveError) {
      setError(getErrorMessage(archiveError));
    }
  }

  async function handleUpdateSpaceSetting(
    key: keyof Pick<
      SpaceMemorySettingsResponse,
      "memory_read_enabled" | "memory_write_enabled" | "behavior_rules_enabled" | "personality_overlay_enabled"
    >,
    value: boolean
  ) {
    if (!selectedSpaceId || !spaceSettings) {
      return;
    }
    const next = { ...spaceSettings, [key]: value };
    setSpaceSettings(next);
    setSpaceSettingsSaving(true);
    setSpaceSettingsError(null);
    try {
      const saved = await updateSpaceSettings(selectedSpaceId, {
        memory_read_enabled: next.memory_read_enabled,
        memory_write_enabled: next.memory_write_enabled,
        behavior_rules_enabled: next.behavior_rules_enabled,
        personality_overlay_enabled: next.personality_overlay_enabled,
      });
      setSpaceSettings(saved);
    } catch (updateError) {
      setSpaceSettingsError(getErrorMessage(updateError));
      setSpaceSettings(spaceSettings);
    } finally {
      setSpaceSettingsSaving(false);
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
            setMessages((prev) => {
              const updated = prev.map((item) =>
                item.id === assistantId ? { ...item, streaming: false } : item
              );
              const assistantMsg = updated.find((m) => m.id === assistantId);
              if (voiceSettings?.tts_enabled && assistantMsg?.text.trim()) {
                void playTTS(assistantMsg.text);
              }
              return updated;
            });
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

  const selectedSpace = useMemo(
    () => spaces.find((space) => space.id === selectedSpaceId) ?? null,
    [spaces, selectedSpaceId]
  );

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
          <div className="spaces-panel">
            <div className="spaces-panel__header">
              <p className="spaces-panel__title">Пространства</p>
              <button
                type="button"
                className="chat-edit-button"
                onClick={() => void handleCreateSpace()}
                disabled={isGenerating || spacesLoading}
              >
                + Создать
              </button>
            </div>
            {spacesLoading ? <p className="status-text">Загрузка пространств...</p> : null}
            {spacesError ? <p className="status-text status-text--error">{spacesError}</p> : null}
            <ul className="spaces-panel__list">
              {spaces.map((space) => {
                const active = space.id === selectedSpaceId;
                return (
                  <li key={space.id} className="spaces-panel__item">
                    <button
                      type="button"
                      className={`chat-sidebar__select${active ? " chat-sidebar__select--active" : ""}`}
                      onClick={() => setSelectedSpaceId(space.id)}
                      disabled={isGenerating}
                    >
                      {space.name}
                      {space.is_default ? " (по умолчанию)" : ""}
                      {space.is_admin_only ? " (admin)" : ""}
                    </button>
                    {!space.is_default ? (
                      <div className="chat-sidebar__actions">
                        <button
                          type="button"
                          className="chat-edit-button"
                          onClick={() => void handleRenameSpace(space)}
                          disabled={isGenerating}
                        >
                          Переим.
                        </button>
                        <button
                          type="button"
                          className="chat-edit-button"
                          onClick={() => void handleArchiveSpace(space)}
                          disabled={isGenerating}
                        >
                          Архив
                        </button>
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
            {selectedSpace ? <p className="status-text">Текущее пространство: {selectedSpace.name}</p> : null}
            <div className="spaces-settings">
              <p className="spaces-settings__title">Память пространства</p>
              {spaceSettingsLoading ? <p className="status-text">Загрузка настроек...</p> : null}
              {spaceSettingsError ? <p className="status-text status-text--error">{spaceSettingsError}</p> : null}
              {spaceSettings ? (
                <>
                  <label className="spaces-settings__toggle">
                    <input
                      type="checkbox"
                      checked={spaceSettings.memory_read_enabled}
                      onChange={(event) => void handleUpdateSpaceSetting("memory_read_enabled", event.target.checked)}
                      disabled={spaceSettingsSaving}
                    />
                    Читать память
                  </label>
                  <label className="spaces-settings__toggle">
                    <input
                      type="checkbox"
                      checked={spaceSettings.memory_write_enabled}
                      onChange={(event) => void handleUpdateSpaceSetting("memory_write_enabled", event.target.checked)}
                      disabled={spaceSettingsSaving}
                    />
                    Записывать память
                  </label>
                  <label className="spaces-settings__toggle">
                    <input
                      type="checkbox"
                      checked={spaceSettings.behavior_rules_enabled}
                      onChange={(event) => void handleUpdateSpaceSetting("behavior_rules_enabled", event.target.checked)}
                      disabled={spaceSettingsSaving}
                    />
                    Использовать правила
                  </label>
                  <label className="spaces-settings__toggle">
                    <input
                      type="checkbox"
                      checked={spaceSettings.personality_overlay_enabled}
                      onChange={(event) =>
                        void handleUpdateSpaceSetting("personality_overlay_enabled", event.target.checked)
                      }
                      disabled={spaceSettingsSaving}
                    />
                    Использовать personality overlay
                  </label>
                </>
              ) : null}
            </div>
          </div>

          <p className="status-text">{sessionStatusText}</p>
          {chatsLoading ? <p className="status-text">Загрузка чатов...</p> : null}
          {chatsError ? <p className="status-text status-text--error">{chatsError}</p> : null}

          <ul className="chat-sidebar__list">
            {visibleChats.map((chat) => {
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
                    {isBase ? "Base-chat (базовый)" : chat.title}
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
            {voiceRecorder.isSupported ? (
              <button
                type="button"
                className={`chat-form__submit${voiceRecorder.isRecording ? " chat-form__submit--recording" : ""}`}
                onClick={() => void handleVoiceToggle()}
                disabled={!canSend}
              >
                {voiceRecorder.isRecording ? "Стоп" : "Микрофон"}
              </button>
            ) : null}
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

function pickInitialSpaceId(
  chats: ChatListItem[],
  spaces: SpaceListItem[],
  selectedChatId: string | null,
  initialSessionId: string | null
): string | null {
  const chatId = selectedChatId || initialSessionId;
  if (chatId) {
    const selectedChat = chats.find((chat) => chat.id === chatId && !chat.is_archived);
    if (selectedChat?.space_id && spaces.some((space) => space.id === selectedChat.space_id)) {
      return selectedChat.space_id;
    }
  }
  const baseChat = chats.find((chat) => chat.kind === "base" && !chat.is_archived);
  if (baseChat?.space_id && spaces.some((space) => space.id === baseChat.space_id)) {
    return baseChat.space_id;
  }
  const defaultSpace = spaces.find((space) => space.is_default && !space.is_archived);
  if (defaultSpace) {
    return defaultSpace.id;
  }
  return spaces.find((space) => !space.is_archived)?.id ?? null;
}

function filterSpacesForUser(spaces: SpaceListItem[], role: string): SpaceListItem[] {
  if (role === "admin") {
    return spaces.filter((space) => !space.is_archived);
  }
  return spaces.filter((space) => !space.is_archived && !space.is_admin_only);
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

async function playTTS(text: string): Promise<void> {
  try {
    const audioBuffer = await synthesizeVoiceText({ text });
    const blob = new Blob([audioBuffer], { type: "audio/mpeg" });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.onended = () => URL.revokeObjectURL(url);
    await audio.play();
  } catch {
    // best-effort: audio playback failure should never break chat
  }
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Произошла ошибка. Попробуйте позже.";
}

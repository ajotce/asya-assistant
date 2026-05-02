import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import {
  createDiaryEntry,
  createDiaryEntryAudio,
  deleteDiaryEntry,
  getDiarySettings,
  listDiaryEntries,
  patchDiarySettings,
  runObserver,
} from "../api/client";
import type { DiaryEntryItem, DiarySettingsResponse } from "../types/api";

export default function DiaryPage() {
  const [settings, setSettings] = useState<DiarySettingsResponse | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [entries, setEntries] = useState<DiaryEntryItem[]>([]);
  const [entriesLoading, setEntriesLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [inputTitle, setInputTitle] = useState("");
  const [inputContent, setInputContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const loadAll = useCallback(async (query?: string) => {
    setSettingsLoading(true);
    setEntriesLoading(true);
    setError(null);
    try {
      const [s, e] = await Promise.all([getDiarySettings(), listDiaryEntries(query || undefined)]);
      setSettings(s);
      setEntries(e);
    } catch (err) {
      setError(getErr(err));
    } finally {
      setSettingsLoading(false);
      setEntriesLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  async function loadEntries(q?: string) {
    setEntriesLoading(true);
    try {
      setEntries(await listDiaryEntries(q || undefined));
    } catch (err) {
      setError(getErr(err));
    } finally {
      setEntriesLoading(false);
    }
  }

  async function handleSearchSubmit(e: FormEvent) {
    e.preventDefault();
    await loadEntries(searchQuery || undefined);
  }

  async function handleSaveSettings() {
    if (!settings) return;
    setSaving(true);
    setError(null);
    try {
      setSettings(await patchDiarySettings(settings));
    } catch (err) {
      setError(getErr(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateEntry(e: FormEvent) {
    e.preventDefault();
    if (!inputContent.trim() && !inputTitle.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await createDiaryEntry({ title: inputTitle || "Запись дневника", content: inputContent });
      setInputTitle("");
      setInputContent("");
      await loadEntries(searchQuery || undefined);
    } catch (err) {
      setError(getErr(err));
    } finally {
      setSaving(false);
    }
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        try {
          await createDiaryEntryAudio(blob);
          await loadEntries(searchQuery || undefined);
        } catch (err) {
          setError(getErr(err));
        }
        stream.getTracks().forEach((t) => t.stop());
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch {
      setError("Нет доступа к микрофону");
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  }

  async function handleDelete(entryId: string) {
    if (!window.confirm("Удалить запись?")) return;
    setError(null);
    try {
      await deleteDiaryEntry(entryId);
      await loadEntries(searchQuery || undefined);
    } catch (err) {
      setError(getErr(err));
    }
  }

  return (
    <section className="page" aria-label="Дневник">
      <div className="page__row">
        <h2 className="page__title">Дневник</h2>
        <button type="button" className="chat-action-button" onClick={() => { void runObserver(); void loadAll(searchQuery || undefined); }}>
          Обновить
        </button>
      </div>

      {error ? <p className="status-text status-text--error">{error}</p> : null}

      <div className="diary-settings memory-section">
        <h3 className="memory-section__title">Настройки дневника</h3>
        {settingsLoading ? <p className="status-text">Загрузка...</p> : null}
        {settings ? (
          <div className="spaces-settings">
            <label className="spaces-settings__toggle">
              <input
                type="checkbox"
                checked={settings.briefing_enabled}
                onChange={(e) => setSettings({ ...settings, briefing_enabled: e.target.checked })}
              />
              Брифинги
            </label>
            <label className="spaces-settings__toggle">
              <input
                type="checkbox"
                checked={settings.search_enabled}
                onChange={(e) => setSettings({ ...settings, search_enabled: e.target.checked })}
              />
              Поиск
            </label>
            <label className="spaces-settings__toggle">
              <input
                type="checkbox"
                checked={settings.memories_enabled}
                onChange={(e) => setSettings({ ...settings, memories_enabled: e.target.checked })}
              />
              Воспоминания
            </label>
            <label className="spaces-settings__toggle">
              <input
                type="checkbox"
                checked={settings.evening_prompt_enabled}
                onChange={(e) => setSettings({ ...settings, evening_prompt_enabled: e.target.checked })}
              />
              Вечернее предложение
            </label>
            <button type="button" className="chat-action-button" onClick={() => void handleSaveSettings()} disabled={saving}>
              Сохранить
            </button>
          </div>
        ) : null}
      </div>

      <div className="diary-create memory-section">
        <h3 className="memory-section__title">Новая запись</h3>
        <form className="settings-form" onSubmit={handleCreateEntry}>
          <input
            className="settings-form__input"
            value={inputTitle}
            onChange={(e) => setInputTitle(e.target.value)}
            placeholder="Название (необязательно)"
          />
          <textarea
            className="settings-form__textarea"
            value={inputContent}
            onChange={(e) => setInputContent(e.target.value)}
            rows={4}
            placeholder="Текст записи..."
          />
          <div className="chat-edit-panel__actions">
            <button type="submit" className="chat-action-button" disabled={saving}>
              Сохранить текст
            </button>
            {!isRecording ? (
              <button type="button" className="chat-action-button" onClick={() => void startRecording()} disabled={saving}>
                Запись аудио
              </button>
            ) : (
              <button type="button" className="chat-action-button" onClick={stopRecording}>
                Стоп (запись)
              </button>
            )}
          </div>
        </form>
      </div>

      <div className="diary-search memory-section">
        <form className="settings-form" onSubmit={handleSearchSubmit}>
          <input
            className="settings-form__input"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Поиск по записям..."
          />
        </form>
      </div>

      {entriesLoading ? <p className="status-text">Загрузка записей...</p> : null}
      {!entriesLoading && !entries.length ? (
        <p className="status-text">Записей пока нет.</p>
      ) : null}
      <ul className="memory-list">
        {entries.map((entry) => (
          <li key={entry.id} className="memory-list__item">
            <div className="diary-entry__header">
              <h3 className="memory-list__title">{entry.title}</h3>
              <span className="status-badge status-badge--unknown">
                {entry.processing_status === "processed" ? "OK" : entry.processing_status}
              </span>
            </div>
            <p className="memory-list__text">{entry.content || entry.transcript}</p>
            <div className="diary-entry__meta">
              {entry.topics.length > 0 && (
                <p className="status-text">Темы: {entry.topics.join(", ")}</p>
              )}
              {entry.decisions.length > 0 && (
                <p className="status-text">Решения: {entry.decisions.join(", ")}</p>
              )}
              {entry.mentions.length > 0 && (
                <p className="status-text">Упоминания: {entry.mentions.join(", ")}</p>
              )}
            </div>
            {expandedId === entry.id && entry.transcript && !entry.content && (
              <details open>
                <summary>Транскрипция</summary>
                <p className="status-text">{entry.transcript}</p>
              </details>
            )}
            <div className="memory-actions">
              <button
                type="button"
                className="chat-edit-button"
                onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
              >
                {expandedId === entry.id ? "Свернуть" : "Подробнее"}
              </button>
              <button type="button" className="chat-edit-button" onClick={() => void handleDelete(entry.id)}>
                Удалить
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function getErr(err: unknown): string {
  return err instanceof Error ? err.message : "Ошибка";
}

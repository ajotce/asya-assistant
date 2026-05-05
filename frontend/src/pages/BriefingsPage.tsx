import { useCallback, useEffect, useState } from "react";

import {
  generateBriefing,
  getBriefingItem,
  getBriefingSettings,
  listBriefingsArchive,
  patchBriefingSettings,
} from "../api/client";
import type { BriefingArchiveItem, BriefingItem, BriefingSettingsResponse } from "../types/api";

export default function BriefingsPage() {
  const [settings, setSettings] = useState<BriefingSettingsResponse | null>(null);
  const [archive, setArchive] = useState<BriefingArchiveItem[]>([]);
  const [selected, setSelected] = useState<BriefingItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextSettings, nextArchive] = await Promise.all([getBriefingSettings(), listBriefingsArchive()]);
      setSettings(nextSettings);
      setArchive(nextArchive);
      if (nextArchive.length > 0) {
        const first = await getBriefingItem(nextArchive[0].id);
        setSelected(first);
      } else {
        setSelected(null);
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function saveSettings() {
    if (!settings) return;
    setSaving(true);
    setError(null);
    try {
      setSettings(await patchBriefingSettings(settings));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function manualGenerate(kind: "morning" | "evening") {
    setSaving(true);
    setError(null);
    try {
      const response = await generateBriefing(kind);
      const nextArchive = await listBriefingsArchive();
      setArchive(nextArchive);
      setSelected(response.briefing);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function openItem(id: string) {
    setSaving(true);
    setError(null);
    try {
      setSelected(await getBriefingItem(id));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="page" aria-label="Брифинги Asya">
      <div className="page__row">
        <h2 className="page__title">Брифинги</h2>
        <button type="button" className="chat-action-button" onClick={() => void load()} disabled={loading || saving}>
          Обновить
        </button>
      </div>

      {error ? <p className="status-text status-text--error">{error}</p> : null}
      {loading ? <p className="status-text">Загрузка...</p> : null}

      {settings ? (
        <div className="memory-section">
          <h3 className="memory-section__title">Настройки</h3>
          <div className="spaces-settings">
            <label className="spaces-settings__toggle" htmlFor="briefings-morning-enabled">
              <input
                id="briefings-morning-enabled"
                type="checkbox"
                checked={settings.morning_enabled}
                onChange={(event) => setSettings({ ...settings, morning_enabled: event.target.checked })}
              />
              Утренний брифинг
            </label>
            <label className="spaces-settings__toggle" htmlFor="briefings-evening-enabled">
              <input
                id="briefings-evening-enabled"
                type="checkbox"
                checked={settings.evening_enabled}
                onChange={(event) => setSettings({ ...settings, evening_enabled: event.target.checked })}
              />
              Вечерний итог
            </label>
            <label className="spaces-settings__toggle" htmlFor="briefings-delivery-in-app">
              <input
                id="briefings-delivery-in-app"
                type="checkbox"
                checked={settings.delivery_in_app}
                onChange={(event) => setSettings({ ...settings, delivery_in_app: event.target.checked })}
              />
              Доставка в Notification Center
            </label>
            <label className="spaces-settings__toggle" htmlFor="briefings-delivery-telegram">
              <input
                id="briefings-delivery-telegram"
                type="checkbox"
                checked={settings.delivery_telegram}
                onChange={(event) => setSettings({ ...settings, delivery_telegram: event.target.checked })}
              />
              Доставка в Telegram
            </label>
            <button type="button" className="chat-action-button" onClick={() => void saveSettings()} disabled={saving}>
              Сохранить настройки
            </button>
          </div>
        </div>
      ) : null}

      <div className="memory-section">
        <h3 className="memory-section__title">Ручная генерация</h3>
        <div className="chat-edit-panel__actions">
          <button type="button" className="chat-action-button" onClick={() => void manualGenerate("morning")} disabled={saving}>
            Сгенерировать утренний
          </button>
          <button type="button" className="chat-action-button" onClick={() => void manualGenerate("evening")} disabled={saving}>
            Сгенерировать вечерний
          </button>
        </div>
      </div>

      <div className="memory-section">
        <h3 className="memory-section__title">Архив последних брифингов</h3>
        {archive.length === 0 ? <p className="status-text">Архив пока пуст.</p> : null}
        <ul className="memory-list">
          {archive.map((item) => (
            <li key={item.id} className="memory-list__item">
              <button type="button" className="chat-action-button" onClick={() => void openItem(item.id)}>
                {item.title}
              </button>
              <p className="status-text">
                {new Date(item.created_at).toLocaleString()} · in-app: {item.delivered_in_app ? "да" : "нет"} · telegram: {item.delivered_telegram ? "да" : "нет"}
              </p>
            </li>
          ))}
        </ul>
      </div>

      <div className="memory-section">
        <h3 className="memory-section__title">Содержимое брифинга</h3>
        {!selected ? <p className="status-text">Выберите брифинг из архива.</p> : null}
        {selected ? (
          <>
            <p className="status-text">{selected.title}</p>
            <pre className="chat-message__content">{selected.content_markdown}</pre>
          </>
        ) : null}
      </div>
    </section>
  );
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Не удалось выполнить запрос.";
}

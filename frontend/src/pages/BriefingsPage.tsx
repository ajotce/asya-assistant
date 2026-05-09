import { useEffect, useMemo, useState } from "react";

import {
  generateBriefing,
  getBriefingSettings,
  listBriefings,
  patchBriefingSettings,
  type BriefingItem,
  type BriefingSettingsPatchRequest,
} from "../api/client";

export default function BriefingsPage() {
  const [items, setItems] = useState<BriefingItem[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<BriefingSettingsPatchRequest>({
    timezone: "Europe/Moscow",
    morning_enabled: true,
    evening_enabled: true,
    morning_time: "08:00",
    evening_time: "19:00",
    channel_in_app: true,
    channel_telegram: false,
  });

  useEffect(() => {
    void reload();
  }, []);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const [briefings, prefs] = await Promise.all([listBriefings(30, 100), getBriefingSettings()]);
      setItems(briefings);
      setActiveId(briefings[0]?.id ?? null);
      setSettings({
        timezone: prefs.timezone,
        morning_enabled: prefs.morning_enabled,
        evening_enabled: prefs.evening_enabled,
        morning_time: prefs.morning_time,
        evening_time: prefs.evening_time,
        channel_in_app: prefs.channel_in_app,
        channel_telegram: prefs.channel_telegram,
      });
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }

  const active = useMemo(() => items.find((item) => item.id === activeId) ?? items[0] ?? null, [items, activeId]);

  async function handleGenerate(kind: "morning" | "evening") {
    setSaving(true);
    setError(null);
    try {
      const created = await generateBriefing(kind);
      setItems((prev) => [created, ...prev]);
      setActiveId(created.id);
    } catch (genError) {
      setError(getErrorMessage(genError));
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveSettings() {
    setSaving(true);
    setError(null);
    try {
      await patchBriefingSettings(settings);
    } catch (saveError) {
      setError(getErrorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="page">
      <h2 className="page__title">Брифинги</h2>
      {loading ? <p className="status-text">Загрузка...</p> : null}
      {error ? <p className="status-text status-text--error">{error}</p> : null}

      <div className="page__row">
        <button className="chat-action-button" type="button" disabled={saving} onClick={() => void handleGenerate("morning")}>Generate morning</button>
        <button className="chat-action-button" type="button" disabled={saving} onClick={() => void handleGenerate("evening")}>Generate evening</button>
      </div>

      <div className="memory-section">
        <h3 className="memory-section__title">Настройки брифингов</h3>
        <div className="settings-grid">
          <label>
            Timezone
            <input value={settings.timezone} onChange={(e) => setSettings({ ...settings, timezone: e.target.value })} />
          </label>
          <label>
            Morning time
            <input value={settings.morning_time} onChange={(e) => setSettings({ ...settings, morning_time: e.target.value })} />
          </label>
          <label>
            Evening time
            <input value={settings.evening_time} onChange={(e) => setSettings({ ...settings, evening_time: e.target.value })} />
          </label>
          <label><input type="checkbox" checked={settings.morning_enabled} onChange={(e) => setSettings({ ...settings, morning_enabled: e.target.checked })} /> Morning enabled</label>
          <label><input type="checkbox" checked={settings.evening_enabled} onChange={(e) => setSettings({ ...settings, evening_enabled: e.target.checked })} /> Evening enabled</label>
          <label><input type="checkbox" checked={settings.channel_in_app} onChange={(e) => setSettings({ ...settings, channel_in_app: e.target.checked })} /> In-app</label>
          <label><input type="checkbox" checked={settings.channel_telegram} onChange={(e) => setSettings({ ...settings, channel_telegram: e.target.checked })} /> Telegram</label>
        </div>
        <button className="chat-action-button" type="button" disabled={saving} onClick={() => void handleSaveSettings()}>
          Сохранить
        </button>
      </div>

      <div className="memory-section">
        <h3 className="memory-section__title">Архив за 30 дней</h3>
        <div className="page__row" style={{ alignItems: "flex-start" }}>
          <div style={{ minWidth: 280 }}>
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`chat-action-button${active?.id === item.id ? " nav-tabs__button--active" : ""}`}
                onClick={() => setActiveId(item.id)}
              >
                {item.kind} · {new Date(item.created_at).toLocaleString()}
              </button>
            ))}
          </div>
          <article className="chat-bubble" style={{ width: "100%" }}>
            <pre className="chat-bubble__text">{active?.content || "Нет данных"}</pre>
          </article>
        </div>
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

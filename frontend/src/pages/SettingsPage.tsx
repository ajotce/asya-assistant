import { FormEvent, useEffect, useState } from "react";

import { getModels, getSettings, updateSettings } from "../api/client";
import type { ModelInfo, SettingsResponse } from "../types/api";

interface SettingsFormState {
  assistant_name: string;
  selected_model: string;
  system_prompt: string;
}

const emptyState: SettingsFormState = {
  assistant_name: "",
  selected_model: "",
  system_prompt: "",
};

export default function SettingsPage() {
  const [form, setForm] = useState<SettingsFormState>(emptyState);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const [apiKeyConfigured, setApiKeyConfigured] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadSettings() {
      setLoading(true);
      setError(null);
      try {
        const data = await getSettings();
        if (!active) {
          return;
        }
        applySettings(data);
        await loadModels(data.selected_model, active);
      } catch (loadError) {
        if (!active) {
          return;
        }
        setError(getErrorMessage(loadError));
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadSettings();
    return () => {
      active = false;
    };
  }, []);

  async function loadModels(selectedModel: string, active = true) {
    setModelsLoading(true);
    setModelsError(null);
    try {
      const list = await getModels();
      if (!active) {
        return;
      }
      setModels(list);
      if (list.length > 0) {
        const hasCurrent = list.some((model) => model.id === selectedModel);
        if (!hasCurrent) {
          setForm((prev) => ({ ...prev, selected_model: list[0].id }));
        }
      }
    } catch (modelsLoadError) {
      if (!active) {
        return;
      }
      setModels([]);
      setModelsError(getErrorMessage(modelsLoadError));
    } finally {
      if (active) {
        setModelsLoading(false);
      }
    }
  }

  function applySettings(settings: SettingsResponse) {
    setForm({
      assistant_name: settings.assistant_name,
      selected_model: settings.selected_model,
      system_prompt: settings.system_prompt,
    });
    setApiKeyConfigured(settings.api_key_configured);
  }

  function updateField<K extends keyof SettingsFormState>(key: K, value: SettingsFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setSavedMessage(null);
    try {
      const updated = await updateSettings(form);
      applySettings(updated);
      setSavedMessage("Настройки сохранены.");
    } catch (saveError) {
      setError(getErrorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <section className="page" aria-label="Настройки Asya">
        <h2 className="page__title">Настройки</h2>
        <p className="status-text">Загрузка настроек...</p>
      </section>
    );
  }

  return (
    <section className="page" aria-label="Настройки Asya">
      <h2 className="page__title">Настройки</h2>

      {error ? <p className="status-text status-text--error">{error}</p> : null}
      {savedMessage ? <p className="status-text status-text--ok">{savedMessage}</p> : null}

      <form className="settings-form" onSubmit={handleSubmit}>
        <p className="status-text">VseLLM API-ключ: {apiKeyConfigured ? "настроен" : "не настроен"}</p>
        <label className="settings-form__label" htmlFor="assistant-name">
          Имя ассистента
        </label>
        <input
          id="assistant-name"
          className="settings-form__input"
          value={form.assistant_name}
          onChange={(event) => updateField("assistant_name", event.target.value)}
          placeholder="Asya"
        />

        <div className="settings-form__row">
          <label className="settings-form__label" htmlFor="selected-model">
            Глобально выбранная модель
          </label>
          <button
            type="button"
            className="chat-action-button"
            onClick={() => loadModels(form.selected_model)}
            disabled={modelsLoading || saving}
          >
            {modelsLoading ? "Обновление..." : "Обновить список"}
          </button>
        </div>

        {modelsError ? <p className="status-text status-text--error">{modelsError}</p> : null}

        {models.length > 0 ? (
          <select
            id="selected-model"
            className="settings-form__input"
            value={form.selected_model}
            onChange={(event) => updateField("selected_model", event.target.value)}
          >
            {models.map((model) => (
              <option key={model.id} value={model.id}>
                {model.id}
              </option>
            ))}
          </select>
        ) : (
          <input
            id="selected-model"
            className="settings-form__input"
            value={form.selected_model}
            onChange={(event) => updateField("selected_model", event.target.value)}
            placeholder="openai/gpt-5"
          />
        )}

        <label className="settings-form__label" htmlFor="system-prompt">
          Системный промт
        </label>
        <textarea
          id="system-prompt"
          className="settings-form__textarea"
          value={form.system_prompt}
          onChange={(event) => updateField("system_prompt", event.target.value)}
          rows={6}
        />

        <button type="submit" className="settings-form__submit" disabled={saving}>
          {saving ? "Сохранение..." : "Сохранить"}
        </button>
      </form>
    </section>
  );
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Произошла ошибка. Попробуйте позже.";
}

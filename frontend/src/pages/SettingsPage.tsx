import { FormEvent, useEffect, useState } from "react";

import {
  downloadDocumentTemplateFill,
  getModels,
  getReasoningCache,
  getSettings,
  listDocumentTemplates,
  previewDocumentTemplateFill,
  probeReasoningModels,
  updateSettings,
} from "../api/client";
import AdminAccessRequestsSection from "../components/AdminAccessRequestsSection";
import type { ThemePreference } from "../hooks/useTheme";
import type { DocumentTemplateItem, ModelInfo, ReasoningProbeItem, SettingsResponse } from "../types/api";

interface SettingsPageProps {
  themePreference: ThemePreference;
  onThemePreferenceChange: (preference: ThemePreference) => void;
  currentUserRole?: string;
}

const THEME_OPTIONS: ReadonlyArray<{ value: ThemePreference; label: string }> = [
  { value: "light", label: "Светлая" },
  { value: "dark", label: "Тёмная" },
  { value: "system", label: "Системная" },
];

const REASONING_HEURISTIC_TOKENS = ["thinking", "reasoning", "-r1", "/o3", "-o3"];

export function isLikelyReasoningModel(modelId: string): boolean {
  const lower = modelId.toLowerCase();
  return REASONING_HEURISTIC_TOKENS.some((token) => lower.includes(token));
}

interface SettingsFormState {
  assistant_name: string;
  selected_model: string;
  system_prompt: string;
  default_storage_provider: string;
  default_storage_folders: Record<string, string>;
}

const emptyState: SettingsFormState = {
  assistant_name: "",
  selected_model: "",
  system_prompt: "",
  default_storage_provider: "google_drive",
  default_storage_folders: {},
};

export default function SettingsPage({ themePreference, onThemePreferenceChange, currentUserRole }: SettingsPageProps) {
  const [form, setForm] = useState<SettingsFormState>(emptyState);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const [apiKeyConfigured, setApiKeyConfigured] = useState(false);
  const [reasoningResults, setReasoningResults] = useState<ReasoningProbeItem[]>([]);
  const [reasoningProbeLoading, setReasoningProbeLoading] = useState(false);
  const [reasoningError, setReasoningError] = useState<string | null>(null);
  const [reasoningProbeRanOnce, setReasoningProbeRanOnce] = useState(false);
  const [templates, setTemplates] = useState<DocumentTemplateItem[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");
  const [templateValues, setTemplateValues] = useState<Record<string, string>>({});
  const [templateMessage, setTemplateMessage] = useState<string | null>(null);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const [templateLoading, setTemplateLoading] = useState(false);

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

  useEffect(() => {
    let active = true;
    async function loadTemplates() {
      try {
        const items = await listDocumentTemplates();
        if (!active) {
          return;
        }
        setTemplates(items);
        if (items.length > 0) {
          setSelectedTemplateId(items[0].id);
        }
      } catch {
        if (!active) {
          return;
        }
        setTemplateError("Не удалось загрузить шаблоны документов.");
      }
    }
    loadTemplates();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    async function loadCachedProbe() {
      try {
        const cache = await getReasoningCache();
        if (!active) {
          return;
        }
        if (cache.results.length > 0) {
          setReasoningResults(cache.results);
          setReasoningProbeRanOnce(true);
        }
      } catch {
        // Silently ignore; user can still trigger probe manually.
      }
    }

    loadCachedProbe();
    return () => {
      active = false;
    };
  }, []);

  async function handleProbeReasoning(force = false) {
    setReasoningProbeLoading(true);
    setReasoningError(null);
    try {
      const response = await probeReasoningModels({ force });
      setReasoningResults(response.results);
      setReasoningProbeRanOnce(true);
    } catch (probeError) {
      setReasoningError(getErrorMessage(probeError));
    } finally {
      setReasoningProbeLoading(false);
    }
  }

  const reasoningStatusById = new Map(reasoningResults.map((item) => [item.id, item]));

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
          const fallbackModel = list.find((model) => model.supports_chat !== false) ?? list[0];
          setForm((prev) => ({ ...prev, selected_model: fallbackModel.id }));
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
      default_storage_provider: settings.default_storage_provider || "google_drive",
      default_storage_folders: settings.default_storage_folders || {},
    });
    setApiKeyConfigured(settings.api_key_configured);
  }

  function updateField<K extends keyof SettingsFormState>(key: K, value: SettingsFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  const selectedModelMeta = models.find((model) => model.id === form.selected_model);
  const selectedTemplate = templates.find((item) => item.id === selectedTemplateId) ?? null;
  const selectedModelIsChatUnsupported = selectedModelMeta?.supports_chat === false;
  const modelCompatibilityWarning = selectedModelIsChatUnsupported
    ? `Модель '${form.selected_model}' по metadata провайдера не поддерживает chat/completions. Выберите другую chat-модель.`
    : null;

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

  function updateTemplateField(key: string, value: string) {
    setTemplateValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleTemplatePreview() {
    if (!selectedTemplateId) {
      return;
    }
    setTemplateLoading(true);
    setTemplateError(null);
    setTemplateMessage(null);
    try {
      const preview = await previewDocumentTemplateFill(selectedTemplateId, templateValues);
      if (preview.ready) {
        setTemplateMessage("Все обязательные поля заполнены, можно скачивать DOCX.");
      } else {
        const invalid = Object.entries(preview.invalid_fields)
          .map(([key, value]) => `${key}: ${value}`)
          .join(", ");
        setTemplateMessage(
          `Missing: ${preview.missing_fields.join(", ") || "—"}. Invalid: ${invalid || "—"}.`
        );
      }
    } catch (previewError) {
      setTemplateError(getErrorMessage(previewError));
    } finally {
      setTemplateLoading(false);
    }
  }

  async function handleTemplateDownload() {
    if (!selectedTemplateId) {
      return;
    }
    setTemplateLoading(true);
    setTemplateError(null);
    setTemplateMessage(null);
    try {
      const { blob, filename } = await downloadDocumentTemplateFill(selectedTemplateId, templateValues);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
      setTemplateMessage("DOCX успешно сформирован.");
    } catch (downloadError) {
      setTemplateError(getErrorMessage(downloadError));
    } finally {
      setTemplateLoading(false);
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

      <div className="theme-switcher" role="group" aria-label="Тема оформления">
        <span className="settings-form__label">Тема оформления</span>
        <div className="theme-switcher__options">
          {THEME_OPTIONS.map((option) => {
            const isActive = themePreference === option.value;
            return (
              <button
                key={option.value}
                type="button"
                className={`theme-switcher__button${isActive ? " theme-switcher__button--active" : ""}`}
                aria-pressed={isActive}
                onClick={() => onThemePreferenceChange(option.value)}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

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
        {modelCompatibilityWarning ? <p className="status-text status-text--error">{modelCompatibilityWarning}</p> : null}

        {models.length > 0 ? (
          <select
            id="selected-model"
            className="settings-form__input"
            value={form.selected_model}
            onChange={(event) => updateField("selected_model", event.target.value)}
          >
            {models.map((model) => (
              <option key={model.id} value={model.id} disabled={model.supports_chat === false}>
                {formatModelOptionLabel(model, reasoningStatusById.get(model.id))}
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
        <p className="status-text settings-form__hint">
          🧠 — модель помечена как reasoning по эвристике на ID, реальная поддержка стриминга reasoning зависит от провайдера. ✅ — подтверждено живой проверкой ниже.
        </p>

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

        <label className="settings-form__label" htmlFor="default-storage-provider">
          Хранилище файлов по умолчанию
        </label>
        <select
          id="default-storage-provider"
          className="settings-form__input"
          value={form.default_storage_provider}
          onChange={(event) => updateField("default_storage_provider", event.target.value)}
        >
          <option value="google_drive">Google Drive</option>
          <option value="yandex_disk">Yandex.Disk</option>
          <option value="onedrive">OneDrive</option>
        </select>

        <button type="submit" className="settings-form__submit" disabled={saving || selectedModelIsChatUnsupported}>
          {saving ? "Сохранение..." : "Сохранить"}
        </button>
      </form>

      <section className="reasoning-probe" aria-label="Проверка reasoning у моделей">
        <div className="page__row">
          <h3 className="reasoning-probe__title">Streaming reasoning</h3>
          <button
            type="button"
            className="chat-action-button"
            onClick={() => handleProbeReasoning(reasoningProbeRanOnce)}
            disabled={reasoningProbeLoading}
          >
            {reasoningProbeLoading
              ? "Проверка..."
              : reasoningProbeRanOnce
                ? "Проверить заново"
                : "Проверить reasoning у моделей"}
          </button>
        </div>
        <p className="status-text">
          Backend пробует streaming-запрос к моделям, отмеченным эвристикой 🧠, и фиксирует, какие реально присылают reasoning от провайдера. Результат кешируется на 24 часа.
        </p>
        {reasoningError ? <p className="status-text status-text--error">{reasoningError}</p> : null}
        {reasoningResults.length === 0 && reasoningProbeRanOnce && !reasoningProbeLoading ? (
          <p className="status-text">Кандидатов по эвристике не нашлось или провайдер ничего не вернул.</p>
        ) : null}
        {reasoningResults.length > 0 ? (
          <ul className="reasoning-probe__list" data-testid="reasoning-probe-results">
            {reasoningResults.map((item) => (
              <li
                key={item.id}
                className={`reasoning-probe__item reasoning-probe__item--${item.streams_reasoning ? "ok" : "off"}`}
              >
                <span className="reasoning-probe__badge">{item.streams_reasoning ? "✅" : "—"}</span>
                <span className="reasoning-probe__id">{item.id}</span>
                {item.error ? <span className="reasoning-probe__error">{item.error}</span> : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>
      <section className="reasoning-probe" aria-label="Шаблоны документов">
        <div className="page__row">
          <h3 className="reasoning-probe__title">Заполнение шаблона DOCX</h3>
        </div>
        {templates.length === 0 ? <p className="status-text">Шаблоны пока не созданы.</p> : null}
        {templates.length > 0 ? (
          <>
            <label className="settings-form__label" htmlFor="document-template-id">
              Шаблон
            </label>
            <select
              id="document-template-id"
              className="settings-form__input"
              value={selectedTemplateId}
              onChange={(event) => {
                setSelectedTemplateId(event.target.value);
                setTemplateValues({});
              }}
            >
              {templates.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            {selectedTemplate?.fields.map((field) => (
              <div key={field.key}>
                <label className="settings-form__label" htmlFor={`field-${field.key}`}>
                  {field.label} ({field.key}){field.required ? " *" : ""}
                </label>
                <input
                  id={`field-${field.key}`}
                  className="settings-form__input"
                  value={templateValues[field.key] ?? ""}
                  onChange={(event) => updateTemplateField(field.key, event.target.value)}
                />
              </div>
            ))}
            <div className="settings-form__row">
              <button type="button" className="chat-action-button" onClick={handleTemplatePreview} disabled={templateLoading}>
                Проверить поля
              </button>
              <button type="button" className="chat-action-button" onClick={handleTemplateDownload} disabled={templateLoading}>
                Скачать DOCX
              </button>
            </div>
          </>
        ) : null}
        {templateError ? <p className="status-text status-text--error">{templateError}</p> : null}
        {templateMessage ? <p className="status-text">{templateMessage}</p> : null}
      </section>
      {currentUserRole === "admin" ? <AdminAccessRequestsSection /> : null}
    </section>
  );
}

function formatModelOptionLabel(model: ModelInfo, probeItem: ReasoningProbeItem | undefined): string {
  const reasoningBadge = probeItem?.streams_reasoning
    ? "✅ "
    : isLikelyReasoningModel(model.id)
      ? "🧠 "
      : "";
  const suffix = model.supports_chat === false ? " (без chat/completions)" : "";
  return `${reasoningBadge}${model.id}${suffix}`;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Произошла ошибка. Попробуйте позже.";
}

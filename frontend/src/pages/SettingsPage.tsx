import { FormEvent, useEffect, useState } from "react";

import {
  deleteMyAccount,
  deleteUserExport,
  connectImap,
  disconnectImap,
  getUserExportStatus,
  getImapMessage,
  getGitHubStatus,
  getIntegrations,
  getModels,
  getReasoningCache,
  getSettings,
  listImapFolders,
  listImapMessages,
  listGitHubIssues,
  listGitHubPulls,
  listGitHubRepos,
  markImapAsRead,
  probeReasoningModels,
  requestDeleteConfirmation,
  readGitHubFile,
  searchImapMessages,
  startUserExport,
  testImapConnection,
  updateSettings,
} from "../api/client";
import AdminAccessRequestsSection from "../components/AdminAccessRequestsSection";
import type { ThemePreference } from "../hooks/useTheme";
import type {
  GitHubIssueItem,
  GitHubPullItem,
  GitHubRepoItem,
  IntegrationConnectionResponse,
  ImapConnectRequest,
  ImapMessageDetails,
  ImapMessageSummary,
  ModelInfo,
  ReasoningProbeItem,
  SettingsResponse,
  UserExportStatusResponse,
} from "../types/api";

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
const IMAP_PRESETS = [
  { key: "yandex", label: "Yandex Mail", host: "imap.yandex.ru", port: 993, security: "ssl" as const },
  { key: "mailru", label: "Mail.ru", host: "imap.mail.ru", port: 993, security: "ssl" as const },
  { key: "outlook", label: "Outlook", host: "outlook.office365.com", port: 993, security: "ssl" as const },
  {
    key: "proton",
    label: "ProtonMail Bridge (local-only)",
    host: "127.0.0.1",
    port: 1143,
    security: "plain" as const,
  },
  { key: "custom", label: "Custom", host: "", port: 993, security: "ssl" as const },
];

export function isLikelyReasoningModel(modelId: string): boolean {
  const lower = modelId.toLowerCase();
  return REASONING_HEURISTIC_TOKENS.some((token) => lower.includes(token));
}

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
  const [integrationStates, setIntegrationStates] = useState<IntegrationConnectionResponse[]>([]);
  const [githubStatus, setGithubStatus] = useState<IntegrationConnectionResponse | null>(null);
  const [githubOwner, setGithubOwner] = useState("ajotce");
  const [githubRepo, setGithubRepo] = useState("asya-assistant");
  const [githubPath, setGithubPath] = useState("README.md");
  const [githubRef, setGithubRef] = useState("");
  const [githubRepos, setGithubRepos] = useState<GitHubRepoItem[]>([]);
  const [githubIssues, setGithubIssues] = useState<GitHubIssueItem[]>([]);
  const [githubPulls, setGithubPulls] = useState<GitHubPullItem[]>([]);
  const [githubFilePreview, setGithubFilePreview] = useState<string>("");
  const [githubLoading, setGithubLoading] = useState(false);
  const [githubError, setGithubError] = useState<string | null>(null);
  const [imapPreset, setImapPreset] = useState("yandex");
  const [imapForm, setImapForm] = useState<ImapConnectRequest>({
    email: "",
    username: "",
    password: "",
    host: "imap.yandex.ru",
    port: 993,
    security: "ssl",
  });
  const [imapLoading, setImapLoading] = useState(false);
  const [imapError, setImapError] = useState<string | null>(null);
  const [imapSuccess, setImapSuccess] = useState<string | null>(null);
  const [imapFolders, setImapFolders] = useState<string[]>([]);
  const [imapMessages, setImapMessages] = useState<ImapMessageSummary[]>([]);
  const [imapQuery, setImapQuery] = useState("");
  const [imapFolder, setImapFolder] = useState("INBOX");
  const [imapSelectedMessage, setImapSelectedMessage] = useState<ImapMessageDetails | null>(null);
  const [exportStatus, setExportStatus] = useState<UserExportStatusResponse | null>(null);
  const [exportLoading, setExportLoading] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteToken, setDeleteToken] = useState<string | null>(null);
  const [deleteMessage, setDeleteMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadSettings() {
      setLoading(true);
      setError(null);
      try {
        const data = await getSettings();
        const integrations = await getIntegrations();
        const ghStatus = await getGitHubStatus().catch(() => null);
        if (!active) {
          return;
        }
        applySettings(data);
        setIntegrationStates(integrations);
        setGithubStatus(ghStatus);
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
    });
    setApiKeyConfigured(settings.api_key_configured);
  }

  function updateField<K extends keyof SettingsFormState>(key: K, value: SettingsFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  const selectedModelMeta = models.find((model) => model.id === form.selected_model);
  const bitrixConnection = integrationStates.find((item) => item.provider === "bitrix24");
  const githubConnection = integrationStates.find((item) => item.provider === "github") ?? githubStatus;
  const imapConnection = integrationStates.find((item) => item.provider === "imap");
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

  async function handleLoadGitHubRepos() {
    setGithubLoading(true);
    setGithubError(null);
    try {
      setGithubRepos(await listGitHubRepos());
    } catch (loadError) {
      setGithubError(getErrorMessage(loadError));
    } finally {
      setGithubLoading(false);
    }
  }

  async function handleLoadGitHubIssues() {
    setGithubLoading(true);
    setGithubError(null);
    try {
      setGithubIssues(await listGitHubIssues(githubOwner, githubRepo));
    } catch (loadError) {
      setGithubError(getErrorMessage(loadError));
    } finally {
      setGithubLoading(false);
    }
  }

  async function handleLoadGitHubPulls() {
    setGithubLoading(true);
    setGithubError(null);
    try {
      setGithubPulls(await listGitHubPulls(githubOwner, githubRepo));
    } catch (loadError) {
      setGithubError(getErrorMessage(loadError));
    } finally {
      setGithubLoading(false);
    }
  }

  async function handleReadGitHubFile() {
    setGithubLoading(true);
    setGithubError(null);
    try {
      const payload = await readGitHubFile(githubOwner, githubRepo, githubPath, githubRef || undefined);
      const normalized = payload.content.replace(/\n/g, "");
      const decoded = payload.encoding === "base64" ? atob(normalized) : payload.content;
      setGithubFilePreview(decoded.slice(0, 2000));
    } catch (loadError) {
      setGithubError(getErrorMessage(loadError));
    } finally {
      setGithubLoading(false);
    }
  }

  function applyImapPreset(presetKey: string) {
    setImapPreset(presetKey);
    const preset = IMAP_PRESETS.find((item) => item.key === presetKey);
    if (!preset) {
      return;
    }
    setImapForm((prev) => ({ ...prev, host: preset.host, port: preset.port, security: preset.security }));
  }

  async function refreshImapData() {
    const folders = await listImapFolders();
    setImapFolders(folders.folders);
    const primaryFolder = folders.folders[0] ?? "INBOX";
    setImapFolder(primaryFolder);
    setImapMessages(await listImapMessages(primaryFolder, 20));
  }

  async function handleTestImap() {
    setImapLoading(true);
    setImapError(null);
    setImapSuccess(null);
    try {
      const result = await testImapConnection(imapForm);
      setImapSuccess(`Проверка успешна. Папок: ${result.folders.length}`);
    } catch (loadError) {
      setImapError(getErrorMessage(loadError));
    } finally {
      setImapLoading(false);
    }
  }

  async function handleConnectImap() {
    setImapLoading(true);
    setImapError(null);
    setImapSuccess(null);
    try {
      await connectImap(imapForm);
      setIntegrationStates(await getIntegrations());
      await refreshImapData();
      setImapSuccess("IMAP подключен.");
    } catch (loadError) {
      setImapError(getErrorMessage(loadError));
    } finally {
      setImapLoading(false);
    }
  }

  async function handleDisconnectImap() {
    setImapLoading(true);
    setImapError(null);
    setImapSuccess(null);
    try {
      await disconnectImap();
      setIntegrationStates(await getIntegrations());
      setImapFolders([]);
      setImapMessages([]);
      setImapSelectedMessage(null);
      setImapSuccess("IMAP отключен.");
    } catch (loadError) {
      setImapError(getErrorMessage(loadError));
    } finally {
      setImapLoading(false);
    }
  }

  async function handleSearchImap() {
    setImapLoading(true);
    setImapError(null);
    try {
      if (!imapQuery.trim()) {
        setImapMessages(await listImapMessages(imapFolder, 20));
      } else {
        setImapMessages(await searchImapMessages(imapQuery, imapFolder, 20));
      }
    } catch (loadError) {
      setImapError(getErrorMessage(loadError));
    } finally {
      setImapLoading(false);
    }
  }

  async function handleOpenImapMessage(uid: string) {
    setImapLoading(true);
    setImapError(null);
    try {
      setImapSelectedMessage(await getImapMessage(uid, imapFolder));
    } catch (loadError) {
      setImapError(getErrorMessage(loadError));
    } finally {
      setImapLoading(false);
    }
  }

  async function handleMarkAsRead(uid: string) {
    setImapLoading(true);
    setImapError(null);
    try {
      await markImapAsRead(uid, imapFolder);
      setImapMessages(await listImapMessages(imapFolder, 20));
    } catch (loadError) {
      setImapError(getErrorMessage(loadError));
    } finally {
      setImapLoading(false);
    }
  }

  async function handleStartExport() {
    setExportLoading(true);
    setExportError(null);
    try {
      const start = await startUserExport();
      setExportStatus(await getUserExportStatus(start.export_id));
    } catch (loadError) {
      setExportError(getErrorMessage(loadError));
    } finally {
      setExportLoading(false);
    }
  }

  async function handleRefreshExport() {
    if (!exportStatus?.export_id) return;
    setExportLoading(true);
    setExportError(null);
    try {
      setExportStatus(await getUserExportStatus(exportStatus.export_id));
    } catch (loadError) {
      setExportError(getErrorMessage(loadError));
    } finally {
      setExportLoading(false);
    }
  }

  async function handleDeleteExport() {
    if (!exportStatus?.export_id) return;
    setExportLoading(true);
    setExportError(null);
    try {
      await deleteUserExport(exportStatus.export_id);
      setExportStatus(null);
    } catch (loadError) {
      setExportError(getErrorMessage(loadError));
    } finally {
      setExportLoading(false);
    }
  }

  async function handleRequestDeleteConfirmation() {
    setExportLoading(true);
    setExportError(null);
    setDeleteMessage(null);
    try {
      const result = await requestDeleteConfirmation();
      setDeleteToken(result.confirmation_token);
      setDeleteMessage("Подтверждение получено. Введите пароль и удалите учётку.");
    } catch (loadError) {
      setExportError(getErrorMessage(loadError));
    } finally {
      setExportLoading(false);
    }
  }

  async function handleDeleteAccount() {
    if (!deleteToken || !deletePassword.trim()) return;
    setExportLoading(true);
    setExportError(null);
    setDeleteMessage(null);
    try {
      const result = await deleteMyAccount({ confirmation_token: deleteToken, password: deletePassword });
      setDeleteMessage(
        `Учётка удалена. Export: ${result.export_id}. Ссылка: ${result.export_download_url ?? "недоступна"}`,
      );
    } catch (loadError) {
      setExportError(getErrorMessage(loadError));
    } finally {
      setExportLoading(false);
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
        <p className="status-text" data-testid="bitrix24-status">
          Bitrix24 (read-only): {bitrixConnection?.status ?? "not_connected"}
        </p>
        <p className="status-text" data-testid="github-status">
          GitHub (read-only): {githubConnection?.status ?? "not_connected"}
        </p>
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

        <button type="submit" className="settings-form__submit" disabled={saving || selectedModelIsChatUnsupported}>
          {saving ? "Сохранение..." : "Сохранить"}
        </button>
      </form>

      <section className="reasoning-probe" aria-label="IMAP mail">
        <div className="page__row">
          <h3 className="reasoning-probe__title">IMAP mail</h3>
          <p className="status-text" data-testid="imap-status">
            IMAP: {imapConnection?.status ?? "not_connected"}
          </p>
        </div>
        <div className="settings-form__row">
          <select className="settings-form__input" value={imapPreset} onChange={(event) => applyImapPreset(event.target.value)}>
            {IMAP_PRESETS.map((preset) => (
              <option key={preset.key} value={preset.key}>
                {preset.label}
              </option>
            ))}
          </select>
          <input className="settings-form__input" value={imapForm.host} onChange={(event) => setImapForm({ ...imapForm, host: event.target.value })} placeholder="host" />
          <input className="settings-form__input" value={imapForm.port} type="number" onChange={(event) => setImapForm({ ...imapForm, port: Number(event.target.value) })} placeholder="port" />
          <select className="settings-form__input" value={imapForm.security} onChange={(event) => setImapForm({ ...imapForm, security: event.target.value as ImapConnectRequest["security"] })}>
            <option value="ssl">ssl</option>
            <option value="starttls">starttls</option>
            <option value="plain">plain</option>
          </select>
        </div>
        <div className="settings-form__row">
          <input className="settings-form__input" value={imapForm.email} onChange={(event) => setImapForm({ ...imapForm, email: event.target.value })} placeholder="email" />
          <input className="settings-form__input" value={imapForm.username} onChange={(event) => setImapForm({ ...imapForm, username: event.target.value })} placeholder="username" />
          <input className="settings-form__input" value={imapForm.password} onChange={(event) => setImapForm({ ...imapForm, password: event.target.value })} placeholder="password/app password" type="password" />
        </div>
        <div className="settings-form__row">
          <button type="button" className="chat-action-button" onClick={handleTestImap} disabled={imapLoading}>Test</button>
          <button type="button" className="chat-action-button" onClick={handleConnectImap} disabled={imapLoading}>Connect</button>
          <button type="button" className="chat-action-button" onClick={handleDisconnectImap} disabled={imapLoading}>Disconnect</button>
          <button type="button" className="chat-action-button" onClick={refreshImapData} disabled={imapLoading}>Refresh</button>
        </div>
        <div className="settings-form__row">
          <input className="settings-form__input" value={imapFolder} onChange={(event) => setImapFolder(event.target.value)} placeholder="folder" />
          <input className="settings-form__input" value={imapQuery} onChange={(event) => setImapQuery(event.target.value)} placeholder="search" />
          <button type="button" className="chat-action-button" onClick={handleSearchImap} disabled={imapLoading}>Search</button>
        </div>
        {imapError ? <p className="status-text status-text--error">{imapError}</p> : null}
        {imapSuccess ? <p className="status-text status-text--ok">{imapSuccess}</p> : null}
        {imapFolders.length > 0 ? <p className="status-text">Folders: {imapFolders.join(", ")}</p> : null}
        {imapMessages.length > 0 ? (
          <ul>
            {imapMessages.slice(0, 10).map((item) => (
              <li key={item.uid}>
                <button type="button" className="chat-action-button" onClick={() => handleOpenImapMessage(item.uid)}>
                  {item.is_unread ? "● " : ""}
                  {item.subject || "(no subject)"}
                </button>
                <button type="button" className="chat-action-button" onClick={() => handleMarkAsRead(item.uid)}>Mark read</button>
              </li>
            ))}
          </ul>
        ) : null}
        {imapSelectedMessage ? <pre className="status-text">{imapSelectedMessage.text_body.slice(0, 2000)}</pre> : null}
      </section>

      <section className="reasoning-probe" aria-label="GitHub read-only">
        <div className="page__row">
          <h3 className="reasoning-probe__title">GitHub read-only</h3>
          <button type="button" className="chat-action-button" onClick={handleLoadGitHubRepos} disabled={githubLoading}>
            {githubLoading ? "Загрузка..." : "Загрузить repos"}
          </button>
        </div>
        <div className="settings-form__row">
          <input
            className="settings-form__input"
            value={githubOwner}
            onChange={(event) => setGithubOwner(event.target.value)}
            placeholder="owner"
          />
          <input
            className="settings-form__input"
            value={githubRepo}
            onChange={(event) => setGithubRepo(event.target.value)}
            placeholder="repo"
          />
        </div>
        <div className="settings-form__row">
          <button type="button" className="chat-action-button" onClick={handleLoadGitHubIssues} disabled={githubLoading}>
            Открытые issues
          </button>
          <button type="button" className="chat-action-button" onClick={handleLoadGitHubPulls} disabled={githubLoading}>
            Открытые PR
          </button>
        </div>
        <div className="settings-form__row">
          <input
            className="settings-form__input"
            value={githubPath}
            onChange={(event) => setGithubPath(event.target.value)}
            placeholder="path/to/file"
          />
          <input
            className="settings-form__input"
            value={githubRef}
            onChange={(event) => setGithubRef(event.target.value)}
            placeholder="ref (optional)"
          />
          <button type="button" className="chat-action-button" onClick={handleReadGitHubFile} disabled={githubLoading}>
            Прочитать файл
          </button>
        </div>
        {githubError ? <p className="status-text status-text--error">{githubError}</p> : null}
        {githubRepos.length > 0 ? (
          <p className="status-text">Repos: {githubRepos.slice(0, 5).map((item) => item.full_name).join(", ")}</p>
        ) : null}
        {githubIssues.length > 0 ? (
          <p className="status-text">Issues: {githubIssues.slice(0, 5).map((item) => `#${item.number} ${item.title}`).join("; ")}</p>
        ) : null}
        {githubPulls.length > 0 ? (
          <p className="status-text">PRs: {githubPulls.slice(0, 5).map((item) => `#${item.number} ${item.title}`).join("; ")}</p>
        ) : null}
        {githubFilePreview ? <pre className="status-text">{githubFilePreview}</pre> : null}
      </section>

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
      <section className="reasoning-probe" aria-label="Экспорт и удаление">
        <h3 className="reasoning-probe__title">Экспорт данных</h3>
        <div className="settings-form__row">
          <button type="button" className="chat-action-button" onClick={handleStartExport} disabled={exportLoading}>
            Скачать мои данные
          </button>
          <button
            type="button"
            className="chat-action-button"
            onClick={handleRefreshExport}
            disabled={exportLoading || !exportStatus}
          >
            Обновить статус
          </button>
          <button
            type="button"
            className="chat-action-button"
            onClick={handleDeleteExport}
            disabled={exportLoading || !exportStatus}
          >
            Удалить архив
          </button>
        </div>
        {exportStatus ? (
          <p className="status-text">
            Export {exportStatus.export_id}: {exportStatus.status}
            {exportStatus.download_url ? `, ${exportStatus.download_url}` : ""}
          </p>
        ) : null}

        <h3 className="reasoning-probe__title">Удаление учётки</h3>
        <div className="settings-form__row">
          <button
            type="button"
            className="chat-action-button"
            onClick={handleRequestDeleteConfirmation}
            disabled={exportLoading}
          >
            Запросить подтверждение
          </button>
          <input
            className="settings-form__input"
            type="password"
            value={deletePassword}
            onChange={(event) => setDeletePassword(event.target.value)}
            placeholder="Пароль"
          />
          <button
            type="button"
            className="chat-action-button"
            onClick={handleDeleteAccount}
            disabled={exportLoading || !deleteToken}
          >
            Удалить учётку
          </button>
        </div>
        {deleteMessage ? <p className="status-text status-text--ok">{deleteMessage}</p> : null}
        {exportError ? <p className="status-text status-text--error">{exportError}</p> : null}
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

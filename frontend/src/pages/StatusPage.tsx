import { useCallback, useEffect, useMemo, useState } from "react";

import { getHealth, getIntegrations, getUsage } from "../api/client";
import type { HealthResponse, IntegrationConnectionResponse, UsageOverviewResponse } from "../types/api";

type Severity = "ok" | "warning" | "error" | "unknown";

interface StatusCardData {
  id: string;
  label: string;
  severity: Severity;
  summary: string;
  details: string[];
}

export default function StatusPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [usage, setUsage] = useState<UsageOverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [usageError, setUsageError] = useState<string | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationConnectionResponse[] | null>(null);
  const [integrationsError, setIntegrationsError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>({});

  const refreshStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    setUsageError(null);
    setIntegrationsError(null);
    try {
      const [healthData, usageData, integrationsData] = await Promise.all([
        getHealth(),
        getUsage().catch((usageLoadError) => {
          setUsageError(getErrorMessage(usageLoadError));
          return null;
        }),
        getIntegrations().catch((integrationsLoadError) => {
          setIntegrationsError(getErrorMessage(integrationsLoadError));
          return null;
        }),
      ]);
      setHealth(healthData);
      setUsage(usageData);
      setIntegrations(integrationsData);
      setLastUpdatedAt(new Date());
    } catch (statusError) {
      setHealth(null);
      setUsage(null);
      setIntegrations(null);
      setError(getErrorMessage(statusError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  useEffect(() => {
    if (!autoRefresh) {
      return;
    }
    const timerId = window.setInterval(() => {
      void refreshStatus();
    }, 15000);
    return () => window.clearInterval(timerId);
  }, [autoRefresh, refreshStatus]);

  const cards = useMemo(
    () => buildStatusCards({ health, usage, usageError, integrations, integrationsError, healthError: error }),
    [health, usage, usageError, integrations, integrationsError, error]
  );

  function toggleCard(cardId: string) {
    setExpandedCards((prev) => ({ ...prev, [cardId]: !prev[cardId] }));
  }

  return (
    <section className="page" aria-label="Состояние Asya">
      <div className="page__row">
        <h2 className="page__title">Состояние Asya</h2>
        <button type="button" className="chat-action-button" onClick={() => void refreshStatus()} disabled={loading}>
          {loading ? "Обновление..." : "Обновить"}
        </button>
      </div>

      <div className="status-controls">
        <p className="status-text" data-testid="status-last-updated">
          Последнее обновление: {formatLastUpdated(lastUpdatedAt)}
        </p>
        <label className="status-toggle" htmlFor="status-autorefresh-toggle">
          <input
            id="status-autorefresh-toggle"
            type="checkbox"
            checked={autoRefresh}
            onChange={(event) => setAutoRefresh(event.target.checked)}
          />
          Автообновление (15 сек)
        </label>
      </div>

      {loading ? <p className="status-text">Проверка состояния...</p> : null}
      {error ? <p className="status-text status-text--error">{error}</p> : null}

      <div className="status-grid">
        {cards.map((card) => (
          <StatusCard
            key={card.id}
            card={card}
            expanded={Boolean(expandedCards[card.id])}
            onToggle={() => toggleCard(card.id)}
          />
        ))}
      </div>
    </section>
  );
}

function StatusCard({
  card,
  expanded,
  onToggle,
}: {
  card: StatusCardData;
  expanded: boolean;
  onToggle: () => void;
}) {
  const detailsId = `status-card-details-${card.id}`;

  return (
    <article className={`status-card status-card--${card.severity}`}>
      <button
        type="button"
        className="status-card__button"
        onClick={onToggle}
        aria-expanded={expanded}
        aria-controls={detailsId}
        aria-label={`${card.label}: ${card.summary}. ${expanded ? "Скрыть детали" : "Показать детали"}`}
      >
        <div className="status-card__header">
          <h3 className="status-card__label">{card.label}</h3>
          <span className={`status-badge status-badge--${card.severity}`}>{card.severity}</span>
        </div>
        <p className="status-card__summary">{card.summary}</p>
      </button>
      <div id={detailsId} className="status-card__details" hidden={!expanded}>
        <ul className="status-card__details-list">
          {card.details.map((detail) => (
            <li key={detail}>{detail}</li>
          ))}
        </ul>
      </div>
    </article>
  );
}

function buildStatusCards({
  health,
  usage,
  usageError,
  integrations,
  integrationsError,
  healthError,
}: {
  health: HealthResponse | null;
  usage: UsageOverviewResponse | null;
  usageError: string | null;
  integrations: IntegrationConnectionResponse[] | null;
  integrationsError: string | null;
  healthError: string | null;
}): StatusCardData[] {
  const cards: StatusCardData[] = [];

  if (!health) {
    cards.push({
      id: "backend",
      label: "Backend",
      severity: healthError ? "error" : "unknown",
      summary: healthError ? "Недоступен" : "Нет данных",
      details: [healthError ?? "Нет ответа от /api/health."],
    });
    cards.push({
      id: "usage",
      label: "Usage",
      severity: usageError ? "error" : "unknown",
      summary: usageError ? "Ошибка получения" : "Нет данных",
      details: [usageError ?? "Usage недоступен, пока нет health-данных."],
    });
    cards.push({
      id: "providers",
      label: "File providers",
      severity: integrationsError ? "error" : "unknown",
      summary: integrationsError ? "Ошибка получения" : "Нет данных",
      details: [integrationsError ?? "Интеграции пока не загружены."],
    });
    return cards;
  }

  const backendSeverity: Severity = health.status === "ok" ? "ok" : "error";
  cards.push({
    id: "backend",
    label: "Backend",
    severity: backendSeverity,
    summary: backendSeverity === "ok" ? "Работает" : "Есть ошибка",
    details: [
      `Статус: ${health.status}`,
      `Версия: ${health.version}`,
      `Окружение: ${health.environment}`,
      `Uptime: ${formatUptime(health.uptime_seconds)}`,
      health.last_error?.trim() ? `Последняя ошибка: ${health.last_error}` : "Последняя ошибка: нет",
    ],
  });

  cards.push({
    id: "vsellm",
    label: "VseLLM доступность",
    severity: getVseLLMSeverity(health),
    summary: formatVseLLMSummary(health),
    details: [
      `Base URL: ${health.vsellm.base_url}`,
      `Reachable: ${
        health.vsellm.reachable === true ? "true" : health.vsellm.reachable === false ? "false" : "unknown"
      }`,
      health.last_error?.trim() ? `Причина: ${health.last_error}` : "Причина: нет",
    ],
  });

  cards.push({
    id: "api-key",
    label: "VseLLM API-ключ",
    severity: health.vsellm.api_key_configured ? "ok" : "warning",
    summary: health.vsellm.api_key_configured ? "Настроен" : "Не настроен",
    details: [
      `Состояние: ${health.vsellm.api_key_configured ? "настроен" : "не настроен"}`,
      "Значение ключа в UI не отображается.",
    ],
  });

  const selectedModel = health.model.selected.trim();
  cards.push({
    id: "model",
    label: "Выбранная модель",
    severity: selectedModel ? "ok" : "warning",
    summary: selectedModel || "Не выбрана",
    details: [selectedModel ? `Model ID: ${selectedModel}` : "Model ID отсутствует в настройках backend."],
  });

  cards.push({
    id: "files",
    label: "Файлы",
    severity: getFilesSeverity(health),
    summary: health.files.enabled ? `Модуль: ${health.files.status}` : "Модуль отключен",
    details: [`enabled: ${String(health.files.enabled)}`, `status: ${health.files.status || "unknown"}`],
  });

  cards.push({
    id: "embeddings",
    label: "Embeddings",
    severity: getEmbeddingsSeverity(health),
    summary: formatEmbeddingsSummary(health),
    details: [
      `enabled: ${String(health.embeddings.enabled)}`,
      `model: ${health.embeddings.model || "не указана"}`,
      `status: ${health.embeddings.status || "unknown"}`,
      health.embeddings.last_error?.trim() ? `error: ${health.embeddings.last_error}` : "error: нет",
    ],
  });

  cards.push({
    id: "runtime",
    label: "Session / Runtime",
    severity: health.session.enabled ? "ok" : "warning",
    summary: health.session.enabled
      ? `Активных сессий: ${health.session.active_sessions}`
      : "Сессионный runtime отключен",
    details: [
      `enabled: ${String(health.session.enabled)}`,
      `active_sessions: ${health.session.active_sessions}`,
    ],
  });

  cards.push({
    id: "usage",
    label: "Usage",
    severity: getUsageSeverity(usage, usageError),
    summary: formatUsageSummary(usage, usageError),
    details: usage ? buildUsageDetails(usage) : [usageError ?? "Данные usage не получены."],
  });

  cards.push({
    id: "storage",
    label: "Временное хранилище",
    severity: getStorageSeverity(health),
    summary: health.storage.writable ? "Готово к записи" : "Нет доступа к записи",
    details: [
      `session_store: ${health.storage.session_store}`,
      `file_store: ${health.storage.file_store}`,
      `writable: ${String(health.storage.writable)}`,
      `tmp_dir: ${health.storage.tmp_dir}`,
    ],
  });

  cards.push(...buildFileProviderCards(integrations, integrationsError));

  return cards;
}

function buildFileProviderCards(
  integrations: IntegrationConnectionResponse[] | null,
  integrationsError: string | null
): StatusCardData[] {
  const targets = [
    { code: "yandex_disk", label: "Yandex.Disk" },
    { code: "onedrive", label: "OneDrive" },
    { code: "icloud_drive", label: "iCloud Drive" },
  ];

  return targets.map((target) => {
    const item = integrations?.find((integration) => integration.provider === target.code);
    const status = item?.status ?? "not_connected";
    const severity: Severity =
      status === "connected" ? "ok" : status === "error" ? "error" : status === "expired" ? "warning" : "unknown";
    return {
      id: `provider-${target.code}`,
      label: `${target.label} integration`,
      severity: integrationsError ? "error" : severity,
      summary: integrationsError ? "Ошибка получения" : formatProviderSummary(status),
      details: integrationsError
        ? [integrationsError]
        : [
            `provider: ${target.code}`,
            `status: ${status}`,
            `scopes: ${(item?.scopes ?? []).join(", ") || "—"}`,
            `last_sync_at: ${item?.last_sync_at ?? "—"}`,
          ],
    };
  });
}

function formatProviderSummary(status: string): string {
  if (status === "connected") return "Подключен";
  if (status === "not_connected") return "Не подключен";
  if (status === "expired") return "Нужна перепривязка";
  if (status === "error") return "Ошибка подключения";
  if (status === "revoked") return "Отключен";
  return "Неизвестно";
}

function getVseLLMSeverity(health: HealthResponse): Severity {
  if (health.vsellm.reachable === true) {
    return "ok";
  }
  if (health.vsellm.reachable === false) {
    return "error";
  }
  if (!health.vsellm.api_key_configured) {
    return "warning";
  }
  return "unknown";
}

function formatVseLLMSummary(health: HealthResponse): string {
  if (health.vsellm.reachable === true) {
    return "Доступен";
  }
  if (health.vsellm.reachable === false) {
    return "Недоступен";
  }
  if (!health.vsellm.api_key_configured) {
    return "Ключ не настроен";
  }
  return "Проверка не выполнялась";
}

function getFilesSeverity(health: HealthResponse): Severity {
  if (!health.files.enabled) {
    return "warning";
  }
  const status = health.files.status.trim().toLowerCase();
  if (status.includes("ошиб")) {
    return "error";
  }
  if (status.includes("готов")) {
    return "ok";
  }
  if (!status) {
    return "unknown";
  }
  return "warning";
}

function getEmbeddingsSeverity(health: HealthResponse): Severity {
  if (!health.embeddings.enabled) {
    return "warning";
  }
  const status = health.embeddings.status.trim().toLowerCase();
  if (status.includes("ошиб")) {
    return "error";
  }
  if (status.includes("не настроен")) {
    return "warning";
  }
  if (status.includes("готов")) {
    return "ok";
  }
  return "unknown";
}

function formatEmbeddingsSummary(health: HealthResponse): string {
  if (!health.embeddings.enabled) {
    return "Отключены";
  }
  if (health.embeddings.status.trim().toLowerCase().includes("ошиб")) {
    return "Ошибка embeddings";
  }
  return health.embeddings.status || "Статус неизвестен";
}

function getStorageSeverity(health: HealthResponse): Severity {
  if (!health.storage.writable) {
    return "error";
  }
  const sessionStore = health.storage.session_store.trim().toLowerCase();
  const fileStore = health.storage.file_store.trim().toLowerCase();
  if (sessionStore.includes("ошиб") || fileStore.includes("ошиб")) {
    return "error";
  }
  if (sessionStore.includes("готов") && fileStore.includes("готов")) {
    return "ok";
  }
  return "warning";
}

function getUsageSeverity(usage: UsageOverviewResponse | null, usageError: string | null): Severity {
  if (usageError) {
    return "error";
  }
  if (!usage) {
    return "unknown";
  }
  const hasData = usage.chat.status === "available" || usage.embeddings.status === "available";
  if (hasData) {
    return "ok";
  }
  if (usage.chat.status === "unavailable" && usage.embeddings.status === "unavailable") {
    return "warning";
  }
  return "unknown";
}

function formatUsageSummary(usage: UsageOverviewResponse | null, usageError: string | null): string {
  if (usageError) {
    return "Ошибка получения usage";
  }
  if (!usage) {
    return "Нет данных";
  }
  if (usage.chat.status === "available" || usage.embeddings.status === "available") {
    return "Данные usage доступны";
  }
  if (usage.chat.status === "unavailable" && usage.embeddings.status === "unavailable") {
    return "Данные usage пока не собраны";
  }
  return "Частичные данные";
}

function buildUsageDetails(usage: UsageOverviewResponse): string[] {
  return [
    `chat.status: ${usage.chat.status}`,
    `chat.total_tokens: ${usage.chat.total_tokens ?? "нет данных"}`,
    `embeddings.status: ${usage.embeddings.status}`,
    `embeddings.total_tokens: ${usage.embeddings.total_tokens ?? "нет данных"}`,
    `cost.status: ${usage.cost.status}`,
    `active_sessions: ${usage.runtime.active_sessions}`,
    `selected_model: ${usage.runtime.selected_model || "не выбрана"}`,
    `embedding_model: ${usage.runtime.embedding_model || "не указана"}`,
  ];
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Не удалось получить состояние backend.";
}

function formatLastUpdated(lastUpdatedAt: Date | null): string {
  if (!lastUpdatedAt) {
    return "ещё не обновлялось";
  }
  return lastUpdatedAt.toLocaleTimeString("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatUptime(seconds?: number): string {
  if (typeof seconds !== "number" || Number.isNaN(seconds) || seconds < 0) {
    return "неизвестно";
  }
  if (seconds < 60) {
    return `${Math.floor(seconds)} сек`;
  }
  const totalMinutes = Math.floor(seconds / 60);
  const mins = totalMinutes % 60;
  const hours = Math.floor(totalMinutes / 60);
  if (hours === 0) {
    return `${mins} мин`;
  }
  return `${hours} ч ${mins} мин`;
}

export const __testUtils = {
  buildStatusCards,
  getUsageSeverity,
  formatUsageSummary,
  formatLastUpdated,
  formatUptime,
};

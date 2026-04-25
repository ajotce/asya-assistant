import { useEffect, useState } from "react";

import { getHealth } from "../api/client";
import type { HealthResponse } from "../types/api";

export default function StatusPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    refreshStatus();
  }, []);

  async function refreshStatus() {
    setLoading(true);
    setError(null);
    try {
      const data = await getHealth();
      setHealth(data);
    } catch (statusError) {
      setHealth(null);
      setError(getErrorMessage(statusError));
    } finally {
      setLoading(false);
    }
  }

  const backendStatus = health ? (health.status === "ok" ? "online" : "offline") : "offline";
  const vsellmReachable = health?.vsellm.reachable;
  const vsellmReachableText =
    vsellmReachable === true ? "доступен" : vsellmReachable === false ? "недоступен" : "не проверялся";
  const apiKeyStatus = health?.vsellm.api_key_configured ? "настроен" : "не настроен";
  const modelSelected = health?.model.selected ?? "не выбрана";
  const filesStatus = health ? (health.files.enabled ? health.files.status : "отключён") : "неизвестно";
  const sessionStatus = health
    ? health.session.enabled
      ? `активных сессий: ${health.session.active_sessions}`
      : "отключены"
    : "неизвестно";
  const lastError = health?.last_error ?? null;

  return (
    <section className="page" aria-label="Состояние Asya">
      <div className="page__row">
        <h2 className="page__title">Состояние Asya</h2>
        <button type="button" className="chat-action-button" onClick={refreshStatus} disabled={loading}>
          {loading ? "Обновление..." : "Обновить"}
        </button>
      </div>

      {loading ? <p className="status-text">Проверка состояния...</p> : null}
      {error ? <p className="status-text status-text--error">{error}</p> : null}

      <dl className="status-grid">
        <StatusItem label="Backend" value={backendStatus} />
        <StatusItem label="Версия приложения" value={health?.version ?? "неизвестно"} />
        <StatusItem label="VseLLM API-ключ" value={apiKeyStatus} />
        <StatusItem label="Доступность VseLLM API" value={vsellmReachableText} />
        <StatusItem label="Выбранная модель" value={modelSelected} />
        <StatusItem label="Файловый модуль" value={filesStatus} />
        <StatusItem label="Временная сессия" value={sessionStatus} />
        <StatusItem label="Последняя ошибка" value={lastError ?? "нет"} />
      </dl>
    </section>
  );
}

function StatusItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="status-grid__item">
      <dt className="status-grid__label">{label}</dt>
      <dd className="status-grid__value">{value}</dd>
    </div>
  );
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Не удалось получить состояние backend.";
}

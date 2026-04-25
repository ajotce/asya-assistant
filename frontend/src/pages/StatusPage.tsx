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

  const backendStatus = health && health.status === "ok" ? "online" : "offline";
  const apiKeyStatus = health?.vsellm.api_key_configured ? "настроен" : "не настроен";
  const modelSelected = health?.model.selected.trim() ? health.model.selected : "не выбрана";
  const uptimeText = formatUptime(health?.uptime_seconds);
  const embeddingsStatus = formatEmbeddingsStatus(health);
  const storageStatus = formatStorageStatus(health);
  const storageTmpDir = health?.storage?.tmp_dir ?? "неизвестно";

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
        <StatusItem label="Бэкенд" value={backendStatus} />
        <StatusItem label="Время работы backend" value={uptimeText} />
        <StatusItem label="Выбранная модель" value={modelSelected} />
        <StatusItem label="VseLLM API-ключ" value={apiKeyStatus} />
        <StatusItem label="Embeddings" value={embeddingsStatus} />
        <StatusItem label="Временное хранилище" value={storageStatus} />
        <StatusItem label="TMP путь" value={storageTmpDir} />
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

function formatEmbeddingsStatus(health: HealthResponse | null): string {
  if (!health) {
    return "неизвестно";
  }
  if (!health.embeddings.enabled) {
    return "отключены";
  }

  const status = health.embeddings.status.trim() || "неизвестно";
  const model = health.embeddings.model.trim() || "модель не указана";
  if (health.embeddings.last_error?.trim()) {
    return `${status} (${model}) — ${health.embeddings.last_error}`;
  }
  return `${status} (${model})`;
}

function formatStorageStatus(health: HealthResponse | null): string {
  if (!health) {
    return "неизвестно";
  }

  const writableText = health.storage.writable ? "доступно для записи" : "нет записи";
  return `sessions: ${health.storage.session_store}, files: ${health.storage.file_store}, ${writableText}`;
}

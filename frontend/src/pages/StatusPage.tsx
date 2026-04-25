import { useEffect, useState } from "react";

import { getHealth } from "../api/client";
import type { HealthResponse } from "../types/api";

export default function StatusPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function loadStatus() {
      setLoading(true);
      setError(null);
      try {
        const data = await getHealth();
        if (!active) {
          return;
        }
        setHealth(data);
      } catch (statusError) {
        if (!active) {
          return;
        }
        setError(getErrorMessage(statusError));
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadStatus();
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="page" aria-label="Состояние Asya">
      <h2 className="page__title">Состояние Asya</h2>

      {loading ? <p className="status-text">Проверка состояния...</p> : null}
      {error ? <p className="status-text status-text--error">{error}</p> : null}

      {health ? (
        <dl className="status-grid">
          <StatusItem label="Backend" value={health.status === "ok" ? "online" : "offline"} />
          <StatusItem label="Версия" value={health.version} />
          <StatusItem label="Окружение" value={health.environment} />
          <StatusItem label="VseLLM base URL" value={health.vsellm.base_url} />
          <StatusItem label="VseLLM API-ключ" value={health.vsellm.api_key_configured ? "настроен" : "не настроен"} />
        </dl>
      ) : null}
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

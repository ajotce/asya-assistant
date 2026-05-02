import { useCallback, useEffect, useMemo, useState } from "react";

import {
  actionedObservation,
  dismissObservation,
  listObservations,
  postponeObservation,
  runObserver,
} from "../api/client";
import type { ObservationItem } from "../types/api";

interface ObserverPageProps {
  onDiscuss: (context: string) => void;
}

export default function ObserverPage({ onDiscuss }: ObserverPageProps) {
  const [items, setItems] = useState<ObservationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [detectorFilter, setDetectorFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listObservations(statusFilter || undefined, detectorFilter || undefined, 100);
      setItems(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки наблюдений.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, detectorFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const detectors = useMemo(() => Array.from(new Set(items.map((item) => item.detector))).sort(), [items]);

  async function handleRun() {
    try {
      await runObserver();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось запустить наблюдатель.");
    }
  }

  async function handleDismiss(id: string) {
    await dismissObservation(id);
    await load();
  }

  async function handleActioned(id: string) {
    await actionedObservation(id);
    await load();
  }

  async function handlePostpone(id: string) {
    const dt = new Date(Date.now() + 60 * 60 * 1000).toISOString();
    await postponeObservation(id, { postponed_until: dt });
    await load();
  }

  function buildContext(item: ObservationItem): string {
    return [
      `Нужно обсудить наблюдение.`,
      `Detector: ${item.detector}`,
      `Severity: ${item.severity}`,
      `Title: ${item.title}`,
      `Details: ${item.details}`,
      `Context: ${JSON.stringify(item.context_payload)}`,
    ].join("\n");
  }

  return (
    <section className="page" aria-label="Наблюдатель">
      <div className="page__row">
        <h2 className="page__title">Наблюдатель</h2>
        <button type="button" className="chat-action-button" onClick={() => void handleRun()}>
          Проверить сейчас
        </button>
      </div>

      {error ? <p className="status-text status-text--error">{error}</p> : null}

      <div className="memory-section">
        <h3 className="memory-section__title">Фильтры</h3>
        <div className="chat-edit-panel__actions">
          <select className="settings-form__input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">Все статусы</option>
            <option value="new">new</option>
            <option value="seen">seen</option>
            <option value="dismissed">dismissed</option>
            <option value="actioned">actioned</option>
          </select>
          <select className="settings-form__input" value={detectorFilter} onChange={(e) => setDetectorFilter(e.target.value)}>
            <option value="">Все детекторы</option>
            {detectors.map((detector) => (
              <option key={detector} value={detector}>
                {detector}
              </option>
            ))}
          </select>
          <button type="button" className="chat-edit-button" onClick={() => void load()}>
            Применить
          </button>
        </div>
      </div>

      {loading ? <p className="status-text">Загрузка...</p> : null}
      {!loading && items.length === 0 ? <p className="status-text">Наблюдений пока нет.</p> : null}
      <ul className="memory-list">
        {items.map((item) => (
          <li key={item.id} className="memory-list__item">
            <h3 className="memory-list__title">{item.title}</h3>
            <p className="memory-list__text">{item.details}</p>
            <p className="status-text">
              {item.detector} · {item.severity} · {item.status}
            </p>
            <div className="memory-actions">
              <button type="button" className="chat-edit-button" onClick={() => void handleDismiss(item.id)}>
                Dismiss
              </button>
              <button type="button" className="chat-edit-button" onClick={() => void handlePostpone(item.id)}>
                Postpone 1h
              </button>
              <button type="button" className="chat-edit-button" onClick={() => onDiscuss(buildContext(item))}>
                Обсудить с Asya
              </button>
              <button type="button" className="chat-edit-button" onClick={() => void handleActioned(item.id)}>
                Actioned
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

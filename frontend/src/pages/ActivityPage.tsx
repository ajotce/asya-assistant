import { FormEvent, useEffect, useState } from "react";

import { listActivityLog, listSpaces } from "../api/client";
import type { ActivityLogItem, ActivityLogListRequest, SpaceListItem } from "../types/api";

const EVENT_OPTIONS = [
  "",
  "space_created",
  "space_updated",
  "space_archived",
  "memory_fact_created",
  "memory_episode_created",
  "memory_status_changed",
  "rule_applied",
  "personality_applied",
  "memory_used_in_response",
  "memory_snapshot_created",
  "memory_rollback",
] as const;

const ENTITY_OPTIONS = [
  "",
  "space",
  "space_settings",
  "user_profile_fact",
  "memory_episode",
  "behavior_rule",
  "personality_profile",
  "memory_snapshot",
  "memory_change",
] as const;

export default function ActivityPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<ActivityLogItem[]>([]);
  const [spaces, setSpaces] = useState<SpaceListItem[]>([]);
  const [filters, setFilters] = useState<ActivityLogListRequest>({ limit: 100 });

  useEffect(() => {
    void loadAll({ limit: 100 });
  }, []);

  async function loadAll(nextFilters: ActivityLogListRequest) {
    setLoading(true);
    setError(null);
    try {
      const [eventsData, spacesData] = await Promise.all([
        listActivityLog(nextFilters),
        listSpaces(),
      ]);
      setEvents(eventsData);
      setSpaces(spacesData.filter((space) => !space.is_archived));
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }

  async function handleApplyFilters(event: FormEvent) {
    event.preventDefault();
    await loadAll(filters);
  }

  if (loading) {
    return (
      <section className="page" aria-label="Лента активности Asya">
        <h2 className="page__title">Активность</h2>
        <p className="status-text">Загрузка ленты активности...</p>
      </section>
    );
  }

  return (
    <section className="page" aria-label="Лента активности Asya">
      <div className="page__row">
        <h2 className="page__title">Активность</h2>
        <button type="button" className="chat-action-button" onClick={() => void loadAll(filters)}>
          Обновить
        </button>
      </div>

      <form className="settings-form" onSubmit={handleApplyFilters}>
        <label className="settings-form__label" htmlFor="activity-event-type">Тип события</label>
        <select
          id="activity-event-type"
          className="settings-form__input"
          value={filters.event_type ?? ""}
          onChange={(e) => setFilters({ ...filters, event_type: e.target.value || undefined })}
        >
          {EVENT_OPTIONS.map((value) => (
            <option key={value || "all-events"} value={value}>
              {value ? eventTypeLabel(value) : "Все события"}
            </option>
          ))}
        </select>

        <label className="settings-form__label" htmlFor="activity-entity-type">Тип сущности</label>
        <select
          id="activity-entity-type"
          className="settings-form__input"
          value={filters.entity_type ?? ""}
          onChange={(e) => setFilters({ ...filters, entity_type: e.target.value || undefined })}
        >
          {ENTITY_OPTIONS.map((value) => (
            <option key={value || "all-entities"} value={value}>
              {value ? entityTypeLabel(value) : "Все сущности"}
            </option>
          ))}
        </select>

        <label className="settings-form__label" htmlFor="activity-space">Пространство</label>
        <select
          id="activity-space"
          className="settings-form__input"
          value={filters.space_id ?? ""}
          onChange={(e) => setFilters({ ...filters, space_id: e.target.value || undefined })}
        >
          <option value="">Все пространства</option>
          {spaces.map((space) => (
            <option key={space.id} value={space.id}>
              {space.name}
            </option>
          ))}
        </select>

        <label className="settings-form__label" htmlFor="activity-date-from">Дата от (ISO)</label>
        <input
          id="activity-date-from"
          className="settings-form__input"
          placeholder="2026-05-02T00:00:00Z"
          value={filters.date_from ?? ""}
          onChange={(e) => setFilters({ ...filters, date_from: e.target.value || undefined })}
        />

        <label className="settings-form__label" htmlFor="activity-date-to">Дата до (ISO)</label>
        <input
          id="activity-date-to"
          className="settings-form__input"
          placeholder="2026-05-02T23:59:59Z"
          value={filters.date_to ?? ""}
          onChange={(e) => setFilters({ ...filters, date_to: e.target.value || undefined })}
        />

        <button type="submit" className="settings-form__submit">Применить фильтры</button>
      </form>

      {error ? <p className="status-text status-text--error">{error}</p> : null}
      {!events.length ? <p className="status-text">Событий пока нет.</p> : null}

      <ul className="memory-list" aria-label="Список событий активности">
        {events.map((item) => (
          <li key={item.id} className="memory-list__item">
            <p className="memory-list__title">{eventTypeLabel(item.event_type)}</p>
            <p className="memory-list__text">{item.summary}</p>
            <p className="status-text">
              Сущность: {entityTypeLabel(item.entity_type)} · Пространство: {spaceNameById(spaces, item.space_id)} · Время: {formatDate(item.created_at)}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function eventTypeLabel(value: string): string {
  if (value === "space_created") return "Создано пространство";
  if (value === "space_updated") return "Обновлено пространство";
  if (value === "space_archived") return "Архивировано пространство";
  if (value === "memory_fact_created") return "Создан факт памяти";
  if (value === "memory_episode_created") return "Создан эпизод памяти";
  if (value === "memory_status_changed") return "Изменён факт/статус памяти";
  if (value === "rule_applied") return "Изменено правило поведения";
  if (value === "personality_applied") return "Изменена личность Asya";
  if (value === "memory_used_in_response") return "Память использована в ответе";
  if (value === "memory_snapshot_created") return "Создан snapshot памяти";
  if (value === "memory_rollback") return "Откат памяти";
  return value;
}

function entityTypeLabel(value: string): string {
  if (value === "space") return "Пространство";
  if (value === "space_settings") return "Настройки пространства";
  if (value === "user_profile_fact") return "Факт профиля";
  if (value === "memory_episode") return "Эпизод памяти";
  if (value === "behavior_rule") return "Правило поведения";
  if (value === "personality_profile") return "Профиль личности";
  if (value === "memory_snapshot") return "Snapshot памяти";
  if (value === "memory_change") return "Изменение памяти";
  return value;
}

function spaceNameById(spaces: SpaceListItem[], spaceId?: string | null): string {
  if (!spaceId) {
    return "Глобально";
  }
  const found = spaces.find((space) => space.id === spaceId);
  return found ? found.name : "Другое пространство";
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ru-RU");
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Не удалось выполнить запрос.";
}

import { FormEvent, useEffect, useState } from "react";

import {
  createMemoryFact,
  createMemoryRule,
  createMemorySnapshot,
  disableMemoryRule,
  forbidMemoryFact,
  getMemorySnapshotSummary,
  getPersonalityProfile,
  listMemoryEpisodes,
  listMemoryFacts,
  listMemoryRules,
  listMemorySnapshots,
  rollbackMemorySnapshot,
  updateMemoryFact,
  updateMemoryFactStatus,
  updateMemoryRule,
  updatePersonalityProfile,
} from "../api/client";
import type {
  BehaviorRuleCreateRequest,
  BehaviorRuleItem,
  BehaviorRuleUpdateRequest,
  MemoryEpisodeItem,
  MemoryFactCreateRequest,
  MemoryFactItem,
  PersonalityProfile,
  PersonalityProfileUpdateRequest,
  MemorySnapshotItem,
  MemorySnapshotSummary,
} from "../types/api";

const MEMORY_STATUSES = ["confirmed", "inferred", "needs_review", "outdated", "forbidden", "deleted"] as const;

export default function MemoryPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [facts, setFacts] = useState<MemoryFactItem[]>([]);
  const [rules, setRules] = useState<BehaviorRuleItem[]>([]);
  const [episodes, setEpisodes] = useState<MemoryEpisodeItem[]>([]);
  const [personality, setPersonality] = useState<PersonalityProfile | null>(null);
  const [snapshots, setSnapshots] = useState<MemorySnapshotItem[]>([]);
  const [selectedSnapshotSummary, setSelectedSnapshotSummary] = useState<MemorySnapshotSummary | null>(null);
  const [newSnapshotLabel, setNewSnapshotLabel] = useState("Manual snapshot");

  const [newFact, setNewFact] = useState<MemoryFactCreateRequest>({
    key: "",
    value: "",
    status: "needs_review",
    source: "user",
  });
  const [newRule, setNewRule] = useState<BehaviorRuleCreateRequest>({
    title: "",
    instruction: "",
    scope: "user",
    strictness: "normal",
    source: "user",
    status: "active",
  });
  const [personalityForm, setPersonalityForm] = useState<PersonalityProfileUpdateRequest | null>(null);

  useEffect(() => {
    void loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [factsData, rulesData, episodesData, personalityData, snapshotsData] = await Promise.all([
        listMemoryFacts(false),
        listMemoryRules(false),
        listMemoryEpisodes(true),
        getPersonalityProfile(),
        listMemorySnapshots(),
      ]);
      setFacts(factsData);
      setRules(rulesData);
      setEpisodes(episodesData);
      setPersonality(personalityData);
      setSnapshots(snapshotsData);
      setPersonalityForm({
        name: personalityData.name,
        tone: personalityData.tone,
        style_notes: personalityData.style_notes,
        humor_level: personalityData.humor_level,
        initiative_level: personalityData.initiative_level,
        can_gently_disagree: personalityData.can_gently_disagree,
        address_user_by_name: personalityData.address_user_by_name,
        is_active: personalityData.is_active,
      });
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateSnapshot(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createMemorySnapshot({ label: newSnapshotLabel });
      await loadAll();
    } catch (actionError) {
      setError(getErrorMessage(actionError));
    } finally {
      setSaving(false);
    }
  }

  async function handleShowSnapshotSummary(snapshotId: string) {
    setSaving(true);
    setError(null);
    try {
      const summary = await getMemorySnapshotSummary(snapshotId);
      setSelectedSnapshotSummary(summary);
    } catch (actionError) {
      setError(getErrorMessage(actionError));
    } finally {
      setSaving(false);
    }
  }

  async function handleRollbackSnapshot(snapshot: MemorySnapshotItem) {
    const confirmed = window.confirm(`Выполнить rollback по snapshot "${snapshot.label}"?`);
    if (!confirmed) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await rollbackMemorySnapshot(snapshot.id);
      await loadAll();
    } catch (actionError) {
      setError(getErrorMessage(actionError));
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateFact(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createMemoryFact(newFact);
      setNewFact({ key: "", value: "", status: "needs_review", source: "user" });
      await loadAll();
    } catch (saveError) {
      setError(getErrorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateRule(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createMemoryRule(newRule);
      setNewRule({ title: "", instruction: "", scope: "user", strictness: "normal", source: "user", status: "active" });
      await loadAll();
    } catch (saveError) {
      setError(getErrorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  async function handleFactAction(action: "confirm" | "outdated" | "forbid" | "delete", fact: MemoryFactItem) {
    setSaving(true);
    setError(null);
    try {
      if (action === "forbid") {
        await forbidMemoryFact(fact.id);
      } else if (action === "confirm") {
        await updateMemoryFactStatus(fact.id, { status: "confirmed" });
      } else if (action === "outdated") {
        await updateMemoryFactStatus(fact.id, { status: "outdated" });
      } else {
        await updateMemoryFactStatus(fact.id, { status: "deleted" });
      }
      await loadAll();
    } catch (actionError) {
      setError(getErrorMessage(actionError));
    } finally {
      setSaving(false);
    }
  }

  async function handleFactEdit(fact: MemoryFactItem) {
    const nextValue = window.prompt("Изменить значение факта", fact.value)?.trim();
    if (!nextValue) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateMemoryFact(fact.id, { key: fact.key, value: nextValue, source: fact.source });
      await loadAll();
    } catch (actionError) {
      setError(getErrorMessage(actionError));
    } finally {
      setSaving(false);
    }
  }

  async function handleRuleEdit(rule: BehaviorRuleItem) {
    const nextInstruction = window.prompt("Изменить текст правила", rule.instruction)?.trim();
    if (!nextInstruction) {
      return;
    }
    const payload: BehaviorRuleUpdateRequest = {
      title: rule.title,
      instruction: nextInstruction,
      scope: rule.scope,
      strictness: rule.strictness,
      source: rule.source,
      status: rule.status,
      space_id: rule.space_id,
    };
    setSaving(true);
    setError(null);
    try {
      await updateMemoryRule(rule.id, payload);
      await loadAll();
    } catch (actionError) {
      setError(getErrorMessage(actionError));
    } finally {
      setSaving(false);
    }
  }

  async function handleDisableRule(rule: BehaviorRuleItem) {
    setSaving(true);
    setError(null);
    try {
      await disableMemoryRule(rule.id);
      await loadAll();
    } catch (actionError) {
      setError(getErrorMessage(actionError));
    } finally {
      setSaving(false);
    }
  }

  async function handleSavePersonality(event: FormEvent) {
    event.preventDefault();
    if (!personalityForm) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updatePersonalityProfile(personalityForm);
      await loadAll();
    } catch (actionError) {
      setError(getErrorMessage(actionError));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <section className="page" aria-label="Память Asya">
        <h2 className="page__title">Память</h2>
        <p className="status-text">Загрузка памяти...</p>
      </section>
    );
  }

  return (
    <section className="page" aria-label="Память Asya">
      <div className="page__row">
        <h2 className="page__title">Память</h2>
        <button type="button" className="chat-action-button" onClick={() => void loadAll()} disabled={saving || loading}>
          Обновить
        </button>
      </div>
      {error ? <p className="status-text status-text--error">{error}</p> : null}

      <section className="memory-section">
        <h3 className="memory-section__title">Snapshots памяти</h3>
        <form className="settings-form" onSubmit={handleCreateSnapshot}>
          <label className="settings-form__label" htmlFor="snapshot-label">Название snapshot</label>
          <input
            id="snapshot-label"
            className="settings-form__input"
            value={newSnapshotLabel}
            onChange={(e) => setNewSnapshotLabel(e.target.value)}
          />
          <button type="submit" className="settings-form__submit" disabled={saving}>Создать snapshot</button>
        </form>
        {!snapshots.length ? <p className="status-text">Snapshots пока нет.</p> : null}
        <ul className="memory-list" aria-label="Список snapshots памяти">
          {snapshots.map((snapshot) => (
            <li key={snapshot.id} className="memory-list__item">
              <p className="memory-list__title">{snapshot.label}</p>
              <p className="status-text">Создано: {formatDate(snapshot.created_at)}</p>
              <div className="memory-actions">
                <button type="button" className="chat-edit-button" onClick={() => void handleShowSnapshotSummary(snapshot.id)} disabled={saving}>Summary</button>
                <button type="button" className="chat-edit-button" onClick={() => void handleRollbackSnapshot(snapshot)} disabled={saving}>Rollback</button>
              </div>
            </li>
          ))}
        </ul>
        {selectedSnapshotSummary ? (
          <p className="status-text">
            Summary: facts={selectedSnapshotSummary.facts_count}, rules={selectedSnapshotSummary.rules_count}, episodes={selectedSnapshotSummary.episodes_count}, personality={selectedSnapshotSummary.personality_profiles_count}, settings={selectedSnapshotSummary.space_settings_count}
          </p>
        ) : null}
      </section>

      <section className="memory-section">
        <h3 className="memory-section__title">Личность Asya</h3>
        {personalityForm ? (
          <form className="settings-form" onSubmit={handleSavePersonality}>
            <label className="settings-form__label" htmlFor="personality-name">Имя ассистента</label>
            <input id="personality-name" className="settings-form__input" value={personalityForm.name} onChange={(e) => setPersonalityForm({ ...personalityForm, name: e.target.value })} />

            <label className="settings-form__label" htmlFor="personality-tone">Тон</label>
            <input id="personality-tone" className="settings-form__input" value={personalityForm.tone} onChange={(e) => setPersonalityForm({ ...personalityForm, tone: e.target.value })} />

            <label className="settings-form__label" htmlFor="personality-humor">Уровень юмора</label>
            <select id="personality-humor" className="settings-form__input" value={personalityForm.humor_level} onChange={(e) => setPersonalityForm({ ...personalityForm, humor_level: Number(e.target.value) })}>
              <option value={0}>Низкий</option>
              <option value={1}>Средний</option>
              <option value={2}>Высокий</option>
            </select>

            <label className="settings-form__label" htmlFor="personality-initiative">Краткость/подробность</label>
            <select id="personality-initiative" className="settings-form__input" value={personalityForm.initiative_level} onChange={(e) => setPersonalityForm({ ...personalityForm, initiative_level: Number(e.target.value) })}>
              <option value={0}>Кратко</option>
              <option value={1}>Сбалансированно</option>
              <option value={2}>Подробнее</option>
            </select>

            <label className="spaces-settings__toggle">
              <input type="checkbox" checked={personalityForm.can_gently_disagree} onChange={(e) => setPersonalityForm({ ...personalityForm, can_gently_disagree: e.target.checked })} />
              Мягкое возражение при рисках
            </label>
            <label className="spaces-settings__toggle">
              <input type="checkbox" checked={personalityForm.address_user_by_name} onChange={(e) => setPersonalityForm({ ...personalityForm, address_user_by_name: e.target.checked })} />
              Обращаться по имени
            </label>

            <label className="settings-form__label" htmlFor="personality-style">Комментарий к стилю</label>
            <textarea id="personality-style" className="settings-form__textarea" rows={3} value={personalityForm.style_notes} onChange={(e) => setPersonalityForm({ ...personalityForm, style_notes: e.target.value })} />

            <button type="submit" className="settings-form__submit" disabled={saving}>Сохранить личность</button>
            {personality ? (
              <p className="status-text">Создано: {formatDate(personality.created_at)} · Обновлено: {formatDate(personality.updated_at)}</p>
            ) : null}
          </form>
        ) : (
          <p className="status-text">Профиль личности пока не доступен.</p>
        )}
      </section>

      <section className="memory-section">
        <h3 className="memory-section__title">Факты профиля</h3>
        <form className="settings-form" onSubmit={handleCreateFact}>
          <label className="settings-form__label" htmlFor="fact-key">Ключ</label>
          <input id="fact-key" className="settings-form__input" value={newFact.key} onChange={(e) => setNewFact({ ...newFact, key: e.target.value })} />

          <label className="settings-form__label" htmlFor="fact-value">Значение</label>
          <input id="fact-value" className="settings-form__input" value={newFact.value} onChange={(e) => setNewFact({ ...newFact, value: e.target.value })} />

          <label className="settings-form__label" htmlFor="fact-status">Статус</label>
          <select id="fact-status" className="settings-form__input" value={newFact.status} onChange={(e) => setNewFact({ ...newFact, status: e.target.value })}>
            {MEMORY_STATUSES.map((status) => (
              <option key={status} value={status}>{statusLabel(status)}</option>
            ))}
          </select>

          <button type="submit" className="settings-form__submit" disabled={saving}>Создать факт</button>
        </form>

        {!facts.length ? <p className="status-text">Фактов пока нет.</p> : null}
        <ul className="memory-list" aria-label="Список фактов памяти">
          {facts.map((fact) => (
            <li key={fact.id} className="memory-list__item">
              <p className="memory-list__title">{fact.key}</p>
              <p className="memory-list__text">{fact.value}</p>
              <p className="status-text">
                Статус: {statusLabel(fact.status)} · Источник: {sourceLabel(fact.source)} · Создано: {formatDate(fact.created_at)} · Обновлено: {formatDate(fact.updated_at)}
              </p>
              <div className="memory-actions">
                <button type="button" className="chat-edit-button" onClick={() => void handleFactAction("confirm", fact)} disabled={saving}>Подтвердить</button>
                <button type="button" className="chat-edit-button" onClick={() => void handleFactEdit(fact)} disabled={saving}>Редактировать</button>
                <button type="button" className="chat-edit-button" onClick={() => void handleFactAction("outdated", fact)} disabled={saving}>Устарело</button>
                <button type="button" className="chat-edit-button" onClick={() => void handleFactAction("forbid", fact)} disabled={saving}>Запретить</button>
                <button type="button" className="chat-edit-button" onClick={() => void handleFactAction("delete", fact)} disabled={saving}>Скрыть</button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="memory-section">
        <h3 className="memory-section__title">Правила поведения</h3>
        <form className="settings-form" onSubmit={handleCreateRule}>
          <label className="settings-form__label" htmlFor="rule-title">Название</label>
          <input id="rule-title" className="settings-form__input" value={newRule.title} onChange={(e) => setNewRule({ ...newRule, title: e.target.value })} />

          <label className="settings-form__label" htmlFor="rule-instruction">Инструкция</label>
          <textarea id="rule-instruction" className="settings-form__textarea" rows={3} value={newRule.instruction} onChange={(e) => setNewRule({ ...newRule, instruction: e.target.value })} />

          <button type="submit" className="settings-form__submit" disabled={saving}>Создать правило</button>
        </form>

        {!rules.length ? <p className="status-text">Правил пока нет.</p> : null}
        <ul className="memory-list" aria-label="Список правил поведения">
          {rules.map((rule) => (
            <li key={rule.id} className="memory-list__item">
              <p className="memory-list__title">{rule.title}</p>
              <p className="memory-list__text">{rule.instruction}</p>
              <p className="status-text">
                Статус: {ruleStatusLabel(rule.status)} · Источник: {sourceLabel(rule.source)} · Создано: {formatDate(rule.created_at)} · Обновлено: {formatDate(rule.updated_at)}
              </p>
              <div className="memory-actions">
                <button type="button" className="chat-edit-button" onClick={() => void handleRuleEdit(rule)} disabled={saving}>Редактировать</button>
                <button type="button" className="chat-edit-button" onClick={() => void handleDisableRule(rule)} disabled={saving || rule.status === "disabled"}>Отключить</button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="memory-section">
        <h3 className="memory-section__title">Эпизоды памяти</h3>
        {!episodes.length ? <p className="status-text">Эпизодов пока нет.</p> : null}
        <ul className="memory-list" aria-label="Список эпизодов памяти">
          {episodes.map((episode) => (
            <li key={episode.id} className="memory-list__item">
              <p className="memory-list__text">{episode.summary}</p>
              <p className="status-text">
                Статус: {statusLabel(episode.status)} · Источник: {sourceLabel(episode.source)} · Создано: {formatDate(episode.created_at)} · Обновлено: {formatDate(episode.updated_at)}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}

function statusLabel(status: string): string {
  if (status === "confirmed") {
    return "Подтверждено";
  }
  if (status === "inferred") {
    return "Выведено";
  }
  if (status === "needs_review") {
    return "Требует проверки";
  }
  if (status === "outdated") {
    return "Устарело";
  }
  if (status === "forbidden") {
    return "Запрещено";
  }
  if (status === "deleted") {
    return "Скрыто";
  }
  return status;
}

function ruleStatusLabel(status: string): string {
  if (status === "active") {
    return "Активно";
  }
  if (status === "disabled") {
    return "Отключено";
  }
  return status;
}

function sourceLabel(source: string): string {
  if (source === "user") {
    return "Пользователь";
  }
  if (source === "assistant") {
    return "Ассистент";
  }
  if (source === "user_explicit") {
    return "Явная команда пользователя";
  }
  if (source === "assistant_inferred") {
    return "Вывод ассистента";
  }
  return source;
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

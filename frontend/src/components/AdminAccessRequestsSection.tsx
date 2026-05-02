import { useEffect, useState } from "react";

import {
  approveAdminAccessRequest,
  listAdminAccessRequests,
  rejectAdminAccessRequest,
} from "../api/client";
import type { AccessRequestResponse } from "../types/api";

export default function AdminAccessRequestsSection() {
  const [items, setItems] = useState<AccessRequestResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    void loadPending();
  }, []);

  async function loadPending() {
    setLoading(true);
    setError(null);
    try {
      const all = await listAdminAccessRequests();
      setItems(all.filter((item) => item.status === "pending"));
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }

  async function approve(requestId: string) {
    setBusyId(requestId);
    setError(null);
    setSuccess(null);
    try {
      const response = await approveAdminAccessRequest(requestId);
      setItems((prev) => prev.filter((item) => item.id !== requestId));
      setSuccess(`Заявка одобрена: ${response.user.email}. Setup link: ${response.setup_link}`);
    } catch (approveError) {
      setError(getErrorMessage(approveError));
    } finally {
      setBusyId(null);
    }
  }

  async function reject(requestId: string) {
    setBusyId(requestId);
    setError(null);
    setSuccess(null);
    try {
      await rejectAdminAccessRequest(requestId);
      setItems((prev) => prev.filter((item) => item.id !== requestId));
      setSuccess("Заявка отклонена.");
    } catch (rejectError) {
      setError(getErrorMessage(rejectError));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="page" aria-label="Admin заявки на доступ">
      <div className="page__row">
        <h3 className="page__title">Admin: Заявки на доступ</h3>
        <button type="button" className="chat-action-button" onClick={() => void loadPending()} disabled={loading}>
          {loading ? "Обновление..." : "Обновить"}
        </button>
      </div>

      <p className="status-text">Approve создаёт one-time setup link и отправляет его по email (smtp/mock).</p>
      {error ? <p className="status-text status-text--error">{error}</p> : null}
      {success ? <p className="status-text status-text--ok">{success}</p> : null}

      {loading ? <p className="status-text">Загрузка pending заявок...</p> : null}
      {!loading && items.length === 0 ? <p className="status-text">Pending заявок нет.</p> : null}

      <ul className="chat-sidebar__list">
        {items.map((item) => (
          <li key={item.id} className="chat-sidebar__item">
            <div className="chat-sidebar__select">
              <strong>{item.display_name}</strong>
              <div>{item.email}</div>
              <div className="status-text">Создана: {new Date(item.created_at).toLocaleString()}</div>
            </div>
            <div className="chat-sidebar__actions">
              <button
                type="button"
                className="chat-edit-button"
                onClick={() => void approve(item.id)}
                disabled={busyId === item.id}
              >
                Approve
              </button>
              <button
                type="button"
                className="chat-edit-button"
                onClick={() => void reject(item.id)}
                disabled={busyId === item.id}
              >
                Reject
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Не удалось выполнить запрос.";
}

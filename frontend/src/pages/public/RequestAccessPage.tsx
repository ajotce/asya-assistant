import { FormEvent, useEffect, useState } from "react";

import { submitAccessRequest } from "../../api/client";
import { applySeo } from "../../seo";

export default function RequestAccessPage() {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [reason, setReason] = useState("");
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    applySeo({
      title: "Запросить инвайт — Asya",
      description: "Оставьте заявку на ранний доступ к Asya: email, имя и короткое описание сценария.",
      path: "/request-access",
    });
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!consentAccepted) {
      setError("Подтвердите согласие с условиями использования и политикой конфиденциальности.");
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      await submitAccessRequest({
        email: email.trim(),
        display_name: displayName.trim(),
        reason: reason.trim(),
      });
      setSuccess("Заявка отправлена. Мы свяжемся с вами после проверки.");
      setEmail("");
      setDisplayName("");
      setReason("");
      setConsentAccepted(false);
    } catch (submitError) {
      setError(getErrorMessage(submitError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page public-page" aria-label="Запросить инвайт">
      <h1 className="page__title">Запросить инвайт</h1>
      <p>Оставьте контакт и контекст использования Asya. Это помогает быстрее обработать заявку.</p>

      {error ? <p className="status-text status-text--error">{error}</p> : null}
      {success ? <p className="status-text status-text--ok">{success}</p> : null}

      <form className="settings-form" onSubmit={handleSubmit}>
        <label className="settings-form__label" htmlFor="request-email">
          Email
        </label>
        <input
          id="request-email"
          className="settings-form__input"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />

        <label className="settings-form__label" htmlFor="request-name">
          Имя
        </label>
        <input
          id="request-name"
          className="settings-form__input"
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
          required
        />

        <label className="settings-form__label" htmlFor="request-reason">
          Коротко о себе и сценарии
        </label>
        <textarea
          id="request-reason"
          className="settings-form__textarea"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          minLength={3}
          required
        />

        <label className="consent-checkbox" htmlFor="legal-consent">
          <input
            id="legal-consent"
            type="checkbox"
            checked={consentAccepted}
            onChange={(event) => setConsentAccepted(event.target.checked)}
            required
          />
          <span>
            Я принимаю <a href="/terms">условия использования</a> и <a href="/privacy">политику конфиденциальности</a>.
          </span>
        </label>

        <button type="submit" className="settings-form__submit" disabled={loading || !consentAccepted}>
          {loading ? "Отправка..." : "Отправить заявку"}
        </button>
      </form>
    </section>
  );
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Не удалось выполнить запрос.";
}

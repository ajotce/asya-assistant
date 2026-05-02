import { FormEvent, useMemo, useState } from "react";

import { authLogin, authRegister, authSetupPassword, submitAccessRequest } from "../api/client";
import type { AuthUser } from "../types/api";

type AuthMode = "login" | "register" | "request" | "setup";

interface AuthPageProps {
  onAuthenticated: (user: AuthUser) => void;
}

export default function AuthPage({ onAuthenticated }: AuthPageProps) {
  const queryToken = useMemo(() => new URLSearchParams(window.location.search).get("token") ?? "", []);
  const initialMode: AuthMode = window.location.pathname.startsWith("/setup-password") ? "setup" : "login";

  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [reason, setReason] = useState("");
  const [setupToken, setSetupToken] = useState(queryToken);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      if (mode === "login") {
        const user = await authLogin({ email: email.trim(), password });
        onAuthenticated(user);
        return;
      }

      if (mode === "register") {
        const response = await authRegister({
          email: email.trim(),
          display_name: displayName.trim(),
          password,
        });
        if (response.status === "registered" && response.user) {
          const user = await authLogin({ email: email.trim(), password });
          onAuthenticated(user);
          return;
        }
        if (response.status === "request_saved") {
          setSuccess("Регистрация закрыта. Заявка сохранена.");
          setMode("request");
          return;
        }
      }

      if (mode === "request") {
        await submitAccessRequest({
          email: email.trim(),
          display_name: displayName.trim(),
          reason: reason.trim(),
        });
        setSuccess("Заявка отправлена. Дождитесь подтверждения доступа.");
        return;
      }

      if (mode === "setup") {
        const user = await authSetupPassword({ token: setupToken.trim(), password });
        onAuthenticated(user);
      }
    } catch (submitError) {
      setError(getErrorMessage(submitError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page auth-page" aria-label="Авторизация">
      <h2 className="page__title">Вход в Asya</h2>
      <div className="auth-switcher" role="group" aria-label="Режим авторизации">
        <button type="button" className="chat-action-button" onClick={() => setMode("login")} disabled={loading || mode === "setup"}>
          Вход
        </button>
        <button type="button" className="chat-action-button" onClick={() => setMode("register")} disabled={loading || mode === "setup"}>
          Регистрация
        </button>
        <button type="button" className="chat-action-button" onClick={() => setMode("request")} disabled={loading || mode === "setup"}>
          Заявка на доступ
        </button>
      </div>

      {error ? <p className="status-text status-text--error">{error}</p> : null}
      {success ? <p className="status-text status-text--ok">{success}</p> : null}

      <form className="settings-form" onSubmit={handleSubmit}>
        {mode === "setup" ? (
          <>
            <p className="status-text">Подтвердите доступ: задайте пароль для аккаунта по одноразовой ссылке.</p>
            <label className="settings-form__label" htmlFor="setup-token">
              Setup token
            </label>
            <input
              id="setup-token"
              className="settings-form__input"
              value={setupToken}
              onChange={(event) => setSetupToken(event.target.value)}
              required
            />
          </>
        ) : (
          <>
            <label className="settings-form__label" htmlFor="auth-email">
              Email
            </label>
            <input
              id="auth-email"
              className="settings-form__input"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              type="email"
              autoComplete="email"
              required
            />

            {mode !== "login" ? (
              <>
                <label className="settings-form__label" htmlFor="auth-display-name">
                  Имя
                </label>
                <input
                  id="auth-display-name"
                  className="settings-form__input"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  autoComplete="name"
                  required
                />
              </>
            ) : null}

            {mode === "request" ? (
              <>
                <label className="settings-form__label" htmlFor="auth-request-reason">
                  Почему хотите попробовать Asya
                </label>
                <textarea
                  id="auth-request-reason"
                  className="settings-form__textarea"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  required
                  minLength={3}
                />
              </>
            ) : null}
          </>
        )}

        <label className="settings-form__label" htmlFor="auth-password">
          Пароль
        </label>
        <input
          id="auth-password"
          className="settings-form__input"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          type="password"
          autoComplete={mode === "register" || mode === "setup" ? "new-password" : "current-password"}
          minLength={8}
          required
        />

        <button type="submit" className="settings-form__submit" disabled={loading}>
          {loading
            ? "Отправка..."
            : mode === "login"
              ? "Войти"
              : mode === "register"
                ? "Создать аккаунт"
                : mode === "request"
                  ? "Отправить заявку"
                  : "Задать пароль"}
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

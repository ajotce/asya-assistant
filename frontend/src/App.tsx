import { useEffect, useState } from "react";

import { authLogout, authMe } from "./api/client";
import AppHeader from "./components/AppHeader";
import NavTabs, { type AppTab } from "./components/NavTabs";
import { useTheme } from "./hooks/useTheme";
import AuthPage from "./pages/AuthPage";
import ChatPage from "./pages/ChatPage";
import SettingsPage from "./pages/SettingsPage";
import StatusPage from "./pages/StatusPage";
import type { AuthUser } from "./types/api";
import "./styles/app.css";

export default function App() {
  const { preference: themePreference, setPreference: setThemePreference } = useTheme();
  const [activeTab, setActiveTab] = useState<AppTab>(() => getTabFromPath(window.location.pathname));
  const [mountedTabs, setMountedTabs] = useState<Record<AppTab, boolean>>(() =>
    buildInitialMountedTabs(getTabFromPath(window.location.pathname))
  );
  const [authLoading, setAuthLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [logoutLoading, setLogoutLoading] = useState(false);
  const [preferredChatId, setPreferredChatId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadCurrentUser() {
      setAuthLoading(true);
      setAuthError(null);
      try {
        const user = await authMe();
        if (!active) {
          return;
        }
        setCurrentUser(user);
        setPreferredChatId(user.preferred_chat_id ?? null);
      } catch (error) {
        if (!active) {
          return;
        }
        const message = getErrorMessage(error);
        const unauthorized =
          message.includes("401") || message.toLowerCase().includes("требуется авторизация");
        if (!unauthorized) {
          setAuthError(message);
        }
        setCurrentUser(null);
      } finally {
        if (active) {
          setAuthLoading(false);
        }
      }
    }

    void loadCurrentUser();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    function handlePopState() {
      const tab = getTabFromPath(window.location.pathname);
      setActiveTab(tab);
      setMountedTabs((prev) => markTabMounted(prev, tab));
    }

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  function handleTabChange(tab: AppTab) {
    setActiveTab(tab);
    setMountedTabs((prev) => markTabMounted(prev, tab));
    const nextPath = getPathForTab(tab);
    if (window.location.pathname !== nextPath) {
      window.history.pushState(null, "", nextPath);
    }
  }

  async function handleLogout() {
    setLogoutLoading(true);
    setAuthError(null);
    try {
      await authLogout();
      setCurrentUser(null);
      setPreferredChatId(null);
      setMountedTabs(buildInitialMountedTabs("chat"));
      setActiveTab("chat");
      if (window.location.pathname !== "/") {
        window.history.pushState(null, "", "/");
      }
    } catch (error) {
      setAuthError(getErrorMessage(error));
    } finally {
      setLogoutLoading(false);
    }
  }

  function handleAuthenticated(user: AuthUser) {
    setCurrentUser(user);
    setPreferredChatId(user.preferred_chat_id ?? null);
    setAuthError(null);
    setMountedTabs((prev) => markTabMounted(prev, "chat"));
    setActiveTab("chat");
    if (window.location.pathname !== "/") {
      window.history.pushState(null, "", "/");
    }
  }

  return (
    <div className="app-shell">
      <AppHeader
        title="Asya"
        subtitle="Персональный ИИ-ассистент"
        rightSlot={
          currentUser ? (
            <div className="auth-user">
              <span className="status-text">{currentUser.display_name}</span>
              <button type="button" className="chat-action-button" onClick={handleLogout} disabled={logoutLoading}>
                {logoutLoading ? "Выход..." : "Выйти"}
              </button>
            </div>
          ) : null
        }
      />
      {authLoading ? <p className="status-text">Проверка авторизации...</p> : null}
      {authError ? <p className="status-text status-text--error">{authError}</p> : null}
      {!authLoading && !currentUser ? (
        <AuthPage onAuthenticated={handleAuthenticated} />
      ) : null}
      {!authLoading && currentUser ? (
        <>
          <NavTabs activeTab={activeTab} onChange={handleTabChange} />
          <div className="tab-panels">
            {mountedTabs.chat ? (
              <section className="tab-panel" hidden={activeTab !== "chat"}>
                <ChatPage initialSessionId={preferredChatId} />
              </section>
            ) : null}
            {mountedTabs.settings ? (
              <section className="tab-panel" hidden={activeTab !== "settings"}>
                <SettingsPage
                  themePreference={themePreference}
                  onThemePreferenceChange={setThemePreference}
                  currentUserRole={currentUser.role}
                />
              </section>
            ) : null}
            {mountedTabs.status ? (
              <section className="tab-panel" hidden={activeTab !== "status"}>
                <StatusPage />
              </section>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Не удалось выполнить запрос.";
}

function buildInitialMountedTabs(initialTab: AppTab): Record<AppTab, boolean> {
  return {
    chat: initialTab === "chat",
    settings: initialTab === "settings",
    status: initialTab === "status",
  };
}

function markTabMounted(mountedTabs: Record<AppTab, boolean>, tab: AppTab): Record<AppTab, boolean> {
  if (mountedTabs[tab]) {
    return mountedTabs;
  }
  return { ...mountedTabs, [tab]: true };
}

function getTabFromPath(pathname: string): AppTab {
  if (pathname.startsWith("/settings")) {
    return "settings";
  }
  if (pathname.startsWith("/status")) {
    return "status";
  }
  return "chat";
}

function getPathForTab(tab: AppTab): string {
  if (tab === "settings") {
    return "/settings";
  }
  if (tab === "status") {
    return "/status";
  }
  return "/";
}

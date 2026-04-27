import { useEffect, useState } from "react";

import AppHeader from "./components/AppHeader";
import NavTabs, { type AppTab } from "./components/NavTabs";
import { useTheme } from "./hooks/useTheme";
import ChatPage from "./pages/ChatPage";
import SettingsPage from "./pages/SettingsPage";
import StatusPage from "./pages/StatusPage";
import "./styles/app.css";

export default function App() {
  const { preference: themePreference, setPreference: setThemePreference } = useTheme();
  const [activeTab, setActiveTab] = useState<AppTab>(() => getTabFromPath(window.location.pathname));
  const [mountedTabs, setMountedTabs] = useState<Record<AppTab, boolean>>(() =>
    buildInitialMountedTabs(getTabFromPath(window.location.pathname))
  );

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

  return (
    <div className="app-shell">
      <AppHeader title="Asya" subtitle="Персональный ИИ-ассистент" />
      <NavTabs activeTab={activeTab} onChange={handleTabChange} />
      <div className="tab-panels">
        {mountedTabs.chat ? (
          <section className="tab-panel" hidden={activeTab !== "chat"}>
            <ChatPage />
          </section>
        ) : null}
        {mountedTabs.settings ? (
          <section className="tab-panel" hidden={activeTab !== "settings"}>
            <SettingsPage themePreference={themePreference} onThemePreferenceChange={setThemePreference} />
          </section>
        ) : null}
        {mountedTabs.status ? (
          <section className="tab-panel" hidden={activeTab !== "status"}>
            <StatusPage />
          </section>
        ) : null}
      </div>
    </div>
  );
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

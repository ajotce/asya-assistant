import { useEffect, useMemo, useState } from "react";

import AppHeader from "./components/AppHeader";
import NavTabs, { type AppTab } from "./components/NavTabs";
import ChatPage from "./pages/ChatPage";
import SettingsPage from "./pages/SettingsPage";
import StatusPage from "./pages/StatusPage";
import "./styles/app.css";

export default function App() {
  const [activeTab, setActiveTab] = useState<AppTab>(() => getTabFromPath(window.location.pathname));

  useEffect(() => {
    function handlePopState() {
      setActiveTab(getTabFromPath(window.location.pathname));
    }

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const page = useMemo(() => {
    if (activeTab === "settings") {
      return <SettingsPage />;
    }
    if (activeTab === "status") {
      return <StatusPage />;
    }
    return <ChatPage />;
  }, [activeTab]);

  function handleTabChange(tab: AppTab) {
    setActiveTab(tab);
    const nextPath = getPathForTab(tab);
    if (window.location.pathname !== nextPath) {
      window.history.pushState(null, "", nextPath);
    }
  }

  return (
    <div className="app-shell">
      <AppHeader title="Asya" subtitle="Персональный ИИ-ассистент" />
      <NavTabs activeTab={activeTab} onChange={handleTabChange} />
      {page}
    </div>
  );
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

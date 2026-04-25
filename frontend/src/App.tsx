import { useMemo, useState } from "react";

import AppHeader from "./components/AppHeader";
import NavTabs, { type AppTab } from "./components/NavTabs";
import ChatPage from "./pages/ChatPage";
import SettingsPage from "./pages/SettingsPage";
import StatusPage from "./pages/StatusPage";
import "./styles/app.css";

export default function App() {
  const [activeTab, setActiveTab] = useState<AppTab>("chat");

  const page = useMemo(() => {
    if (activeTab === "settings") {
      return <SettingsPage />;
    }
    if (activeTab === "status") {
      return <StatusPage />;
    }
    return <ChatPage />;
  }, [activeTab]);

  return (
    <div className="app-shell">
      <AppHeader title="Asya" subtitle="Персональный ИИ-ассистент" />
      <NavTabs activeTab={activeTab} onChange={setActiveTab} />
      {page}
    </div>
  );
}

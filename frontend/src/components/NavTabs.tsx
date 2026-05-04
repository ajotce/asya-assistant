export type AppTab = "chat" | "diary" | "briefings" | "observer" | "memory" | "activity" | "settings" | "status";

interface TabItem {
  id: AppTab;
  label: string;
}

const tabs: TabItem[] = [
  { id: "chat", label: "Чат" },
  { id: "diary", label: "Дневник" },
  { id: "briefings", label: "Брифинги" },
  { id: "observer", label: "Наблюдатель" },
  { id: "memory", label: "Память" },
  { id: "activity", label: "Активность" },
  { id: "settings", label: "Настройки" },
  { id: "status", label: "Состояние" },
];

interface NavTabsProps {
  activeTab: AppTab;
  onChange: (tab: AppTab) => void;
}

export default function NavTabs({ activeTab, onChange }: NavTabsProps) {
  return (
    <nav className="nav-tabs" aria-label="Разделы приложения">
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            type="button"
            className={`nav-tabs__button${isActive ? " nav-tabs__button--active" : ""}`}
            onClick={() => onChange(tab.id)}
            aria-pressed={isActive}
          >
            {tab.label}
          </button>
        );
      })}
    </nav>
  );
}

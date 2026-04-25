import type { ReactNode } from "react";

interface AppHeaderProps {
  title: string;
  subtitle?: string;
  rightSlot?: ReactNode;
}

export default function AppHeader({ title, subtitle, rightSlot }: AppHeaderProps) {
  return (
    <header className="app-header" aria-label="Шапка приложения">
      <div className="app-header__text">
        <h1 className="app-header__title">{title}</h1>
        {subtitle ? <p className="app-header__subtitle">{subtitle}</p> : null}
      </div>
      {rightSlot ? <div className="app-header__right">{rightSlot}</div> : null}
    </header>
  );
}

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("./pages/ChatPage", () => ({
  default: () => <div>Chat page mock</div>,
}));

vi.mock("./pages/SettingsPage", () => ({
  default: () => <div>Settings page mock</div>,
}));

vi.mock("./pages/StatusPage", () => ({
  default: () => <div>Status page mock</div>,
}));

describe("App routing", () => {
  beforeEach(() => {
    window.history.pushState(null, "", "/");
  });

  it("открывает страницу состояния при прямом URL /status", () => {
    window.history.pushState(null, "", "/status");

    render(<App />);

    expect(screen.getByText("Status page mock")).toBeInTheDocument();
  });

  it("синхронизирует вкладку настроек с URL", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Настройки" }));

    expect(screen.getByText("Settings page mock")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/settings");
  });
});

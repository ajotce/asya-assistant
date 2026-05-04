import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { executeRollback, listActivityLog, listReversibleActions, listSpaces, previewRollback } from "../api/client";
import ActivityPage from "./ActivityPage";

vi.mock("../api/client", () => ({
  listActivityLog: vi.fn(),
  listSpaces: vi.fn(),
  listReversibleActions: vi.fn(),
  previewRollback: vi.fn(),
  executeRollback: vi.fn(),
}));

describe("ActivityPage", () => {
  beforeEach(() => {
    vi.mocked(listSpaces).mockResolvedValue([
      {
        id: "space-1",
        name: "Default",
        is_default: true,
        is_admin_only: false,
        is_archived: false,
        created_at: "2026-05-02T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
      },
    ] as never);
    vi.mocked(listActivityLog).mockResolvedValue([
      {
        id: "act-1",
        event_type: "memory_fact_created",
        entity_type: "user_profile_fact",
        entity_id: "fact-1",
        summary: "Создан факт памяти: lang",
        space_id: null,
        created_at: "2026-05-02T00:00:00Z",
      },
    ] as never);
    vi.mocked(listReversibleActions).mockResolvedValue([
      {
        id: "ae-1",
        provider: "todoist",
        operation: "update",
        target_id: "task-1",
        reversible: true,
        rollback_status: "not_requested",
        safe_metadata: { activity_log_id: "act-1" },
        created_at: "2026-05-02T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
      },
    ] as never);
    vi.mocked(previewRollback).mockResolvedValue({
      action_event_id: "ae-1",
      provider: "todoist",
      operation: "update",
      reversible: true,
      rollback_strategy: "todoist_update_restore_fields",
    } as never);
    vi.mocked(executeRollback).mockResolvedValue({
      action_event_id: "ae-1",
      status: "executed",
      message: "Rollback выполнен.",
    } as never);
    vi.spyOn(window, "confirm").mockReturnValue(false);
  });

  it("рендерит список событий", async () => {
    render(<ActivityPage />);

    expect(await screen.findByLabelText("Лента активности Asya")).toBeInTheDocument();
    expect(screen.getAllByText("Создан факт памяти").length).toBeGreaterThan(0);
    expect(screen.getByText("Создан факт памяти: lang")).toBeInTheDocument();
  });

  it("применяет фильтры", async () => {
    render(<ActivityPage />);
    await screen.findByText("Создан факт памяти: lang");

    fireEvent.change(screen.getByLabelText("Тип события"), { target: { value: "memory_snapshot_created" } });
    fireEvent.click(screen.getByRole("button", { name: "Применить фильтры" }));

    await waitFor(() => {
      expect(listActivityLog).toHaveBeenLastCalledWith(
        expect.objectContaining({ event_type: "memory_snapshot_created" })
      );
    });
  });

  it("показывает кнопку отката и preview", async () => {
    render(<ActivityPage />);
    await screen.findByText("Создан факт памяти: lang");

    fireEvent.click(screen.getByRole("button", { name: "Откатить" }));

    await waitFor(() => {
      expect(previewRollback).toHaveBeenCalledWith("ae-1");
    });
    expect(screen.getByText(/Preview:/)).toBeInTheDocument();
  });
});

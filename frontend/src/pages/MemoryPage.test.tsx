import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createMemorySnapshot,
  createMemoryFact,
  createMemoryRule,
  getMemorySnapshotSummary,
  getPersonalityProfile,
  listMemorySnapshots,
  listMemoryEpisodes,
  listMemoryFacts,
  listMemoryRules,
  rollbackMemorySnapshot,
  updateMemoryFactStatus,
  updateMemoryRule,
  updatePersonalityProfile,
} from "../api/client";
import MemoryPage from "./MemoryPage";

vi.mock("../api/client", () => ({
  listMemoryFacts: vi.fn(),
  listMemoryRules: vi.fn(),
  listMemoryEpisodes: vi.fn(),
  getPersonalityProfile: vi.fn(),
  createMemoryFact: vi.fn(),
  updateMemoryFact: vi.fn(),
  updateMemoryFactStatus: vi.fn(),
  updateMemoryRule: vi.fn(),
  createMemorySnapshot: vi.fn(),
  listMemorySnapshots: vi.fn(),
  getMemorySnapshotSummary: vi.fn(),
  rollbackMemorySnapshot: vi.fn(),
  forbidMemoryFact: vi.fn(),
  createMemoryRule: vi.fn(),
  disableMemoryRule: vi.fn(),
  updatePersonalityProfile: vi.fn(),
}));

describe("MemoryPage", () => {
  beforeEach(() => {
    vi.mocked(listMemoryFacts).mockResolvedValue([
      {
        id: "fact-1",
        key: "preferred_language",
        value: "ru",
        status: "confirmed",
        source: "user",
        created_at: "2026-05-02T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
      },
    ] as never);
    vi.mocked(listMemoryRules).mockResolvedValue([
      {
        id: "rule-1",
        title: "Кратко",
        instruction: "Отвечай кратко",
        scope: "user",
        strictness: "normal",
        source: "user",
        status: "active",
        created_at: "2026-05-02T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
      },
    ] as never);
    vi.mocked(listMemoryEpisodes).mockResolvedValue([
      {
        id: "ep-1",
        chat_id: "chat-1",
        summary: "Обсудили план проекта",
        status: "inferred",
        source: "assistant_inferred",
        created_at: "2026-05-02T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
      },
    ] as never);
    vi.mocked(listMemorySnapshots).mockResolvedValue([
      {
        id: "snap-1",
        label: "Manual snapshot",
        created_at: "2026-05-02T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
      },
    ] as never);
    vi.mocked(getPersonalityProfile).mockResolvedValue({
      id: "persona-1",
      scope: "base",
      name: "Asya",
      tone: "balanced",
      style_notes: "",
      humor_level: 1,
      initiative_level: 1,
      can_gently_disagree: true,
      address_user_by_name: true,
      is_active: true,
      created_at: "2026-05-02T00:00:00Z",
      updated_at: "2026-05-02T00:00:00Z",
    } as never);
    vi.mocked(createMemoryFact).mockResolvedValue({} as never);
    vi.mocked(createMemoryRule).mockResolvedValue({} as never);
    vi.mocked(createMemorySnapshot).mockResolvedValue({} as never);
    vi.mocked(rollbackMemorySnapshot).mockResolvedValue({} as never);
    vi.mocked(getMemorySnapshotSummary).mockResolvedValue({
      id: "snap-1",
      label: "Manual snapshot",
      created_at: "2026-05-02T00:00:00Z",
      updated_at: "2026-05-02T00:00:00Z",
      facts_count: 1,
      rules_count: 1,
      episodes_count: 1,
      personality_profiles_count: 1,
      space_settings_count: 1,
    } as never);
    vi.mocked(updateMemoryFactStatus).mockResolvedValue({} as never);
    vi.mocked(updateMemoryRule).mockResolvedValue({} as never);
    vi.mocked(updatePersonalityProfile).mockImplementation(async (payload) => payload as never);
  });

  it("рендерит блоки памяти и личности", async () => {
    render(<MemoryPage />);

    expect(await screen.findByLabelText("Память Asya")).toBeInTheDocument();
    expect(await screen.findByText("Личность Asya")).toBeInTheDocument();
    expect(screen.getByText("Факты профиля")).toBeInTheDocument();
    expect(screen.getByText("Правила поведения")).toBeInTheDocument();
    expect(screen.getByText("Эпизоды памяти")).toBeInTheDocument();
    expect(screen.getByText("Snapshots памяти")).toBeInTheDocument();
    expect(screen.getByText("preferred_language")).toBeInTheDocument();
    expect(screen.getByText("Отвечай кратко")).toBeInTheDocument();
    expect(screen.queryByText("fact-1")).not.toBeInTheDocument();
  });

  it("создаёт факт вручную", async () => {
    render(<MemoryPage />);
    await screen.findByText("Факты профиля");

    fireEvent.change(screen.getByLabelText("Ключ"), { target: { value: "timezone" } });
    fireEvent.change(screen.getByLabelText("Значение"), { target: { value: "Europe/Moscow" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать факт" }));

    await waitFor(() => {
      expect(createMemoryFact).toHaveBeenCalled();
    });
  });

  it("подтверждает факт", async () => {
    render(<MemoryPage />);
    await screen.findByText("preferred_language");

    fireEvent.click(screen.getByRole("button", { name: "Подтвердить" }));

    await waitFor(() => {
      expect(updateMemoryFactStatus).toHaveBeenCalledWith("fact-1", { status: "confirmed" });
    });
  });

  it("сохраняет personality профиль", async () => {
    render(<MemoryPage />);
    await screen.findByLabelText("Тон");

    fireEvent.change(screen.getByLabelText("Тон"), { target: { value: "calm" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить личность" }));

    await waitFor(() => {
      expect(updatePersonalityProfile).toHaveBeenCalledWith(
        expect.objectContaining({ tone: "calm" })
      );
    });
  });

  it("создаёт snapshot вручную", async () => {
    render(<MemoryPage />);
    await screen.findByText("Snapshots памяти");
    fireEvent.click(screen.getByRole("button", { name: "Создать snapshot" }));
    await waitFor(() => {
      expect(createMemorySnapshot).toHaveBeenCalled();
    });
  });

  it("редактирует правило поведения", async () => {
    const promptSpy = vi.spyOn(window, "prompt").mockReturnValue("Отвечай максимально кратко");
    render(<MemoryPage />);
    await screen.findByText("Отвечай кратко");

    fireEvent.click(screen.getAllByRole("button", { name: "Редактировать" })[1]);

    await waitFor(() => {
      expect(updateMemoryRule).toHaveBeenCalledWith(
        "rule-1",
        expect.objectContaining({ instruction: "Отвечай максимально кратко" })
      );
    });

    promptSpy.mockRestore();
  });
});

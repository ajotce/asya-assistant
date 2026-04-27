import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { THEME_STORAGE_KEY, useTheme } from "./useTheme";

function setupMatchMedia(prefersDark: boolean) {
  const listeners = new Set<(event: MediaQueryListEvent) => void>();
  const mediaList = {
    matches: prefersDark,
    media: "(prefers-color-scheme: dark)",
    onchange: null,
    addEventListener: vi.fn((_: string, cb: (event: MediaQueryListEvent) => void) => {
      listeners.add(cb);
    }),
    removeEventListener: vi.fn((_: string, cb: (event: MediaQueryListEvent) => void) => {
      listeners.delete(cb);
    }),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  } as unknown as MediaQueryList;

  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation(() => mediaList)
  );
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: window.matchMedia,
  });

  return {
    fireSystemChange(matches: boolean) {
      (mediaList as unknown as { matches: boolean }).matches = matches;
      listeners.forEach((cb) => cb({ matches } as MediaQueryListEvent));
    },
  };
}

describe("useTheme", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("ставит data-theme=dark и пишет в localStorage при выборе тёмной темы", () => {
    setupMatchMedia(false);
    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.setPreference("dark");
    });

    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(result.current.resolved).toBe("dark");
  });

  it("в режиме system резолвит тему через prefers-color-scheme и реагирует на изменения", () => {
    const { fireSystemChange } = setupMatchMedia(false);
    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.setPreference("system");
    });

    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(result.current.resolved).toBe("light");

    act(() => {
      fireSystemChange(true);
    });

    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(result.current.resolved).toBe("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("system");
  });
});

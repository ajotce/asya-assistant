import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import WakeWordListener from "./WakeWordListener";

describe("WakeWordListener", () => {
  it("останавливает слушание при hidden tab", () => {
    const onStopped = vi.fn();
    const stop = vi.fn();
    const start = vi.fn();

    class FakeRecognition {
      lang = "ru-RU";
      continuous = true;
      interimResults = true;
      onresult: ((event: WakeWordRecognitionEvent) => void) | null = null;
      onerror: (() => void) | null = null;
      onend: (() => void) | null = null;
      start = start;
      stop = stop;
    }

    Object.defineProperty(window, "webkitSpeechRecognition", {
      value: FakeRecognition,
      configurable: true,
    });
    Object.defineProperty(document, "visibilityState", {
      value: "visible",
      configurable: true,
    });

    render(
      <WakeWordListener
        enabled={true}
        phrase="ася"
        sensitivity={0.5}
        busy={false}
        onTranscript={async () => {}}
        onStopped={onStopped}
      />
    );

    Object.defineProperty(document, "visibilityState", {
      value: "hidden",
      configurable: true,
    });
    document.dispatchEvent(new Event("visibilitychange"));

    expect(stop).toHaveBeenCalled();
    expect(onStopped).toHaveBeenCalled();
  });
});

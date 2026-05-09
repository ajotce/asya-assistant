import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { sendVoiceListen } from "../api/client";

type WakeWordState = "idle" | "watching" | "listening" | "processing" | "error";

interface WakeWordListenerProps {
  enabled: boolean;
  phrase: string;
  sensitivity: number;
  busy: boolean;
  onTranscript: (text: string) => Promise<void>;
  onStateChange?: (state: WakeWordState) => void;
  onStopped?: () => void;
}

declare global {
  interface WakeWordRecognitionEngine {
    lang: string;
    continuous: boolean;
    interimResults: boolean;
    onresult: ((event: WakeWordRecognitionEvent) => void) | null;
    onerror: (() => void) | null;
    onend: (() => void) | null;
    start: () => void;
    stop: () => void;
  }
  interface WakeWordRecognitionResult {
    0?: { transcript?: string };
  }
  interface WakeWordRecognitionEvent {
    resultIndex: number;
    results: WakeWordRecognitionResult[];
  }
  interface Window {
    SpeechRecognition?: new () => WakeWordRecognitionEngine;
    webkitSpeechRecognition?: new () => WakeWordRecognitionEngine;
  }
}

function normalize(text: string): string {
  return text.trim().toLowerCase();
}

export default function WakeWordListener({
  enabled,
  phrase,
  sensitivity,
  busy,
  onTranscript,
  onStateChange,
  onStopped,
}: WakeWordListenerProps) {
  const [state, setState] = useState<WakeWordState>("idle");
  const recognitionRef = useRef<WakeWordRecognitionEngine | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const runningRef = useRef(false);
  const phraseNorm = useMemo(() => normalize(phrase), [phrase]);

  const setAndNotify = useCallback((next: WakeWordState) => {
    setState(next);
    onStateChange?.(next);
  }, [onStateChange]);

  const stopCommandCapture = useCallback(async (): Promise<void> => {
    if (recorderRef.current && recorderRef.current.state === "recording") {
      recorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }, []);

  const stopWakeWord = useCallback(() => {
    runningRef.current = false;
    recognitionRef.current?.stop();
    onStopped?.();
  }, [onStopped]);

  const recordUntilSilence = useCallback(async (): Promise<Blob | null> => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
    recorderRef.current = recorder;

    const chunks: Blob[] = [];
    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 1024;
    source.connect(analyser);
    const data = new Uint8Array(analyser.fftSize);

    const threshold = Math.max(0.01, (1 - sensitivity) * 0.04);
    let speechDetected = false;
    let silenceMs = 0;

    return await new Promise((resolve) => {
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
        }
      };
      recorder.onstop = async () => {
        await audioContext.close();
        const blob = new Blob(chunks, { type: "audio/webm" });
        resolve(blob.size > 0 ? blob : null);
      };

      recorder.start(250);
      const intervalId = window.setInterval(() => {
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i += 1) {
          const centered = (data[i] - 128) / 128;
          sum += centered * centered;
        }
        const rms = Math.sqrt(sum / data.length);
        if (rms > threshold) {
          speechDetected = true;
          silenceMs = 0;
          return;
        }
        if (speechDetected) {
          silenceMs += 100;
          if (silenceMs >= 1200) {
            window.clearInterval(intervalId);
            recorder.stop();
          }
        }
      }, 100);

      window.setTimeout(() => {
        window.clearInterval(intervalId);
        if (recorder.state === "recording") {
          recorder.stop();
        }
      }, 15000);
    });
  }, [sensitivity]);

  useEffect(() => {
    const SpeechRecognitionCtor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!enabled || busy || document.visibilityState !== "visible" || !SpeechRecognitionCtor) {
      stopWakeWord();
      void stopCommandCapture();
      setAndNotify("idle");
      return;
    }

    const recognition = new SpeechRecognitionCtor();
    recognition.lang = "ru-RU";
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event: WakeWordRecognitionEvent) => {
      if (!runningRef.current || busy) {
        return;
      }
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        transcript += event.results[i][0]?.transcript ?? "";
      }
      if (!normalize(transcript).includes(phraseNorm)) {
        return;
      }

      runningRef.current = false;
      recognition.stop();
      setAndNotify("listening");
      void (async () => {
        try {
          const blob = await recordUntilSilence();
          if (!blob) {
            setAndNotify("watching");
            return;
          }
          setAndNotify("processing");
          const stt = await sendVoiceListen(blob);
          const text = stt.text.trim();
          if (text) {
            await onTranscript(text);
          }
          setAndNotify("watching");
        } catch {
          setAndNotify("error");
        } finally {
          await stopCommandCapture();
          runningRef.current = true;
          recognition.start();
        }
      })();
    };

    recognition.onerror = () => {
      setAndNotify("error");
    };
    recognition.onend = () => {
      if (runningRef.current && document.visibilityState === "visible" && enabled && !busy) {
        recognition.start();
      }
    };

    recognitionRef.current = recognition;
    runningRef.current = true;
    setAndNotify("watching");
    recognition.start();

    const onVisibility = () => {
      if (document.visibilityState === "hidden") {
        stopWakeWord();
        void stopCommandCapture();
        setAndNotify("idle");
      } else if (enabled && !busy) {
        runningRef.current = true;
        recognition.start();
        setAndNotify("watching");
      }
    };

    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      stopWakeWord();
      void stopCommandCapture();
      setAndNotify("idle");
    };
  }, [
    enabled,
    busy,
    phraseNorm,
    onTranscript,
    recordUntilSilence,
    setAndNotify,
    stopCommandCapture,
    stopWakeWord,
  ]);

  return <span className="status-text">Wake-word: {state === "listening" ? "Слушаю" : state}</span>;
}

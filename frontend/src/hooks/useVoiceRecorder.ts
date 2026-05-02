import { useCallback, useEffect, useRef, useState } from "react";

interface VoiceRecorderState {
  isSupported: boolean;
  isRecording: boolean;
  error: string | null;
}

interface UseVoiceRecorderReturn extends VoiceRecorderState {
  start: () => Promise<void>;
  stop: () => Promise<Blob | null>;
}

export function useVoiceRecorder(): UseVoiceRecorderReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const isSupported =
    typeof window !== "undefined" &&
    Boolean(navigator?.mediaDevices?.getUserMedia) &&
    Boolean(window.MediaRecorder);

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const start = useCallback(async () => {
    setError(null);
    chunksRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorder.onerror = () => {
        setError("Ошибка записи микрофона.");
        setIsRecording(false);
      };
      recorder.start();
      setIsRecording(true);
    } catch (startError) {
      const message =
        startError instanceof Error
          ? startError.message
          : "Не удалось получить доступ к микрофону.";
      setError(message);
      setIsRecording(false);
    }
  }, []);

  const stop = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state !== "recording") {
        setIsRecording(false);
        resolve(null);
        return;
      }
      recorder.onstop = () => {
        setIsRecording(false);
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
        }
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        resolve(blob.size > 0 ? blob : null);
      };
      recorder.stop();
    });
  }, []);

  return { isSupported, isRecording, error, start, stop };
}

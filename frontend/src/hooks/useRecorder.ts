/**
 * useRecorder — thin wrapper around MediaRecorder with graceful fallback.
 *
 * jsdom/older browsers have no MediaRecorder: `supported` is false and the UI
 * shows a clear message while the deterministic touch path stays available
 * (spec §60 — voice must never be the single point of failure).
 */
import { useCallback, useRef, useState } from "react";

export interface RecorderResult {
  /** True if the browser can record audio at all. */
  supported: boolean;
  recording: boolean;
  error: string | null;
  start(): Promise<void>;
  stop(): Promise<Blob | null>;
}

export function useRecorder(): RecorderResult {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const supported =
    typeof window !== "undefined" &&
    typeof MediaRecorder !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia;

  const start = useCallback(async () => {
    if (!supported) {
      setError("unsupported");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
      setError(null);
    } catch {
      setError("permission");
    }
  }, [supported]);

  const stop = useCallback(async () => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === "inactive") {
      setRecording(false);
      return null;
    }
    const stopped = new Promise<void>((resolve) => {
      recorder.addEventListener("stop", () => resolve(), { once: true });
    });
    recorder.stop();
    await stopped;
    setRecording(false);
    const type = recorder.mimeType || "audio/webm";
    return new Blob(chunksRef.current, { type });
  }, []);

  return { supported, recording, error, start, stop };
}

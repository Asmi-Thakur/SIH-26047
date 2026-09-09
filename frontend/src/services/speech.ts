/**
 * Speech service: uploads a recorded blob to the backend SpeechProvider
 * (mock by default) and returns the transcript. Kept separate from api.ts so
 * media calls never share the JSON-only request helper.
 */
import { API_BASE_URL } from "./api";

export interface SpeechTranscript {
  transcript: string;
  language: string;
  provider: string;
  /** True when the transcript is simulated (mock ASR), not real STT. */
  mocked: boolean;
}

export class SpeechError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SpeechError";
  }
}

export async function transcribeAudio(
  blob: Blob,
  language: string,
): Promise<SpeechTranscript> {
  const form = new FormData();
  form.append("language", language);
  form.append("audio", blob, "recording.webm");

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/speech/transcribe`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new SpeechError("Cannot reach the speech service.");
  }

  if (!response.ok) {
    throw new SpeechError(`Speech request failed with status ${response.status}`);
  }
  return (await response.json()) as SpeechTranscript;
}

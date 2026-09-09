import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { transcribeAudio } from "./speech";

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("transcribeAudio", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    globalThis.fetch = fetchMock;
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("uploads the blob as multipart to /api/speech/transcribe", async () => {
    fetchMock.mockResolvedValueOnce(
      json({
        transcript: "sample",
        language: "en",
        provider: "mock",
        mocked: true,
      }),
    );

    const blob = new Blob(["audio-bytes"], { type: "audio/webm" });
    const result = await transcribeAudio(blob, "hi");

    expect(result.transcript).toBe("sample");
    expect(result.mocked).toBe(true);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/speech/transcribe");
    expect(init.body).toBeInstanceOf(FormData);
    const form = init.body as FormData;
    expect(form.get("language")).toBe("hi");
    expect(form.get("audio")).toBeInstanceOf(Blob);
  });

  it("throws SpeechError on network failure", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("network down"));
    await expect(transcribeAudio(new Blob([]), "en")).rejects.toThrow(
      "Cannot reach the speech service.",
    );
  });
});

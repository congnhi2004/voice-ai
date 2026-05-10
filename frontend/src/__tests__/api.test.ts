import { describe, expect, it } from "vitest";
import { normalizeBaseUrl, resolveArtifactUrl, resolveAudioUrl } from "../api";

describe("api helpers", () => {
  it("normalizes an empty or trailing-slash base URL", () => {
    expect(normalizeBaseUrl("")).toBe("http://localhost:8080");
    expect(normalizeBaseUrl(" http://localhost:8080/// ")).toBe("http://localhost:8080");
  });

  it("resolves absolute and relative audio URLs", () => {
    expect(resolveAudioUrl("http://localhost:8080", "/audio/sample.mp3")).toBe("http://localhost:8080/audio/sample.mp3");
    expect(resolveAudioUrl("http://localhost:8080", "https://cdn.example.com/sample.mp3")).toBe("https://cdn.example.com/sample.mp3");
  });

  it("falls back from audio_path to the local audio route", () => {
    expect(resolveAudioUrl("http://localhost:8080/", undefined, "data/audio/tts_123.mp3")).toBe(
      "http://localhost:8080/audio/tts_123.mp3"
    );
  });

  it("resolves video workflow artifacts from paths", () => {
    expect(resolveArtifactUrl("http://localhost:8080", undefined, "data/videos/final.mp4")).toBe(
      "http://localhost:8080/artifacts/final.mp4"
    );
    expect(resolveArtifactUrl("http://localhost:8080", undefined, "data/audio/vi.mp3", "audio")).toBe(
      "http://localhost:8080/audio/vi.mp3"
    );
  });
});

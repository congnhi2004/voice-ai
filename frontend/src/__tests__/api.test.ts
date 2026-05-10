import { afterEach, describe, expect, it, vi } from "vitest";
import { normalizeBaseUrl, resolveArtifactUrl, resolveAudioUrl, VoiceAiClient } from "../api";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

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

  it("uses the final checkout-session billing route", async () => {
    vi.stubGlobal("window", { location: { origin: "http://localhost:5173", pathname: "/" } });
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ url: "/checkout-test" })));
    vi.stubGlobal("fetch", fetchMock);

    await new VoiceAiClient({ baseUrl: "http://localhost:8080", sessionToken: "token" }).createCheckoutSession("starter");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8080/v1/billing/checkout-session",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("uses the final customer-portal billing route", async () => {
    vi.stubGlobal("window", { location: { origin: "http://localhost:5173", pathname: "/" } });
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ url: "/portal-test" })));
    vi.stubGlobal("fetch", fetchMock);

    await new VoiceAiClient({ baseUrl: "http://localhost:8080", sessionToken: "token" }).createBillingPortalSession();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8080/v1/billing/customer-portal",
      expect.objectContaining({ method: "POST" })
    );
  });
});

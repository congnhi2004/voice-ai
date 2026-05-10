import { expect, test } from "@playwright/test";

const voiceResponse = {
  provider: "fallback",
  voices: [
    {
      name: "en-US-Standard-C",
      language_codes: ["en-US"],
      ssml_gender: "FEMALE",
      natural_sample_rate_hz: 24000,
      supported_encodings: ["MP3", "LINEAR16", "OGG_OPUS"]
    },
    {
      name: "vi-VN-Standard-A",
      language_codes: ["vi-VN"],
      ssml_gender: "FEMALE",
      natural_sample_rate_hz: 24000,
      supported_encodings: ["MP3", "LINEAR16"]
    }
  ]
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.clear());

  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/readyz/, async (route) => {
    await route.fulfill({
      json: {
        status: "ready",
        provider: { name: "fallback", ready: true },
        storage: { mode: "local", ready: true },
        mlflow: { configured: false, ready: false }
      }
    });
  });

  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/voices/, async (route) => {
    await route.fulfill({ json: voiceResponse });
  });
});

test("TTS flow renders output and captures desktop evidence", async ({ page }, testInfo) => {
  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/synthesize/, async (route) => {
    await route.fulfill({
      json: {
        job_id: "tts_e2e_001",
        status: "succeeded",
        audio_url: "http://localhost:8080/audio/tts_e2e_001.mp3",
        duration_ms: 1180,
        latency_ms: 642,
        provider: { name: "fallback", fallback: true },
        audio: { encoding: "MP3", bytes: 18342, sample_rate_hz: 24000, checksum_sha256: "abc123" },
        observability: { request_id: "req_e2e_001" }
      }
    });
  });

  await page.goto("/");
  await expect(page.getByTestId("prototype-studio")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Text to real voice studio" })).toBeVisible();
  await page.getByLabel("Script input").fill("Xin chao tu Voice AI.");
  await page.getByTestId("generate-tts-preview").click();

  await expect(page.getByTestId("tts-job-id")).toHaveText("tts_e2e_001");
  await expect(page.locator("audio")).toHaveAttribute("controls", "");
  await expect(page.locator("audio")).toHaveAttribute("src", "http://localhost:8080/audio/tts_e2e_001.mp3");
  await expect(page.getByRole("link", { name: "Download audio" })).toBeVisible();

  const screenshotPath = `../docs/subagents/frontend-tts-${testInfo.project.name}.png`;
  await page.screenshot({ path: screenshotPath, fullPage: testInfo.project.name === "desktop" });
  await testInfo.attach(`tts-${testInfo.project.name}`, { path: screenshotPath, contentType: "image/png" });
});

test("video localization flow renders mocked progress, previews, and mobile evidence", async ({ page }, testInfo) => {
  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/video-localization\/jobs$/, async (route) => {
    await route.fulfill({
      json: {
        job_id: "vid_e2e_001",
        status: "succeeded",
        progress: 100,
        stage: "Vietnamese review ready",
        source_language: "en",
        target_language: "vi",
        script: {
          vietnamese_text: "Day la ban dich tieng Viet.",
          srt: "1\\n00:00:00,000 --> 00:00:02,000\\nDay la ban dich tieng Viet."
        },
        artifacts: {
          transcript_url: "/artifacts/vid_e2e_001.txt",
          srt_url: "/artifacts/vid_e2e_001.srt",
          audio_url: "/audio/vid_e2e_001.mp3",
          video_url: "/artifacts/vid_e2e_001.mp4"
        },
        observability: { request_id: "req_vid_e2e_001" }
      }
    });
  });

  await page.goto("/");
  await expect(page.getByTestId("prototype-studio")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Text to real voice studio" })).toBeVisible();
  await page.getByTestId("workflow-video-localization-tab").click();
  await expect(page.getByRole("heading", { name: "Video to Vietnamese studio" })).toBeVisible();
  await page.setInputFiles("#video-file", {
    name: "sample.mp4",
    mimeType: "video/mp4",
    buffer: Buffer.from("fake mp4")
  });
  await page.getByTestId("start-video-localization").click();

  await expect(page.getByTestId("video-job-id")).toHaveText("vid_e2e_001");
  await expect(page.getByLabel("Vietnamese script preview")).toContainText("Day la ban dich tieng Viet.");
  await expect(page.getByRole("link", { name: "Final MP4" })).toBeVisible();

  const screenshotPath = `../docs/subagents/frontend-video-${testInfo.project.name}.png`;
  await page.screenshot({ path: screenshotPath, fullPage: false });
  await testInfo.attach(`video-${testInfo.project.name}`, { path: screenshotPath, contentType: "image/png" });
});

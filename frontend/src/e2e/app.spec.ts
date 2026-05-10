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

  const screenshotPath = `../docs/subagents/evidence/images/frontend-premium-tts-${testInfo.project.name}.png`;
  await page.screenshot({ path: screenshotPath, fullPage: testInfo.project.name === "desktop" });
  await testInfo.attach(`tts-${testInfo.project.name}`, { path: screenshotPath, contentType: "image/png" });
});

test("video localization flow renders mocked progress, previews, and mobile evidence", async ({ page }, testInfo) => {
  const backendScript = "Ban dich tu backend acceptance 47.2.";
  const backendSubtitle = "1\\n00:00:00,000 --> 00:00:02,400\\nBan dich tu backend acceptance 47.2.";

  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/video-localization\/jobs$/, async (route) => {
    await route.fulfill({
      json: {
        job_id: "vid_e2e_001",
        status: "succeeded",
        progress: 100,
        stage: "rendering complete",
        source_language: "en",
        target_language: "vi",
        provider: { name: "local", fallback: true, model: "deterministic-video-localization-demo" },
        input_filename: "sample.mp4",
        segments: [
          {
            index: 1,
            start_ms: 0,
            end_ms: 2400,
            source_text: "Backend source text.",
            translated_text: backendScript
          }
        ],
        script: {
          srt: backendSubtitle,
          editable: false
        },
        artifacts: [
          {
            type: "vietnamese_transcript",
            format: "txt",
            download_url: "/v1/video-localization/jobs/vid_e2e_001/artifacts/vietnamese_transcript/download"
          },
          {
            type: "subtitles_srt",
            format: "srt",
            download_url: "/v1/video-localization/jobs/vid_e2e_001/artifacts/subtitles_srt/download"
          },
          {
            type: "subtitles_vtt",
            format: "vtt",
            download_url: "/v1/video-localization/jobs/vid_e2e_001/artifacts/subtitles_vtt/download"
          },
          {
            type: "vietnamese_audio",
            format: "mp3",
            download_url: "/v1/video-localization/jobs/vid_e2e_001/artifacts/vietnamese_audio/download"
          },
          {
            type: "localized_video",
            format: "mp4",
            download_url: "/v1/video-localization/jobs/vid_e2e_001/artifacts/localized_video/download"
          }
        ],
        observability: { request_id: "req_vid_e2e_001", mlflow_run_id: "run_vid_e2e_001" }
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
  await expect(page.getByLabel("Vietnamese script preview")).toContainText(backendScript);
  await expect(page.getByLabel("Vietnamese script preview")).toHaveAttribute("readonly", "");
  await expect(page.getByLabel("Vietnamese SRT preview")).toContainText("00:00:00,000 --> 00:00:02,400");
  await expect(page.getByRole("link", { name: /Transcript/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /VTT/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Final MP4/ })).toBeVisible();
  await expect(page.locator("video")).toHaveAttribute(
    "src",
    "http://localhost:8080/v1/video-localization/jobs/vid_e2e_001/artifacts/localized_video/download"
  );

  const screenshotPath = `../docs/subagents/evidence/images/frontend-premium-video-${testInfo.project.name}.png`;
  await page.screenshot({ path: screenshotPath, fullPage: false });
  await testInfo.attach(`video-${testInfo.project.name}`, { path: screenshotPath, contentType: "image/png" });
});

test("Video localization tab exposes the upload workflow", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Text to real voice studio" })).toBeVisible();

  await page.getByRole("tab", { name: "Video localization", exact: true }).click();

  await expect(page.getByRole("heading", { name: "Video to Vietnamese studio" })).toBeVisible();
  await expect(page.locator('input[type="file"]')).toBeVisible();
  await expect(page.getByTestId("video-file-input")).toHaveAttribute("accept", /video/);
  await expect(page.getByLabel("Source language")).toBeVisible();
  await expect(page.getByLabel("Target")).toHaveValue("Vietnamese script, SRT, dub, MP4");
  await expect(page.getByLabel("Vietnamese voice")).toBeVisible();
  await expect(page.getByTestId("start-video-localization")).toBeVisible();
});

test("video upload validation blocks unsupported files before hitting backend", async ({ page }) => {
  let backendCalled = false;
  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/video-localization\/jobs$/, async (route) => {
    backendCalled = true;
    await route.fulfill({ status: 500, json: { error: { message: "Should not be called" } } });
  });

  await page.goto("/");
  await page.getByTestId("workflow-video-localization-tab").click();
  await page.setInputFiles("#video-file", {
    name: "notes.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("not a video")
  });

  await expect(page.getByRole("alert")).toContainText("Select an MP4, MOV, M4V, or WebM video");
  await page.getByTestId("start-video-localization").click();
  await expect(page.getByRole("alert")).toContainText("Upload a Chinese or English video");
  expect(backendCalled).toBe(false);
});

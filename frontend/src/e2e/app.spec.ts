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

  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/product\/capabilities/, async (route) => {
    await route.fulfill({
      json: {
        service: "voice-ai",
        environment: "local",
        mode: "demo",
        tts: {
          available: true,
          providers: ["openai"],
          active_provider: "openai",
          encodings: ["MP3"],
          local_fallback: false,
          max_input_chars: 4096
        },
        video_localization: {
          available: true,
          source_languages: ["en-US", "zh-CN"],
          target_languages: ["vi"],
          demo_mode: true,
          max_upload_bytes: 25 * 1024 * 1024
        },
        auth: { available: true, mode: "local-demo", production_identity: false },
        billing: { available: false, mode: "pricing-copy-only", production_billing: false }
      }
    });
  });

  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/product\/plans/, async (route) => {
    await route.fulfill({
      json: {
        plans: [
          {
            id: "demo-free",
            name: "Demo Free",
            monthly_price_usd: 0,
            included_minutes: 20,
            features: [{ key: "tts", label: "Short TTS previews" }],
            demo_only: true
          },
          {
            id: "starter-placeholder",
            name: "Starter Placeholder",
            monthly_price_usd: 49,
            included_minutes: 500,
            overage_price_usd_per_minute: 0.18,
            features: [{ key: "api", label: "API access" }],
            recommended: true,
            demo_only: true
          }
        ],
        billing: { production_billing: false, demo_only: true, mode: "pricing-copy-only" }
      }
    });
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
  await expect(page.locator("#character-count")).toHaveText("158 / 4,096 characters");
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
            kind: "source_video",
            url: "/v1/video-localization/jobs/vid_e2e_001/artifacts/source.mp4"
          },
          {
            kind: "source_audio",
            url: "/v1/video-localization/jobs/vid_e2e_001/artifacts/source-audio.mp3"
          },
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
            kind: "voiceover_audio",
            format: "mp3",
            download_url: "/v1/video-localization/jobs/vid_e2e_001/artifacts/vietnamese_audio/download"
          },
          {
            kind: "localized_video",
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
  await page.getByRole("tab", { name: "Video localization", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Video to Vietnamese studio" })).toBeVisible();
  await page.getByLabel("Source video", { exact: true }).setInputFiles({
    name: "sample.mp4",
    mimeType: "video/mp4",
    buffer: Buffer.from("fake mp4")
  });
  await page.getByRole("button", { name: "Start Vietnamese localization", exact: true }).click();

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
  await expect(page.getByRole("button", { name: "Open video workflow", exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Video localization", exact: true }).click();

  await expect(page.getByRole("heading", { name: "Video to Vietnamese studio" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Video localization", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByLabel("Source video", { exact: true })).toBeVisible();
  await expect(page.getByTestId("video-file-input")).toHaveAttribute("accept", /video/);
  await expect(page.locator("#video-file-help")).toContainText("up to 25 MB");
  await expect(page.getByLabel("Source language")).toBeVisible();
  await expect(page.getByLabel("Target")).toHaveValue("Vietnamese script, SRT, dub, MP4");
  await expect(page.getByLabel("Vietnamese voice")).toBeVisible();
  await expect(page.getByRole("button", { name: "Start Vietnamese localization", exact: true })).toBeVisible();
});

test("video upload validation blocks unsupported files before hitting backend", async ({ page }) => {
  let backendCalled = false;
  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/video-localization\/jobs$/, async (route) => {
    backendCalled = true;
    await route.fulfill({ status: 500, json: { error: { message: "Should not be called" } } });
  });

  await page.goto("/");
  await page.getByRole("tab", { name: "Video localization", exact: true }).click();
  await page.getByLabel("Source video", { exact: true }).setInputFiles({
    name: "notes.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("not a video")
  });

  await expect(page.getByRole("alert")).toContainText("Select an MP4, MOV, M4V, or WebM video");
  await page.getByRole("button", { name: "Start Vietnamese localization", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Upload a Chinese or English video");
  expect(backendCalled).toBe(false);
});

test("auth and billing panel expose session state with billing disabled", async ({ page }) => {
  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/auth\/register/, async (route) => {
    await route.fulfill({
      json: {
        access_token: "demo_token_123",
        user: { id: "user_123", email: "creator@example.com", plan_id: "demo-free", subscription_status: "demo" }
      }
    });
  });
  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/auth\/me/, async (route) => {
    await route.fulfill({
      json: { user: { id: "user_123", email: "creator@example.com", plan_id: "demo-free", subscription_status: "demo" } }
    });
  });
  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/billing\/subscription/, async (route) => {
    await route.fulfill({ status: 404, json: { error: { message: "Billing not configured", code: "billing_not_configured" } } });
  });

  await page.goto("/");
  const navSignupButton = page.locator("button#signup-button");
  await expect(navSignupButton).toHaveAccessibleName("Sign up");
  await navSignupButton.click();
  await page.getByLabel("Email").fill("creator@example.com");
  await page.getByLabel("Password").fill("correct-horse");
  await page.getByRole("button", { name: "Create account" }).click();

  const accountBillingPanel = page.getByLabel("Account and billing");
  await expect(accountBillingPanel.getByText("creator@example.com")).toBeVisible();
  await expect(accountBillingPanel.getByText("local-demo")).toBeVisible();
  await expect(accountBillingPanel.getByRole("button", { name: "Manage billing" })).toBeDisabled();
  const starterPricingCard = page.locator(".pricing-card", { hasText: "Starter Placeholder" });
  await expect(starterPricingCard.getByText("Action unavailable")).toBeVisible();
  await expect(starterPricingCard.getByRole("button", { name: "Checkout disabled" })).toBeDisabled();
});

test("pricing selection calls checkout when billing capability is enabled", async ({ page }) => {
  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/product\/capabilities/, async (route) => {
    await route.fulfill({
      json: {
        service: "voice-ai",
        mode: "production",
        auth: { available: true, mode: "session", production_identity: true },
        billing: { available: true, mode: "stripe", production_billing: true, checkout_available: true, portal_available: true, stripe_configured: true }
      }
    });
  });
  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/auth\/register/, async (route) => {
    await route.fulfill({ json: { access_token: "prod_token_123", user: { email: "buyer@example.com" } } });
  });
  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/auth\/me/, async (route) => {
    await route.fulfill({ json: { user: { email: "buyer@example.com", plan_id: "starter-placeholder", subscription_status: "trialing" } } });
  });
  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/billing\/subscription/, async (route) => {
    await route.fulfill({ json: { status: "trialing", plan_id: "starter-placeholder", entitlement_status: "active" } });
  });
  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8080\/v1\/billing\/checkout-session/, async (route) => {
    const body = route.request().postDataJSON() as { plan_id?: string };
    expect(body.plan_id).toBe("starter-placeholder");
    await route.fulfill({ json: { url: "/checkout-test?session_id=cs_test_123" } });
  });

  await page.goto("/");
  const navSignupButton = page.locator("button#signup-button");
  await expect(navSignupButton).toHaveAccessibleName("Sign up");
  await navSignupButton.click();
  await page.getByLabel("Email").fill("buyer@example.com");
  await page.getByLabel("Password").fill("correct-horse");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByLabel("Account and billing").getByText("Stripe billing ready")).toBeVisible();
  await page.locator(".pricing-card", { hasText: "Starter Placeholder" }).getByRole("button", { name: "Choose plan" }).click();
  await expect(page).toHaveURL(/checkout-test/);
});

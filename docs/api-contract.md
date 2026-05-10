# API Contract

## Base URLs

Local:

- `http://localhost:8080`

Production:

- Cloud Run service URL or custom domain.

## Authentication

Protected endpoints require one of:

```http
Authorization: Bearer <api_key>
X-API-Key: <api_key>
```

Public endpoints:

- `GET /healthz`

Readiness may be public or internal depending on deployment policy.

## Headers

Request headers:

- `Content-Type: application/json` for JSON requests.
- `X-Request-ID`: optional client request id.
- `Idempotency-Key`: optional for synthesis deduplication.

Response headers:

- `X-Request-ID`
- `X-Job-ID` for synthesis responses.
- `X-Video-ID` or `X-Job-ID` for video localization responses when emitted by the implementation.

## `GET /healthz`

Returns liveness.

Response `200`:

```json
{
  "status": "ok",
  "service": "voice-ai",
  "version": "0.1.0"
}
```

## `GET /readyz`

Returns dependency readiness.

Response `200`:

```json
{
  "status": "ready",
  "provider": {
    "name": "openai",
    "ready": true
  },
  "storage": {
    "mode": "local",
    "ready": true
  },
  "mlflow": {
    "configured": true,
    "ready": true
  }
}
```

Response `503` uses the same shape with failed components marked `ready: false`.

## `GET /v1/product/plans`

Returns public pricing/package copy and billing mode. This endpoint is public and may return pricing-copy-only data when Stripe is not configured.

Response `200`:

```json
{
  "plans": [
    {
      "id": "starter",
      "name": "Starter",
      "monthly_price_usd": 0,
      "included_minutes": 20,
      "stripe_price_id": null
    }
  ],
  "billing": {
    "available": false,
    "mode": "not-configured",
    "production_billing": false
  }
}
```

## `GET /v1/product/capabilities`

Returns runtime capability metadata used by the frontend to distinguish prototype, billing, auth, provider, and storage readiness. It is evidence, not a production-readiness certificate.

Response `200`:

```json
{
  "service": "voice-ai",
  "environment": "local",
  "tts": {
    "available": true,
    "active_provider": "openai",
    "local_fallback": true
  },
  "video_localization": {
    "available": true,
    "demo_mode": false,
    "ffmpeg_available": true
  },
  "auth": {
    "available": true,
    "mode": "jwt-password",
    "production_identity": true,
    "storage": "sqlite"
  },
  "billing": {
    "available": false,
    "mode": "not-configured",
    "production_billing": false
  }
}
```

Commercial release docs must not treat `environment: "local"`, `storage: "sqlite"`, or `billing.production_billing: false` as production-ready.

## `GET /v1/voices`

Lists voices for the active provider.

Query parameters:

- `language_code`: optional, example `en-US`.

Response `200`:

```json
{
  "provider": "openai",
  "voices": [
    {
      "name": "marin",
      "language_codes": ["vi-VN"],
      "ssml_gender": null,
      "natural_sample_rate_hz": 24000,
      "supported_encodings": ["MP3", "LINEAR16", "OGG_OPUS"]
    }
  ]
}
```

## `POST /v1/video-localization/jobs`

Current public prototype endpoint. It accepts a source video and localization options in one multipart request, performs short-video localization inline during the HTTP request, and returns the completed job payload when successful.

This endpoint is suitable for controlled prototype testing. It is not the target commercial production shape for long-running workloads.

Request:

- `multipart/form-data`
- Field `file`: source video file.
- Field `source_language`: `en-US`, `en`, `zh-CN`, `zh`, or `auto` where supported by the runtime.
- Field `target_language`: `vi` or `vi-VN`; MVP target is Vietnamese.
- Field `voice_name`: optional active-provider voice, for example `marin` on OpenAI.
- Field `subtitle_format`: optional subtitle preference when exposed by the client.

Current OpenAI-backed prototype limits:

- OpenAI speech-to-text upload limit is 25 MB per file; backend evidence enforces this for current uploaded video bytes.
- OpenAI text-to-speech request input limit is 4096 characters per synthesis call; production chunking is not proven.
- Frontend or deploy config may advertise larger video limits, but those are target/planned values until provider-aware validation and chunking are implemented.

Response `200`:

```json
{
  "job_id": "vid_5f5d6bde54404efbb05375c1fdc80d32",
  "status": "succeeded",
  "source_language": "en-US",
  "target_language": "vi",
  "provider": {
    "name": "openai",
    "fallback": false,
    "model": "gpt-4o-mini-transcribe+gpt-4o-mini+gpt-4o-mini-tts"
  },
  "input_filename": "source-speaking.mp4",
  "input_bytes": 92659,
  "transcript_chars": 95,
  "translated_chars": 112,
  "segments": [
    {
      "index": 1,
      "start_ms": 0,
      "end_ms": 6250,
      "source_text": "Hello, this is a short English video for testing Vietnamese localization on the public website.",
      "translated_text": "Xin chào, đây là một video tiếng Anh ngắn để thử nghiệm việc địa phương hóa tiếng Việt trên trang web công cộng."
    }
  ],
  "artifacts": [
    {
      "kind": "transcript",
      "url": "http://103.27.237.252:8080/v1/video-localization/jobs/vid_5f5d6bde54404efbb05375c1fdc80d32/artifacts/transcript.json",
      "bytes": 523,
      "checksum_sha256": "example",
      "content_type": "application/json"
    },
    {
      "kind": "localized_video",
      "url": "http://103.27.237.252:8080/v1/video-localization/jobs/vid_5f5d6bde54404efbb05375c1fdc80d32/artifacts/localized.vi.mp4",
      "bytes": 69087,
      "checksum_sha256": "example",
      "content_type": "video/mp4"
    }
  ],
  "latency_ms": 6400,
  "observability": {
    "request_id": "req_aeb4dc2b13ed42b68e6f16ba1672f79e",
    "mlflow_run_id": "568f8bee63c44aed97ec4e325b161bab",
    "warnings": []
  },
  "warnings": [],
  "error": null
}
```

Current artifact kinds include `source_video`, `source_audio`, `transcript`, `subtitles_srt`, `subtitles_vtt`, `voiceover_audio`, and `localized_video`.

Target production behavior:

- Split upload, job creation, status polling, and artifact manifest routes may be reintroduced when backed by durable storage and an async worker.
- Production jobs should return `202 queued` quickly, persist source media to object storage, execute through Cloud Tasks, Cloud Run Jobs, Pub/Sub, or another durable worker, and expose polling/cancel/retry semantics.
- Production artifact URLs should be signed or authenticated durable object-storage URLs, not local container file paths.

## `GET /v1/video-localization/jobs/{job_id}`

Returns localization job status.

Response `200`:

```json
{
  "job_id": "vid_5f5d6bde54404efbb05375c1fdc80d32",
  "status": "succeeded",
  "source_language": "en-US",
  "target_language": "vi",
  "provider": {
    "name": "openai",
    "fallback": false,
    "model": "gpt-4o-mini-transcribe+gpt-4o-mini+gpt-4o-mini-tts"
  },
  "artifacts": [],
  "latency_ms": 6400,
  "observability": {
    "request_id": "req_123",
    "mlflow_run_id": "run_abc"
  },
  "error": null
}
```

Terminal statuses: `succeeded`, `failed`, `canceled`.

Non-terminal statuses: `queued`, `running`.

## `GET /v1/video-localization/jobs/{job_id}/artifacts/{filename}`

Downloads a generated artifact file for the current public prototype.

Supported current filenames include:

- Source and extracted media, for example `source-speaking.mp4` and `source-audio.mp3`.
- `transcript.json`.
- `subtitles.vi.srt` and `subtitles.vi.vtt`.
- `voiceover.vi.wav`.
- `localized.vi.mp4`.

Production may return a signed Cloud Storage URL redirect, an authenticated stream, or a JSON envelope containing a temporary URL depending on access policy.

## Billing Routes

Billing is present as a backend capability but is not configured on the current public prototype. Commercial purchase flow must remain blocked until Stripe secrets, URLs, webhook handling, entitlement checks, and frontend/backend route compatibility are verified.

### `GET /v1/billing/subscription`

Returns the authenticated user's subscription and entitlement state. Requires a session/auth token when auth is enabled.

### `POST /v1/billing/checkout-session`

Current backend route for creating a Stripe Checkout Session.

Request:

```json
{
  "plan_id": "creator"
}
```

Response `200`:

```json
{
  "url": "https://checkout.stripe.com/c/pay/cs_test_...",
  "session_id": "cs_test_123"
}
```

Response `503`:

```json
{
  "error": {
    "code": "billing_not_configured",
    "message": "Stripe billing is not configured."
  }
}
```

### `POST /v1/billing/customer-portal`

Current backend route for creating a Stripe customer portal session. Returns the same `url`/`session_id` response shape as Checkout.

### Compatibility aliases

The frontend audit observed calls to `POST /v1/billing/checkout` and `POST /v1/billing/portal`. Those aliases are compatibility targets only unless a backend agent adds and verifies them. Until then, the documented backend routes are `/v1/billing/checkout-session` and `/v1/billing/customer-portal`.

### `POST /v1/billing/stripe-webhook`

Stripe webhook receiver for billing lifecycle events. Production release must follow Stripe webhook guidance: verify signatures, make fulfillment idempotent, check payment/subscription state, and handle subscription lifecycle events before granting paid entitlements.

## `POST /v1/synthesize`

Synthesizes text or SSML into audio.

Request:

```json
{
  "text": "Xin chào từ Voice AI.",
  "ssml": null,
  "voice": {
    "language_code": "vi-VN",
    "name": "marin",
    "ssml_gender": null
  },
  "audio": {
    "encoding": "MP3",
    "speaking_rate": 1.0,
    "pitch": 0.0,
    "volume_gain_db": 0.0,
    "sample_rate_hz": 24000
  },
  "metadata": {
    "client_reference_id": "script-123"
  }
}
```

Validation rules:

- Exactly one of `text` or `ssml` is required.
- `text` or `ssml` must not exceed `MAX_INPUT_CHARS`.
- For the current OpenAI provider path, request text must not exceed the OpenAI TTS 4096 character input limit unless the backend intentionally chunks requests.
- `voice.language_code` is required.
- `audio.encoding` defaults to `MP3`.
- Supported MVP encodings: `MP3`, `LINEAR16`, `OGG_OPUS`.

Response `200`:

```json
{
  "job_id": "tts_01HX123456789ABCDEFG",
  "status": "succeeded",
  "audio_url": "http://localhost:8080/audio/tts_01HX123456789ABCDEFG.mp3",
  "audio_path": "data/audio/tts_01HX123456789ABCDEFG.mp3",
  "duration_ms": 1250,
  "latency_ms": 842,
  "provider": {
    "name": "openai",
    "fallback": false,
    "model": "gpt-4o-mini-tts"
  },
  "voice": {
    "language_code": "vi-VN",
    "name": "marin",
    "ssml_gender": null
  },
  "audio": {
    "encoding": "MP3",
    "bytes": 18342,
    "sample_rate_hz": 24000,
    "checksum_sha256": "example"
  },
  "observability": {
    "request_id": "req_123",
    "mlflow_run_id": "run_abc"
  },
  "metadata": {
    "client_reference_id": "script-123"
  }
}
```

## Static Audio

Local:

- `GET /audio/{filename}` serves generated files from `AUDIO_STORAGE_DIR`.
- `GET /artifacts/{job_id}/{filename}` may serve local demo/localization artifacts from `ARTIFACT_STORAGE_DIR`.

Production:

- Prefer Cloud Storage signed URLs, CDN URLs, or authenticated media endpoints.
- If `/audio/{filename}` or `/artifacts/{job_id}/{filename}` remains available in production, it must read from durable object storage rather than Cloud Run's local filesystem.

## Error Shape

All non-2xx errors return:

```json
{
  "error": {
    "code": "provider_unavailable",
    "message": "Text-to-speech provider is not ready.",
    "details": {
      "provider": "openai"
    }
  },
  "request_id": "req_123",
  "job_id": "tts_01HX123456789ABCDEFG"
}
```

Common status codes:

- `400`: invalid input or unsupported option.
- `401`: missing or invalid authentication.
- `403`: authenticated but not authorized.
- `413`: input exceeds configured size limit.
- `422`: schema validation failure.
- `429`: rate limit or provider quota.
- `500`: internal storage or unexpected error.
- `503`: provider or dependency unavailable.

## Environment Variables

- `ENVIRONMENT`
- `PORT`
- `TTS_PROVIDER`
- `TRANSCRIPTION_PROVIDER`
- `TRANSLATION_PROVIDER`
- `OPENAI_API_KEY`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `GCP_PROJECT_ID`
- `MLFLOW_TRACKING_URI`
- `AUDIO_STORAGE_DIR`
- `ARTIFACT_STORAGE_DIR`
- `UPLOAD_STORAGE_DIR`
- `AUDIO_BASE_URL`
- `ARTIFACT_BASE_URL`
- `API_KEYS`
- `JWT_SECRET`
- `AUTH_STORAGE_PATH`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_SUCCESS_URL`
- `STRIPE_CANCEL_URL`
- `STRIPE_PORTAL_RETURN_URL`
- `CORS_ALLOW_ORIGINS`
- `MAX_INPUT_CHARS`
- `MAX_VIDEO_UPLOAD_MB`
- `MAX_VIDEO_DURATION_SECONDS`
- `LOG_LEVEL`

## Current Source Notes

- Current public prototype evidence uses OpenAI for TTS and video localization, local storage, Docker/tmux runtime, FFmpeg, and internal/local MLflow tracking.
- OpenAI TTS input is limited to 4096 characters per request; OpenAI speech-to-text uploads are limited to 25 MB.
- Google Speech-to-Text asynchronous recognition remains the target Google-backed production option for long-running English/Chinese transcription if Google is selected.
- Google Speech-to-Text language support includes English and Chinese variants; target translation can use Google Cloud Translation if Google is selected.
- Google Video Intelligence speech transcription is not the preferred source for this MVP because that feature is English-only.
- Google Text-to-Speech `text:synthesize` remains a target Vietnamese voice generation option if Google is selected.
- FFmpeg is the expected implementation boundary for local media transforms and final MP4 rendering.

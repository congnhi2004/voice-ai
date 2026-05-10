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
- `X-Video-ID` for video upload responses.

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
    "name": "google",
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

## `GET /v1/voices`

Lists voices for the active provider.

Query parameters:

- `language_code`: optional, example `en-US`.

Response `200`:

```json
{
  "provider": "google",
  "voices": [
    {
      "name": "en-US-Standard-C",
      "language_codes": ["en-US"],
      "ssml_gender": "FEMALE",
      "natural_sample_rate_hz": 24000,
      "supported_encodings": ["MP3", "LINEAR16", "OGG_OPUS"]
    }
  ]
}
```

## `POST /v1/videos`

Uploads a source video for localization.

Request:

- `multipart/form-data`
- Field `file`: video file.
- Field `source_language`: `en`, `en-US`, `zh`, `zh-CN`, `zh-TW`, or `auto`.
- Field `metadata`: optional JSON string with `client_reference_id`.

MVP limits:

- `MAX_VIDEO_UPLOAD_MB`: default `250`.
- `MAX_VIDEO_DURATION_SECONDS`: default `900`.
- Supported containers/codecs should be documented by implementation; MVP should accept common MP4/H.264 inputs.

Response `202`:

```json
{
  "video_id": "vid_01HX123456789ABCDEFG",
  "status": "uploaded",
  "source_language": "en-US",
  "filename": "source.mp4",
  "bytes": 10485760,
  "duration_ms": 61234,
  "storage_uri": "local://data/artifacts/vid_01HX/source.mp4",
  "request_id": "req_123"
}
```

## `POST /v1/localization-jobs`

Creates an asynchronous localization job for an uploaded Chinese or English video.

Request:

```json
{
  "video_id": "vid_01HX123456789ABCDEFG",
  "source_language": "en-US",
  "target_language": "vi",
  "subtitle": {
    "formats": ["srt", "vtt"],
    "render_mode": "burn_in"
  },
  "voice": {
    "language_code": "vi-VN",
    "name": "vi-VN-Standard-A",
    "ssml_gender": "FEMALE"
  },
  "audio": {
    "encoding": "MP3",
    "speaking_rate": 1.0,
    "pitch": 0.0
  },
  "render": {
    "audio_mode": "replace_source",
    "output_container": "mp4"
  },
  "metadata": {
    "client_reference_id": "video-123"
  }
}
```

Validation rules:

- `video_id` is required.
- Source language must be English or Chinese for MVP.
- `target_language` must be `vi`.
- `subtitle.render_mode` may be `burn_in`, `sidecar`, or `both`.
- `render.audio_mode` may be `replace_source`, `mix_under`, or `sidecar_audio`.

Response `202`:

```json
{
  "job_id": "loc_01HX123456789ABCDEFG",
  "video_id": "vid_01HX123456789ABCDEFG",
  "status": "queued",
  "stage": "queued",
  "progress": 0,
  "status_url": "/v1/localization-jobs/loc_01HX123456789ABCDEFG",
  "artifacts_url": "/v1/localization-jobs/loc_01HX123456789ABCDEFG/artifacts",
  "request_id": "req_123"
}
```

## `GET /v1/localization-jobs/{job_id}`

Returns localization job status.

Response `200`:

```json
{
  "job_id": "loc_01HX123456789ABCDEFG",
  "video_id": "vid_01HX123456789ABCDEFG",
  "status": "running",
  "stage": "translating",
  "progress": 45,
  "source_language": "en-US",
  "target_language": "vi",
  "created_at": "2026-05-10T10:00:00Z",
  "updated_at": "2026-05-10T10:02:00Z",
  "stages": [
    {"name": "extract_audio", "status": "succeeded", "latency_ms": 900},
    {"name": "transcribe", "status": "succeeded", "latency_ms": 32000},
    {"name": "translate", "status": "running", "latency_ms": null}
  ],
  "providers": {
    "transcription": "google-speech-to-text",
    "translation": "google-cloud-translation",
    "tts": "google-cloud-text-to-speech",
    "media": "ffmpeg"
  },
  "observability": {
    "request_id": "req_123",
    "mlflow_run_id": "run_abc"
  },
  "error": null
}
```

Terminal statuses: `succeeded`, `failed`, `canceled`.

Non-terminal statuses: `queued`, `running`.

## `GET /v1/localization-jobs/{job_id}/artifacts`

Lists generated artifacts. For non-complete jobs, return currently available artifacts.

Response `200`:

```json
{
  "job_id": "loc_01HX123456789ABCDEFG",
  "status": "succeeded",
  "artifacts": [
    {
      "type": "vietnamese_transcript",
      "format": "txt",
      "download_url": "/v1/localization-jobs/loc_01HX123456789ABCDEFG/artifacts/vietnamese_transcript/download",
      "bytes": 4096,
      "checksum_sha256": "example"
    },
    {
      "type": "subtitles_srt",
      "format": "srt",
      "download_url": "/v1/localization-jobs/loc_01HX123456789ABCDEFG/artifacts/subtitles_srt/download",
      "bytes": 2048,
      "checksum_sha256": "example"
    },
    {
      "type": "subtitles_vtt",
      "format": "vtt",
      "download_url": "/v1/localization-jobs/loc_01HX123456789ABCDEFG/artifacts/subtitles_vtt/download",
      "bytes": 2048,
      "checksum_sha256": "example"
    },
    {
      "type": "vietnamese_audio",
      "format": "mp3",
      "download_url": "/v1/localization-jobs/loc_01HX123456789ABCDEFG/artifacts/vietnamese_audio/download",
      "duration_ms": 59000,
      "bytes": 940000
    },
    {
      "type": "localized_video",
      "format": "mp4",
      "download_url": "/v1/localization-jobs/loc_01HX123456789ABCDEFG/artifacts/localized_video/download",
      "duration_ms": 61234,
      "bytes": 12000000
    }
  ]
}
```

## `GET /v1/localization-jobs/{job_id}/artifacts/{artifact_type}/download`

Downloads or redirects to the requested artifact.

Supported MVP artifact types:

- `vietnamese_transcript`
- `subtitles_srt`
- `subtitles_vtt`
- `vietnamese_audio`
- `localized_video`

Production may return a signed Cloud Storage URL redirect, an authenticated stream, or a JSON envelope containing a temporary URL depending on access policy.

## `POST /v1/synthesize`

Synthesizes text or SSML into audio.

Request:

```json
{
  "text": "Hello from Voice AI.",
  "ssml": null,
  "voice": {
    "language_code": "en-US",
    "name": "en-US-Standard-C",
    "ssml_gender": "FEMALE"
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
    "name": "google",
    "fallback": false,
    "model": "cloud-text-to-speech"
  },
  "voice": {
    "language_code": "en-US",
    "name": "en-US-Standard-C",
    "ssml_gender": "FEMALE"
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
      "provider": "google"
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
- `GOOGLE_APPLICATION_CREDENTIALS`
- `GCP_PROJECT_ID`
- `MLFLOW_TRACKING_URI`
- `AUDIO_STORAGE_DIR`
- `ARTIFACT_STORAGE_DIR`
- `UPLOAD_STORAGE_DIR`
- `AUDIO_BASE_URL`
- `ARTIFACT_BASE_URL`
- `API_KEYS`
- `CORS_ALLOW_ORIGINS`
- `MAX_INPUT_CHARS`
- `MAX_VIDEO_UPLOAD_MB`
- `MAX_VIDEO_DURATION_SECONDS`
- `LOG_LEVEL`

## Current Source Notes

- Google Speech-to-Text asynchronous recognition should back long-running transcription jobs for uploaded videos.
- Google Speech-to-Text language support includes English and Chinese variants; target translation is Vietnamese through Google Cloud Translation.
- Google Video Intelligence speech transcription is not the preferred source for this MVP because that feature is English-only.
- Google Text-to-Speech `text:synthesize` remains the direct Vietnamese voice generation API.
- FFmpeg is the expected implementation boundary for local media transforms and final MP4 rendering.

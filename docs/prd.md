# Product Requirements Document

## Problem

Teams need a dependable way to localize English or Chinese videos into Vietnamese without manually coordinating transcription, translation, subtitles, TTS, and video rendering. A sellable Voice AI product must offer an ergonomic upload/job API, downloadable localized assets, predictable output, operational visibility, and production deployment practices.

## Goals

- Provide a production-target video localization pipeline backed by OpenAI or Google speech/translation/TTS providers and FFmpeg.
- Preserve the existing TTS API for direct Vietnamese voice generation.
- Make local development and CI independent from live Google credentials through a fallback/demo provider.
- Track every localization job and synthesis request with useful operational and product metrics.
- Deploy as a Cloud Run service with documented CI/CD, rollback, and environment management.

## Personas

- Developer integrator: calls the API from another product and needs stable upload/job/artifact contracts.
- Content producer: uploads a Chinese or English video and downloads Vietnamese localized assets.
- Operator: owns uptime, cost, quota, security, and release rollback.
- QA engineer: verifies output behavior without depending on a live cloud provider for every test.

## Functional Requirements

### Health And Readiness

- `GET /healthz` returns process liveness.
- `GET /readyz` verifies provider configuration, writable audio storage, and optional MLflow connectivity.

### Voice Catalog

- `GET /v1/voices` returns the voice catalog available for the active provider.
- Production should proxy/cache active provider voice metadata where feasible.
- Local fallback may return a small deterministic set of fake voices.

### Video Localization

- Current public prototype: `POST /v1/video-localization/jobs` accepts a Chinese or English video upload plus localization options as multipart form data and returns a completed job payload for short videos.
- Current public prototype: `GET /v1/video-localization/jobs/{job_id}` returns the recorded job payload when available.
- Current public prototype: `GET /v1/video-localization/jobs/{job_id}/artifacts/{filename}` downloads generated source, transcript, subtitle, voiceover, or localized MP4 artifacts.
- Target production model: split source upload, asynchronous job creation, status polling, cancel/retry, and artifact manifest routes backed by durable storage and a worker.
- MVP artifact types: Vietnamese transcript/script, SRT, VTT, Vietnamese TTS audio, and final localized MP4.
- Source language must be English or Chinese. Target language is Vietnamese for MVP.
- The pipeline must extract audio, transcribe source speech with timestamps, translate transcript/script to Vietnamese, create Vietnamese subtitle files, synthesize Vietnamese voice audio, and render final MP4.
- Production async mode should use a provider path that supports the chosen language and file-size/duration limits. Google Speech-to-Text asynchronous or long-audio recognition remains a target option for English/Chinese. The current public prototype uses OpenAI for real TTS/video localization.
- FFmpeg is required for audio extraction, subtitle processing, audio muxing/replacement, and final MP4 rendering.

### Synthesis

- `POST /v1/synthesize` accepts text or SSML, language/voice settings, audio encoding, and tuning parameters.
- The current public prototype calls OpenAI TTS with `gpt-4o-mini-tts` and voices such as `marin`; Google Cloud Text-to-Speech remains a production target option when Google credentials are configured.
- Provider-specific audio is stored as a generated audio file.
- The response returns JSON with `job_id`, `status`, `audio_url`, `audio_path`, `duration_ms`, `latency_ms`, `provider`, and metadata.
- Requests must be idempotent only when a client supplies an idempotency key; otherwise each request creates a new job.

### Audio Retrieval

- Local dev serves files from `AUDIO_STORAGE_DIR` through `/audio/{filename}`.
- Local dev may serve video, subtitle, transcript, and rendered media artifacts from `ARTIFACT_STORAGE_DIR`.
- Production should store durable audio/video/text artifacts in Cloud Storage and return signed URLs or authenticated download URLs. Cloud Run container filesystem is disposable and must not be treated as durable storage.

### Frontend MVP

- A minimal web UI can upload a video, create a localization job, poll job status, preview/download artifacts, and call voice list/synthesize endpoints.
- UI must support video upload, source language selection or auto-detect request, Vietnamese voice selection, subtitle mode, submit state, progress, error state, audio playback, and final video playback/download.
- UI must not expose Google credentials.

## Non-Functional Requirements

- Current public prototype video localization is synchronous inline request work and is suitable only for short controlled tests. Production video localization must be asynchronous; target accepted upload/job creation is under 5 seconds, with completion dependent on duration and provider latency.
- P95 synthesis API latency target: under 4 seconds for typical short Vietnamese text, excluding provider incidents.
- Request body limit must be provider-aware. OpenAI TTS currently has a 4096 character input limit; backend defaults above that are not production-ready without chunking.
- Upload size and duration limits must be configurable and provider-aware. OpenAI STT file uploads are limited to 25 MB; larger frontend/deploy limits are target values until chunking or a large-file provider path is implemented.
- Structured JSON errors for validation, auth, provider failure, quota, and storage failure.
- Logs must include request id, job id, video id, stage, and artifact ids, but not raw transcript/script text by default.
- MLflow logging must degrade gracefully if unavailable, while surfacing readiness warnings.
- API keys and Google credentials must be injected through environment/secret management.

## Release Criteria

- All acceptance checklist items have evidence.
- Local tests pass without Google credentials.
- Local/demo mode can produce deterministic video localization artifacts.
- The public prototype has localized at least one English and one Chinese short sample video into Vietnamese with real OpenAI provider evidence.
- A production candidate has generated at least one provider-backed audio file under the intended production provider and limit settings.
- MLflow contains a run for a staging localization job and a staging synthesis request.
- Deployment runbook has been exercised by QA or infra.

## Key Risks

- Missing or invalid provider credentials block production synthesis/localization for that provider.
- OpenAI provider limits can reject longer text or video inputs unless the product implements chunking or a different large-file path.
- Cloud Run filesystem is not durable; production audio must move to Cloud Storage or equivalent.
- Video files are larger and more sensitive than text/audio-only artifacts; storage cost, retention, and access control must be explicit.
- Subtitle timing and translated speech duration may not match source timing automatically; MVP must state quality limits and evidence expectations.
- Google quota/cost spikes require rate limits and usage monitoring.
- Logging raw user text can create privacy and compliance exposure.

## Current Source Notes

- Current public prototype uses OpenAI for real TTS and video localization, local storage, local/tmux runtime, and MLflow internal tracking.
- Use Google Speech-to-Text for the target asynchronous English/Chinese production transcription path if Google is selected because it supports asynchronous recognition and has English/Chinese language coverage.
- Use Google Cloud Translation for Vietnamese target translation if Google is selected.
- Use Google Cloud Text-to-Speech for Vietnamese voice/dub audio generation if Google is selected.
- Do not rely on Video Intelligence speech transcription for Chinese coverage; official guidance states that feature is English-only.
- Use FFmpeg for deterministic media processing and final MP4 rendering.

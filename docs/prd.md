# Product Requirements Document

## Problem

Teams need a dependable way to localize English or Chinese videos into Vietnamese without manually coordinating transcription, translation, subtitles, TTS, and video rendering. A sellable Voice AI product must offer an ergonomic upload/job API, downloadable localized assets, predictable output, operational visibility, and production deployment practices.

## Goals

- Provide a production-grade video localization pipeline backed by Google Speech-to-Text, Cloud Translation, Google Cloud Text-to-Speech, and FFmpeg.
- Preserve the existing production-grade TTS API for direct Vietnamese voice generation.
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
- Production should proxy/cache Google voice metadata where feasible.
- Local fallback may return a small deterministic set of fake voices.

### Video Localization

- `POST /v1/videos` accepts a Chinese or English video upload and returns `video_id`.
- `POST /v1/localization-jobs` creates an asynchronous localization job for an uploaded video.
- `GET /v1/localization-jobs/{job_id}` returns status, progress, current stage, timing, provider metadata, and error details.
- `GET /v1/localization-jobs/{job_id}/artifacts` lists generated artifacts and download URLs.
- `GET /v1/localization-jobs/{job_id}/artifacts/{artifact_type}/download` downloads a requested artifact.
- MVP artifact types: Vietnamese transcript/script, SRT, VTT, Vietnamese TTS audio, and final localized MP4.
- Source language must be English or Chinese. Target language is Vietnamese for MVP.
- The pipeline must extract audio, transcribe source speech with timestamps, translate transcript/script to Vietnamese, create Vietnamese subtitle files, synthesize Vietnamese voice audio, and render final MP4.
- Production should use Google Speech-to-Text asynchronous or long-audio recognition for source transcription rather than Video Intelligence speech transcription because Video Intelligence speech transcription is English-only for that feature.
- FFmpeg is required for audio extraction, subtitle processing, audio muxing/replacement, and final MP4 rendering.

### Synthesis

- `POST /v1/synthesize` accepts text or SSML, language/voice settings, audio encoding, and tuning parameters.
- The service calls Google Cloud Text-to-Speech in production using required `input`, `voice`, and `audioConfig` concepts from the official API.
- The service decodes Google base64 audio into a stored audio file.
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

- Video localization is asynchronous. MVP target: accepted upload/job creation under 5 seconds; job completion target depends on video duration and provider latency.
- P95 synthesis API latency target: under 4 seconds for typical short Vietnamese text, excluding provider incidents.
- Request body limit: default 5,000 characters for MVP unless product explicitly raises it.
- Upload size and duration limits must be configurable, with MVP defaults documented in the API contract.
- Structured JSON errors for validation, auth, provider failure, quota, and storage failure.
- Logs must include request id, job id, video id, stage, and artifact ids, but not raw transcript/script text by default.
- MLflow logging must degrade gracefully if unavailable, while surfacing readiness warnings.
- API keys and Google credentials must be injected through environment/secret management.

## Release Criteria

- All acceptance checklist items have evidence.
- Local tests pass without Google credentials.
- Local/demo mode can produce deterministic video localization artifacts.
- A staging deployment has localized at least one English or Chinese sample video into Vietnamese.
- A staging deployment has generated at least one Google-backed audio file.
- MLflow contains a run for a staging localization job and a staging synthesis request.
- Deployment runbook has been exercised by QA or infra.

## Key Risks

- Missing or invalid Google credentials block production synthesis.
- Missing or invalid Google Speech-to-Text or Translation configuration blocks production localization.
- Cloud Run filesystem is not durable; production audio must move to Cloud Storage or equivalent.
- Video files are larger and more sensitive than text/audio-only artifacts; storage cost, retention, and access control must be explicit.
- Subtitle timing and translated speech duration may not match source timing automatically; MVP must state quality limits and evidence expectations.
- Google quota/cost spikes require rate limits and usage monitoring.
- Logging raw user text can create privacy and compliance exposure.

## Current Source Notes

- Use Google Speech-to-Text for English/Chinese source transcription because it supports asynchronous recognition and has English/Chinese language coverage.
- Use Google Cloud Translation for Vietnamese target translation.
- Use Google Cloud Text-to-Speech for Vietnamese voice/dub audio generation.
- Do not rely on Video Intelligence speech transcription for Chinese coverage; official guidance states that feature is English-only.
- Use FFmpeg for deterministic media processing and final MP4 rendering.

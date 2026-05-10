# AI System Design

## Architecture

Voice AI is a FastAPI application with a provider abstraction around video localization, transcription, translation, text-to-speech synthesis, artifact storage, and media rendering.

Core components:

- API layer: request validation, authentication, CORS, response contracts.
- Job orchestration layer: asynchronous localization jobs, stage state, retries, and artifact manifests.
- Transcription provider layer: Google Speech-to-Text for English/Chinese audio.
- Translation provider layer: Google Cloud Translation for Vietnamese text output.
- TTS provider layer: Google provider for production; local deterministic provider for dev and CI.
- Media processing layer: FFmpeg for extracting audio, creating subtitle outputs, muxing/replacing audio, and rendering MP4.
- Artifact storage layer: local filesystem in development; Cloud Storage or compatible durable object storage in production.
- Observability layer: structured logs, metrics, MLflow Tracking runs, and health/readiness checks.
- Deployment layer: Cloud Run service built from source or container image.

## Request Flow

### Direct TTS Flow

1. Client calls `POST /v1/synthesize` with text or SSML.
2. API validates auth, request size, input mode, voice config, and audio config.
3. Service creates `job_id` and starts timing.
4. TTS provider synthesizes audio.
5. Google provider sends a synchronous request to `POST https://texttospeech.googleapis.com/v1/text:synthesize`.
6. Google response returns `audioContent` as base64 audio data.
7. Service decodes audio, stores it, estimates or records duration, and returns JSON metadata.
8. Service logs metrics and parameters to MLflow.

### Video Localization Flow

1. Client uploads a Chinese or English video through `POST /v1/videos`.
2. Service validates auth, content type, file size, duration if available, and stores the source artifact.
3. Client creates a localization job through `POST /v1/localization-jobs`.
4. Job worker extracts source audio with FFmpeg.
5. Transcription provider runs Google Speech-to-Text asynchronous or long-audio recognition and returns timestamped segments.
6. Translation provider translates source segments into Vietnamese.
7. Subtitle builder writes Vietnamese SRT and VTT files.
8. TTS provider synthesizes Vietnamese voice/dub audio from the Vietnamese script.
9. Renderer uses FFmpeg to create the final MP4 with Vietnamese subtitles and Vietnamese audio according to the requested render mode.
10. Artifact manifest stores transcript/script, subtitles, audio, final MP4, checksums, durations, provider metadata, and download URLs.
11. Service logs stage metrics, provider metrics, and artifact references to MLflow.

## Provider Contract

TTS providers should expose:

- `list_voices(language_code: str | None) -> list[Voice]`
- `synthesize(request: SynthesizeRequest) -> ProviderSynthesisResult`
- `healthcheck() -> ProviderHealth`

Google provider maps local request fields to:

- `input.text` or `input.ssml`
- `voice.languageCode`, `voice.name`, `voice.ssmlGender`
- `audioConfig.audioEncoding`, `speakingRate`, `pitch`, `volumeGainDb`, `sampleRateHertz`
- Optional advanced voice options where supported

The official Google endpoint requires input, voice, and audioConfig, and returns base64 audio content.

Transcription providers should expose:

- `transcribe_async(source_audio_uri, source_language, options) -> TranscriptionJob`
- `get_transcription_result(provider_job_id) -> TimestampedTranscript`
- `healthcheck() -> ProviderHealth`

Translation providers should expose:

- `translate_segments(segments, source_language, target_language="vi") -> TranslatedSegments`
- `healthcheck() -> ProviderHealth`

Media processing should expose:

- `extract_audio(video_uri) -> audio_uri`
- `write_subtitles(translated_segments) -> srt_uri, vtt_uri`
- `render_video(video_uri, subtitle_uri, dub_audio_uri, render_mode) -> mp4_uri`
- `probe_media(uri) -> MediaMetadata`

Current-source decision: prefer Google Speech-to-Text over Video Intelligence speech transcription for this MVP because Video Intelligence speech transcription is English-only for that feature, while Speech-to-Text supports English and Chinese coverage.

## Local Fallback

The local/demo provider exists for tests and developer onboarding when `GOOGLE_APPLICATION_CREDENTIALS` or other cloud credentials are unavailable.

Required behavior:

- Return deterministic fake voice entries.
- Generate a small valid audio file or fixture-backed audio file.
- Preserve the same API response shape as Google-backed synthesis.
- Accept a fixture video upload and generate deterministic Vietnamese transcript/script, SRT, VTT, audio, and MP4 artifacts.
- Preserve the same localization job/status/artifact response shapes as cloud-backed localization.
- Mark metadata with `provider: "local"` and `fallback: true`.

## Storage

Development:

- Store files under `AUDIO_STORAGE_DIR`, default `./data/audio`.
- Store localization artifacts under `ARTIFACT_STORAGE_DIR`, default `./data/artifacts`.
- Serve static audio from `/audio/{filename}`.
- Serve local artifact downloads from `/artifacts/{job_id}/{filename}`.

Production:

- Do not rely on Cloud Run local filesystem for durable files.
- Store source videos, extracted audio, transcripts, subtitles, TTS audio, and rendered videos in Cloud Storage.
- Return signed URLs, authenticated media URLs, or CDN-backed public URLs depending on product policy.

## Failure Modes

- Validation failure: `400` or `422` with field details.
- Missing API key: `401`.
- Forbidden API key or tenant mismatch: `403`.
- Provider credentials missing: `503` readiness failure and synthesis error.
- Transcription, translation, TTS, or render stage failure: job status becomes `failed` with stage-specific error details.
- Unsupported source language: `400`.
- Unsupported media type, file too large, or duration too long: `400` or `413`.
- Google quota/rate error: `429` or `503` depending on upstream status.
- Audio storage failure: `500` with job id for support traceability.
- FFmpeg missing or render failure: `503` readiness failure or stage failure.
- MLflow failure: synthesis should continue, but response metadata should include an observability warning only in non-production unless policy allows client visibility.

## Production Decisions

- Use FastAPI for the HTTP boundary because Cloud Run supports Python web services and the official quickstart demonstrates FastAPI serving HTTP requests in a container.
- Use Cloud Run for stateless serving because it provides managed HTTPS services and can run containerized applications on Google infrastructure.
- Use Cloud Tasks, Pub/Sub, a worker service, or an equivalent job runner for long-running localization work rather than blocking HTTP requests.
- Use MLflow Tracking for localization and TTS lifecycle telemetry: source language, target language, provider settings, stage latency, character count, media duration, output artifact references, and quality review labels.

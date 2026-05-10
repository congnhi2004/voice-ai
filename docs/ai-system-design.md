# AI System Design

## Architecture

Voice AI is a FastAPI application with a provider abstraction around video localization, transcription, translation, text-to-speech synthesis, artifact storage, and media rendering.

Core components:

- API layer: request validation, authentication, CORS, response contracts.
- Current public video endpoint: synchronous multipart localization for short prototype videos at `POST /v1/video-localization/jobs`.
- Target job orchestration layer: asynchronous localization jobs, stage state, retries, and artifact manifests.
- Transcription provider layer: OpenAI in the current public prototype; Google Speech-to-Text remains a target option for English/Chinese audio in production async mode.
- Translation provider layer: OpenAI in the current public prototype; Google Cloud Translation remains a target option for Vietnamese text output.
- TTS provider layer: OpenAI in the current public prototype; Google provider is a target production option; local deterministic provider remains for dev and CI.
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
5. The active provider sends a synchronous TTS request. Current public runtime uses OpenAI `gpt-4o-mini-tts`; Google target mode uses `POST https://texttospeech.googleapis.com/v1/text:synthesize`.
6. Provider response returns audio bytes or encoded audio content.
7. Service decodes audio, stores it, estimates or records duration, and returns JSON metadata.
8. Service logs metrics and parameters to MLflow.

### Current Public Video Localization Flow

1. Client uploads a Chinese or English video through `POST /v1/video-localization/jobs` as multipart form data.
2. Service validates auth, content type, current provider file-size limits, source language, and target language.
3. Service creates a job id, stores the source artifact locally, and processes the short video inline during the HTTP request.
4. FFmpeg extracts source audio.
5. Current public provider path uses OpenAI transcription and translation for supported short files.
6. Subtitle builder writes Vietnamese SRT and VTT files.
7. TTS provider synthesizes Vietnamese voice/dub audio from the Vietnamese script.
8. Renderer uses FFmpeg to create the final MP4 with Vietnamese subtitles and Vietnamese audio according to the current render mode.
9. Response returns the completed job payload with transcript segments, artifact URLs, checksums, provider metadata, latency, and MLflow run id when tracking succeeds.

This flow is a prototype implementation. It can prove product value for short samples, but it should not be presented as the production worker architecture.

### Target Production Video Localization Flow

1. Client uploads source media to an authenticated upload endpoint or signed object-storage URL.
2. Service validates source metadata, stores the source in durable object storage, creates a job record, and returns `202 queued` within the request lifetime.
3. Cloud Tasks, Cloud Run Jobs, Pub/Sub, or an equivalent worker dispatches the job.
4. Worker extracts source audio with FFmpeg.
5. Transcription provider runs a provider path appropriate for the source language, duration, and file size. Google Speech-to-Text asynchronous or long-audio recognition is the preferred Google path for English/Chinese if Google is selected.
6. Translation provider translates source segments into Vietnamese.
7. Subtitle builder writes Vietnamese SRT and VTT files.
8. TTS provider synthesizes Vietnamese voice/dub audio from the Vietnamese script, chunking where provider character limits require it.
9. Renderer uses FFmpeg to create the final MP4.
10. Artifact manifest stores transcript/script, subtitles, audio, final MP4, checksums, durations, provider metadata, and signed or authenticated download URLs.
11. Service logs stage metrics, provider metrics, and artifact references to MLflow or the approved observability store.

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

OpenAI provider mode must enforce current OpenAI limits before calling the provider: TTS input is limited to 4096 characters per request, and speech-to-text file uploads are limited to 25 MB unless the service implements chunking or a different large-file path.

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

Current-source decision: prefer Google Speech-to-Text over Video Intelligence speech transcription for the target Google-backed production path because Video Intelligence speech transcription is English-only for that feature, while Speech-to-Text supports English and Chinese coverage. The current public prototype uses OpenAI instead.

## Local Fallback

The local/demo provider exists for tests and developer onboarding when `GOOGLE_APPLICATION_CREDENTIALS` or other cloud credentials are unavailable.

Required behavior:

- Return deterministic fake voice entries.
- Generate a small valid audio file or fixture-backed audio file.
- Preserve the same API response shape as Google-backed synthesis.
- Accept a fixture video upload and generate deterministic Vietnamese transcript/script, SRT, VTT, audio, and MP4 artifacts.
- Preserve the same localization job/status/artifact response shapes as cloud-backed localization.
- Mark metadata with `provider: "local"` and `fallback: true`.
- Do not present beep/tone fallback output as real Voice AI quality in public prototype evidence.

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
- Run long video processing outside the public request thread through a durable worker model.

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

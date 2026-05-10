# Backend Real Video Localization Report - 2026-05-10

## Files Changed

- `app/config.py`
  - Added `OPENAI_TRANSCRIPTION_MODEL` and `OPENAI_TRANSLATION_MODEL`.
  - Changed default `LOCALIZATION_PROVIDER` from `local` to `auto`.
- `app/video_localization.py`
  - Added OpenAI-backed video localization provider.
  - Added upload metadata validation, 25 MB provider-limit guard, source-language normalization, FFmpeg probe/audio extraction helpers, and explicit provider selection.
  - Auto mode now selects OpenAI when `OPENAI_API_KEY` is configured, otherwise local deterministic fallback remains available.
  - Real path extracts source audio, transcribes with OpenAI, translates/adapts to Vietnamese, writes transcript/subtitle artifacts, synthesizes Vietnamese speech, and attempts final MP4 mux.
- `app/main.py`
  - Added early upload validation for video jobs.
  - Added redacted OpenAI provider error mapping.
  - Readiness now reports selected video localization provider.
- `tests/backend/test_api.py`
  - Added mocked OpenAI transcription/translation/TTS test coverage.
  - Added provider-secret redaction test.
  - Added oversized upload rejection test.

## Official Docs And Context7 Sources

Official OpenAI sources checked with built-in web search:

- OpenAI Speech to text guide: `https://platform.openai.com/docs/guides/speech-to-text`
  - Confirmed `gpt-4o-transcribe` and `gpt-4o-mini-transcribe`.
  - Confirmed 25 MB upload limit.
  - Confirmed supported upload formats include `mp4`, `wav`, and `webm`.
- OpenAI Audio API reference, transcriptions/speech: `https://platform.openai.com/docs/api-reference/audio/transcriptions`
  - Confirmed transcription request shape and model set.
  - Confirmed `gpt-4o-transcribe`/`gpt-4o-mini-transcribe` support `json` and `text` response formats.
- OpenAI Text to speech guide/API reference: `https://platform.openai.com/docs/guides/text-to-speech`
  - Confirmed `gpt-4o-mini-tts` and speech endpoint usage.
  - Confirmed supported speech output formats include `mp3` and `wav`.

Context7 used before code changes:

- `/openai/openai-python`, topic `audio transcriptions speech create responses client errors`
- `/fastapi/fastapi`, topic `UploadFile TestClient dependency overrides HTTPException BackgroundTasks`

## Pipeline Behavior

- `POST /v1/video-localization/jobs` keeps the existing multipart contract.
- In `LOCALIZATION_PROVIDER=auto`, the backend uses OpenAI when `OPENAI_API_KEY` is present.
- Without OpenAI credentials, the backend uses the existing local deterministic fallback and returns provider metadata as `{"name":"local","fallback":true,...}`.
- Real OpenAI path:
  - Validates file extension/content type and rejects uploads over 25 MB.
  - Requires Chinese, English, or auto source language.
  - Uses FFmpeg/ffprobe to validate the media and extract mono 16 kHz MP3 source audio.
  - Transcribes source speech with `OPENAI_TRANSCRIPTION_MODEL`, default `gpt-4o-mini-transcribe`.
  - Translates/adapts transcript to Vietnamese with `OPENAI_TRANSLATION_MODEL`, default `gpt-4o-mini`.
  - Generates Vietnamese SRT/VTT from the translated script.
  - Synthesizes Vietnamese voice with OpenAI TTS when credentials are present, default `gpt-4o-mini-tts` and `marin`.
  - Attempts to mux original video, Vietnamese audio, and Vietnamese subtitles into `localized.vi.mp4`.
- Provider metadata is explicit:
  - OpenAI real path returns `provider.name=openai`, `fallback=false`, model string including transcription, translation, and TTS models.
  - Local fallback returns `provider.name=local`, `fallback=true`.

## Tests

Commands run:

```bash
python3 -m compileall app tests/backend/test_api.py
PYTHONPATH=. taskset -c 0-3 .venv/bin/pytest tests/backend/test_api.py
```

Result:

- `24 passed, 3 skipped, 2 warnings`
- The remaining skips are existing FFmpeg fixture-dependent tests in environments where the fixture cannot run.
- New OpenAI video pipeline tests mock OpenAI and FFmpeg boundaries, so they run without live credentials and without printing secrets.

## Privacy Notes

- No OpenAI key was read, printed, written, or logged.
- Tests use dummy keys only.
- Provider errors are redacted through existing secret redaction before returning API details.
- Logs and MLflow tracking continue to use metadata such as provider, language, character counts, latency, and status.
- Raw transcripts/translations are stored as user-facing artifacts for the job, but they are not logged to MLflow or structured logs.

## Public Acceptance Steps

1. Rebuild/restart the public backend with the existing server-side secret mechanism.
2. Confirm `/readyz` reports `video_localization.provider=openai` when `OPENAI_API_KEY` is configured.
3. Upload a short English or Chinese MP4/WebM under 25 MB with an audio track.
4. Confirm the response returns:
   - `provider.name=openai`
   - `provider.fallback=false`
   - transcript, SRT, VTT, voiceover audio, and localized MP4 artifacts.
5. Download artifacts through `/v1/video-localization/jobs/{job_id}/artifacts/{filename}`.
6. Use `ffprobe` on `localized.vi.mp4` to confirm video, Vietnamese audio, and subtitle streams when FFmpeg mux succeeds.

## Residual Risks

- OpenAI `gpt-4o-mini-transcribe` JSON output does not provide segment timestamps, so this MVP creates a single subtitle segment across the probed video duration.
- Videos over 25 MB are rejected until chunking/cloud storage/background jobs are added.
- Synchronous endpoint behavior remains acceptable for short public demos but should move to background jobs for production.
- Final MP4 mux depends on installed FFmpeg and source/container compatibility. Transcript, subtitles, and TTS artifacts are still generated when upstream stages succeed, but mux failures return a structured render error.

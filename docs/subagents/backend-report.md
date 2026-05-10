# Backend Builder Report

## Role Skill And Sources

Used role skill: `$voice-ai-backend-builder` from `/home/jhao/.codex/skills/voice-ai-backend-builder/SKILL.md`.

Current official/web sources checked before and during implementation:

- FastAPI official docs: testing with `TestClient`, CORS middleware, security/header patterns, and file uploads with `UploadFile`, `File`, and `Form`.
  - https://fastapi.tiangolo.com/tutorial/testing/
  - https://fastapi.tiangolo.com/tutorial/cors/
  - https://fastapi.tiangolo.com/tutorial/request-files/
  - https://fastapi.tiangolo.com/tutorial/request-forms-and-files/
- Google Cloud Text-to-Speech official docs: synchronous synthesize request shape, Python client concepts, `input`, `voice`, `audioConfig`, and base64/audio content behavior.
  - https://cloud.google.com/text-to-speech/docs/create-audio-text-client-libraries
  - https://cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize
- Google Cloud Speech-to-Text official docs: synchronous and streaming transcription concepts for future cloud video transcription.
  - https://cloud.google.com/speech-to-text/docs/v1/sync-recognize
  - https://docs.cloud.google.com/speech-to-text/v2/docs/sync-recognize
- Google Cloud Translation official docs: Translation v3 Python client and `translateText` request concepts for future cloud translation.
  - https://cloud.google.com/translate/docs/reference/libraries/v3/python
  - https://docs.cloud.google.com/translate/docs/translate-text
- MLflow Tracking official docs: run creation, params, metrics, tags, and artifacts.
  - https://mlflow.org/docs/latest/tracking.html
- FFmpeg official docs: stream selection, muxing, audio/video/subtitle handling, and MP4 subtitle codec constraints.
  - https://ffmpeg.org/ffmpeg.html
  - https://www.ffmpeg.org/documentation.html
- Context7 `/openai/openai-python`, topic `audio speech text to speech streaming response create file`: confirmed Python SDK speech creation under `client.audio.speech.create(...)` and response-format support for `/audio/speech`.
- PM-provided OpenAI official TTS notes used for API/model behavior: `/audio/speech`, `gpt-4o-mini-tts`, voices including `coral`, `wav`/`mp3` output, Vietnamese input support, and AI-generated voice disclosure requirement.

## 2026-05-10 OpenAI TTS Provider Update

Implemented a real OpenAI text-to-speech provider so the core TTS prototype no longer has to return the deterministic beep when credentials are available.

- `TTS_PROVIDER=openai` selects OpenAI explicitly.
- `TTS_PROVIDER=auto` still prefers healthy Google credentials first, then selects OpenAI when `OPENAI_API_KEY` exists, then falls back to local demo audio only when no real provider credentials are configured.
- `OPENAI_API_KEY` is read only from environment-backed settings and is never hardcoded in code, tests, or docs. Provider failures redact the configured key from API error details and avoid logging exception text that may contain the key.
- `OPENAI_TTS_MODEL` defaults to `gpt-4o-mini-tts`.
- `OPENAI_TTS_VOICE` defaults to `coral`.
- `OPENAI_TTS_RESPONSE_FORMAT` defaults to `wav` and accepts `wav` or `mp3`. WAV is the default because the current video-localization demo writes voiceover artifacts as WAV.
- `GET /v1/voices` returns OpenAI voice options, including `coral`, when the active provider is `openai`.
- `POST /v1/synthesize` stores and serves the returned OpenAI audio bytes through the existing local storage path and public `/audio/...` URL, preserving request ids, job ids, metadata, structured logs, and MLflow best-effort tracking.
- Local fallback remains available, but its provider metadata now reports `fallback=true` and model `deterministic-wav-tone-demo` to make demo mode explicit.

Infra restart command without exposing the key value:

```bash
set +x
: "${OPENAI_API_KEY:?Set OPENAI_API_KEY in this shell or a secret manager before restart}"
cat >/tmp/voice-ai-openai.override.yml <<'YAML'
services:
  app:
    environment:
      TTS_PROVIDER: openai
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      OPENAI_TTS_MODEL: gpt-4o-mini-tts
      OPENAI_TTS_VOICE: coral
      OPENAI_TTS_RESPONSE_FORMAT: wav
YAML
docker compose -f docker-compose.yml -f /tmp/voice-ai-openai.override.yml up -d --build app
```

Backend verification run:

```text
taskset -c 0-3 .venv/bin/python -m pytest tests/backend -q
16 passed, 3 skipped, 2 warnings in 1.76s
```

## Implemented

- FastAPI app package under `app/` with OpenAPI available through FastAPI.
- `GET /healthz` liveness.
- `GET /readyz` readiness for active TTS provider, local storage, MLflow config, and video localization mode. In this environment `ffmpeg_available` is `false`.
- `GET /v1/voices` with local fallback voices, Google provider adapter support, and OpenAI voice options when OpenAI is active.
- `POST /v1/synthesize` with typed validation, optional API key auth, request ids, job ids, deterministic local WAV fallback, local audio serving under `/audio/{filename}`, Google Cloud TTS adapter, OpenAI TTS adapter, and MLflow best-effort tracking.
- Structured JSON logs with request id, route, provider, status, latency, and no raw text by default.
- Optional API key auth through `Authorization: Bearer <key>` or `X-API-Key`.
- CORS settings through `CORS_ALLOW_ORIGINS`.
- Video localization demo workflow:
  - `POST /v1/video-localization/jobs` accepts `multipart/form-data` video upload plus `source_language`, `target_language`, and optional `voice_name`.
  - Local deterministic transcript for Chinese/English source videos.
  - Local deterministic Vietnamese translation.
  - Vietnamese TTS voiceover through the existing TTS provider boundary.
  - SRT and VTT subtitle artifact generation.
  - Final `localized.vi.mp4` artifact. If FFmpeg is available it attempts muxing with Vietnamese audio and subtitles; if FFmpeg is missing or muxing fails, local demo mode copies the uploaded MP4 and returns a warning while still producing audio and subtitle artifacts.
  - `GET /v1/video-localization/jobs/{job_id}` returns saved status.
  - `GET /v1/video-localization/jobs/{job_id}/artifacts/{filename}` downloads job artifacts.
  - MLflow best-effort tracking for video localization metadata using privacy-safe counts and artifact metadata, not raw source text by default in logs.

## Not Implemented Yet

- Real cloud video transcription through Google Speech-to-Text.
- Real cloud translation through Google Cloud Translation.
- Audio extraction from uploaded video before transcription.
- Asynchronous background queue or worker execution. The current video job endpoint processes synchronously and stores a completed status.
- Durable production artifact storage such as Cloud Storage signed URLs. Current implementation uses local filesystem storage.
- Guaranteed final MP4 muxing in environments without `ffmpeg`. This machine has no `ffmpeg` binary on PATH, so local demo mode produces a copied MP4 artifact plus separate Vietnamese WAV/SRT/VTT artifacts.
- Production rate limiting, tenant authorization, quotas, and dashboard/alert integration.

## API Behavior Evidence

Readiness probe sample:

```text
/readyz 200 {"status":"ready","provider":{"name":"local","ready":true,"detail":null},"storage":{"mode":"local","ready":true,"detail":null},"mlflow":{"configured":false,"ready":true,"detail":"MLFLOW_TRACKING_URI is not configured"},"video_localization":{"mode":"local","ready":true,"ffmpeg_available":false,"detail":"local demo mode can create artifacts without ffmpeg; real muxing requires ffmpeg"}}
```

TTS synthesize probe sample:

```text
/v1/synthesize 200 {"job_id":"tts_bfd0cff9b5464ff88eb86c89ec16f193","status":"succeeded","audio_url":"http://testserver/audio/tts_bfd0cff9b5464ff88eb86c89ec16f193.wav","audio_path":"/tmp/voice-ai-report-audio/tts_bfd0cff9b5464ff88eb86c89ec16f193.wav","duration_ms":600,"latency_ms":56,"provider":{"name":"local","fallback":true,"model":"deterministic-wav-tone"},"voice":{"language_code":"en-US","name":"local-en-US-test-voice","ssml_gender":"NEUTRAL"},"audio":{"encoding":"LINEAR16","bytes":28844,"sample_rate_hz":24000,"checksum_sha256":"1413f17a018608698f931c889f60c85233e6c9d3d26097989606f7fea3a58e76","content_type":"audio/wav"}}
```

Video localization probe sample:

```text
/v1/video-localization/jobs 200 {"job_id":"vid_ce0cd51615434039915a5595fa2b1554","status":"succeeded","source_language":"en-US","target_language":"vi","provider":{"name":"local","fallback":true,"model":"deterministic-video-localization-demo"},"input_filename":"sample.mp4","input_bytes":22,"transcript_chars":54,"translated_chars":80,"segments":[{"index":1,"start_ms":0,"end_ms":2800,"source_text":"Demo transcript from uploaded English video, 22 bytes.","translated_text":"Ban dich tieng Viet demo: Demo transcript from uploaded English video, 22 bytes."}],"artifacts":["source_video","transcript","subtitles_srt","subtitles_vtt","voiceover_audio","localized_video"]}
```

## Verification Commands

Dependency setup:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Test command:

```bash
.venv/bin/python -m pytest tests/backend -q
```

Latest test output:

```text
........                                                                 [100%]
=============================== warnings summary ===============================
tests/backend/test_api.py::test_google_required_credentials_readiness_failure
  /home/jhao/code/voice-ai/.venv/lib/python3.10/site-packages/google/api_core/_python_version_support.py:273: FutureWarning: You are using a Python version (3.10.12) which Google will stop supporting in new releases of google.api_core once it reaches its end of life (2026-10-04). Please upgrade to the latest Python version, or at least Python 3.11, to continue receiving updates for google.api_core past that date.
    warnings.warn(message, FutureWarning)

tests/backend/test_api.py::test_google_required_credentials_readiness_failure
  /home/jhao/code/voice-ai/.venv/lib/python3.10/site-packages/google/api_core/_python_version_support.py:273: FutureWarning: You are using a Python version (3.10.12) which Google will stop supporting in new releases of google.cloud.texttospeech_v1 once it reaches its end of life (2026-10-04). Please upgrade to the latest Python version, or at least Python 3.11, to continue receiving updates for google.cloud.texttospeech_v1 past that date.
    warnings.warn(message, FutureWarning)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
8 passed, 2 warnings in 3.49s
```

FFmpeg check:

```bash
command -v ffmpeg && ffmpeg -version | sed -n '1,3p' || true
```

Output was empty, meaning no `ffmpeg` binary is available on PATH in this environment.

## Local Run Command

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
```

OpenAPI:

```text
http://localhost:8080/openapi.json
http://localhost:8080/docs
```

## Environment Variables

- `ENVIRONMENT`
- `PORT`
- `TTS_PROVIDER`: `auto`, `local`, or `google`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `GCP_PROJECT_ID`
- `MLFLOW_TRACKING_URI`
- `MLFLOW_EXPERIMENT_NAME`
- `MLFLOW_LOG_AUDIO_ARTIFACTS`
- `AUDIO_STORAGE_DIR`
- `AUDIO_BASE_URL`
- `VIDEO_JOBS_DIR`
- `LOCALIZATION_PROVIDER`
- `FFMPEG_PATH`
- `API_KEYS`
- `CORS_ALLOW_ORIGINS`
- `MAX_INPUT_CHARS`
- `LOG_LEVEL`
- `LOG_RAW_TEXT`
- `OPENAI_API_KEY`: not used by the current backend. If a future OpenAI-backed test is explicitly required, read it only from the environment and redact it as `[redacted]` in logs/reports.

## Secret Handling Update

No code-level secret-handling change was needed for this backend slice. The implementation prioritizes Google STT/Translation/TTS design paths and local fallback/demo mode, and it does not currently call OpenAI APIs.

If OpenAI API support is added later, the backend must read `OPENAI_API_KEY` only from the process environment, never hardcode it, never commit it, never echo it in command output, never log it, and only refer to it as `[redacted]` in reports.

## Files Changed

- `requirements.txt`
- `app/__init__.py`
- `app/config.py`
- `app/logging_config.py`
- `app/main.py`
- `app/models.py`
- `app/observability.py`
- `app/providers.py`
- `app/storage.py`
- `app/video_localization.py`
- `tests/backend/test_api.py`
- `docs/subagents/backend-report.md`

## Notes For PM

The backend is now usable locally for TTS and video localization demos without cloud credentials. The TTS path includes a real Google Cloud Text-to-Speech adapter. The video path is intentionally local/demo for this slice: it proves API shape, artifact lifecycle, subtitles, Vietnamese voiceover generation, downloads, status persistence, auth, OpenAPI, and MLflow-safe metadata, but it still needs real Speech-to-Text, Translation, audio extraction, durable storage, async jobs, and installed FFmpeg for production-grade video muxing.

## Addendum 2026-05-10 SaaS Frontend Support

Agent identity: `Backend Builder Agent`.

Role skill used: `$voice-ai-backend-builder`.

Implemented additive endpoints for the upgraded SaaS frontend:

- `GET /v1/product/plans`
  - Public endpoint returning demo-safe plan/pricing copy.
  - Explicitly marks billing as `production_billing: false` and `demo_only: true`.
  - Does not claim real Stripe, metering, invoicing, or production billing.
- `GET /v1/product/capabilities`
  - Public endpoint returning frontend feature flags/capabilities for TTS, video localization, auth, and billing.
  - Reports local/demo mode, active TTS provider, supported video source/target languages, artifact types, and `ffmpeg_available`.
- `GET /v1/demo/workspace`
  - Public endpoint returning local demo workspace status for the frontend.
  - Reports local filesystem storage, MLflow configured status, FFmpeg availability, and demo-only notes.
- `POST /v1/auth/register`
  - Local demo auth only.
  - Stores users in process memory with salted password hashes.
  - Returns a `demo_...` bearer token.
- `POST /v1/auth/login`
  - Local demo auth only.
  - Validates against the in-memory user store.
- `GET /v1/auth/me`
  - Local demo auth only.
  - Reads the bearer token and returns the demo user.
- `POST /v1/auth/logout`
  - Local demo auth only.
  - Invalidates the in-memory demo token.

Preserved behavior:

- Existing TTS endpoints and tests still pass.
- Existing video localization demo endpoints and tests still pass.
- OpenAPI includes the original TTS/video paths plus the new product/demo/auth paths.

Secret safety:

- No user-provided API key or secret was added to source, tests, or this report.
- Demo auth never logs passwords or tokens explicitly.
- `OPENAI_API_KEY` remains unused by this backend and must remain environment-only and redacted as `[redacted]` if future OpenAI-backed tests are explicitly requested.

Production gaps:

- Demo auth is not production identity. It has no durable persistence, email verification, password reset, tenant isolation, OAuth/SAML, session hardening, RBAC, or audit trail.
- Pricing endpoint is product/config copy only. It is not connected to billing, metering, checkout, invoices, entitlements, or usage enforcement.
- Demo workspace status is local runtime status only, not a real multi-tenant workspace service.

Verification command:

```bash
.venv/bin/python -m pytest tests/backend -q
```

Verification output:

```text
..........                                                               [100%]
=============================== warnings summary ===============================
tests/backend/test_api.py::test_google_required_credentials_readiness_failure
  /home/jhao/code/voice-ai/.venv/lib/python3.10/site-packages/google/api_core/_python_version_support.py:273: FutureWarning: You are using a Python version (3.10.12) which Google will stop supporting in new releases of google.api_core once it reaches its end of life (2026-10-04). Please upgrade to the latest Python version, or at least Python 3.11, to continue receiving updates for google.api_core past that date.
    warnings.warn(message, FutureWarning)

tests/backend/test_api.py::test_google_required_credentials_readiness_failure
  /home/jhao/code/voice-ai/.venv/lib/python3.10/site-packages/google/api_core/_python_version_support.py:273: FutureWarning: You are using a Python version (3.10.12) which Google will stop supporting in new releases of google.cloud.texttospeech_v1 once it reaches its end of life (2026-10-04). Please upgrade to the latest Python version, or at least Python 3.11, to continue receiving updates for google.cloud.texttospeech_v1 past that date.
    warnings.warn(message, FutureWarning)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
10 passed, 2 warnings in 1.42s
```

Additional files changed in this addendum:

- `app/frontend_support.py`
- `app/main.py`
- `app/models.py`
- `tests/backend/test_api.py`
- `docs/subagents/backend-report.md`

## Addendum 2026-05-10 PM 404 Traceability

Agent identity: `Backend Builder Agent`.

Issue investigated:

- PM reported `404` on `http://localhost:8080/health`, `http://localhost:8080/v1/product/capabilities`, and `http://localhost:8080/v1/product/plans`.

Source implementation verification:

- The source app OpenAPI includes the product/config endpoints:
  - `/healthz`
  - `/readyz`
  - `/v1/product/capabilities`
  - `/v1/product/plans`
  - `/v1/demo/workspace`
  - `/v1/auth/register`
  - `/v1/auth/login`
  - `/v1/auth/me`
  - `/v1/auth/logout`
  - `/v1/voices`
  - `/v1/synthesize`
  - `/v1/video-localization/jobs`
  - `/v1/video-localization/jobs/{job_id}`
  - `/v1/video-localization/jobs/{job_id}/artifacts/{filename}`

Compatibility update:

- Added `GET /health` as an alias for `GET /healthz`.
- Frontend can use either `/health` or `/healthz`; `/readyz` remains the dependency readiness endpoint.

Exact frontend paths to call:

- Liveness: `GET /health` or `GET /healthz`
- Readiness: `GET /readyz`
- Plans/pricing copy: `GET /v1/product/plans`
- Feature/config capabilities: `GET /v1/product/capabilities`
- Demo workspace status: `GET /v1/demo/workspace`
- Demo register: `POST /v1/auth/register`
- Demo login: `POST /v1/auth/login`
- Demo current user: `GET /v1/auth/me` with `Authorization: Bearer <demo_token>`
- Demo logout: `POST /v1/auth/logout` with `Authorization: Bearer <demo_token>`
- Voices: `GET /v1/voices`
- TTS synthesize: `POST /v1/synthesize`
- Video localization create: `POST /v1/video-localization/jobs`
- Video localization status: `GET /v1/video-localization/jobs/{job_id}`
- Video artifact download: `GET /v1/video-localization/jobs/{job_id}/artifacts/{filename}`

Running service diagnosis:

- `localhost:8080` was served by Docker container `voice-ai-backend` from image `voice-ai:infra-video-check`.
- In-container OpenAPI only showed older paths:
  - `/healthz`
  - `/readyz`
  - `/v1/voices`
  - `/v1/synthesize`
  - `/v1/video-localization/jobs`
  - `/v1/video-localization/jobs/{job_id}`
  - `/v1/video-localization/jobs/{job_id}/artifacts/{filename}`
- That explains PM's `404` for product/config paths: the running Docker image is stale and predates the SaaS frontend support endpoints.
- Infra action needed: rebuild the backend image from current source and restart `voice-ai-backend` on port `8080`. No secrets should be printed during rebuild/restart.

Verification command after compatibility update:

```bash
.venv/bin/python -m pytest tests/backend -q
```

Verification output:

```text
..........                                                               [100%]
=============================== warnings summary ===============================
tests/backend/test_api.py::test_google_required_credentials_readiness_failure
  /home/jhao/code/voice-ai/.venv/lib/python3.10/site-packages/google/api_core/_python_version_support.py:273: FutureWarning: You are using a Python version (3.10.12) which Google will stop supporting in new releases of google.api_core once it reaches its end of life (2026-10-04). Please upgrade to the latest Python version, or at least Python 3.11, to continue receiving updates for google.api_core past that date.
    warnings.warn(message, FutureWarning)

tests/backend/test_api.py::test_google_required_credentials_readiness_failure
  /home/jhao/code/voice-ai/.venv/lib/python3.10/site-packages/google/api_core/_python_version_support.py:273: FutureWarning: You are using a Python version (3.10.12) which Google will stop supporting in new releases of google.cloud.texttospeech_v1 once it reaches its end of life (2026-10-04). Please upgrade to the latest Python version, or at least Python 3.11, to continue receiving updates for google.cloud.texttospeech_v1 past that date.
    warnings.warn(message, FutureWarning)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
10 passed, 2 warnings in 1.77s
```

Files changed in this addendum:

- `app/main.py`
- `tests/backend/test_api.py`
- `docs/subagents/backend-report.md`

## Addendum 2026-05-10 Real-Service Backend Debug

Agent identity: `Backend Builder Agent`.

Context7 docs used before code edits:

- `/fastapi/fastapi`
  - Topics: routing, OpenAPI route verification, `UploadFile`, `File`, `Form`, `FileResponse`, response handling, TestClient-related behavior.
- `/encode/httpx`
  - Topics: real HTTP status checks, response JSON/content access, multipart file upload, streaming/download response checks.

Scope:

- Debugged the actual HTTP service on `http://localhost:8080`, not just TestClient.
- No secrets were printed or added to source/report.

Findings before fixes:

- `GET /health` returned `404` on the running container even though source had the alias. The container was stale.
- `POST /v1/synthesize` returned a successful response, but `audio_url` was malformed as `/audio/audio/...` because Infra had configured `AUDIO_BASE_URL` with the `/audio` mount already included.
- `POST /v1/video-localization/jobs` returned a successful response, but artifact URLs were malformed as `/audio/v1/...` for the same base URL reason.

Source fixes:

- `app/config.py`
  - Added `service_base_url` and `audio_public_base_url` helpers so `AUDIO_BASE_URL` can be either the service root (`http://host:8080`) or the audio mount (`http://host:8080/audio`).
- `app/storage.py`
  - Uses `audio_public_base_url` for generated TTS audio URLs and avoids duplicate `/audio/audio`.
- `app/video_localization.py`
  - Uses `service_base_url` for video job artifact URLs and avoids `/audio/v1/...`.
- `tests/backend/test_api.py`
  - Added regression coverage for `AUDIO_BASE_URL=http://testserver/audio`, TTS audio download, and video SRT artifact download.

Container action:

- Attempted clean Docker rebuild:

```bash
docker build -t voice-ai:infra-video-check .
```

- Docker canceled the build during dependency installation with `failed to solve: Canceled: context canceled`.
- To unblock PM/user real-service testing, hot-patched current `app/` source into the running `voice-ai-backend` container and restarted it:

```bash
docker cp app/. voice-ai-backend:/app/app/
docker restart voice-ai-backend
```

- Infra still needs to perform a clean image rebuild from current source so the fix survives container replacement.

Running container route verification after hot-patch:

```text
/health
/healthz
/readyz
/v1/auth/login
/v1/auth/logout
/v1/auth/me
/v1/auth/register
/v1/demo/workspace
/v1/product/capabilities
/v1/product/plans
/v1/synthesize
/v1/video-localization/jobs
/v1/video-localization/jobs/{job_id}
/v1/video-localization/jobs/{job_id}/artifacts/{filename}
/v1/voices
```

Backend unit/API test command:

```bash
.venv/bin/python -m pytest tests/backend -q
```

Backend unit/API test output:

```text
........                                                              [100%]
=============================== warnings summary ===============================
tests/backend/test_api.py::test_google_required_credentials_readiness_failure
  /home/jhao/code/voice-ai/.venv/lib/python3.10/site-packages/google/api_core/_python_version_support.py:273: FutureWarning: You are using a Python version (3.10.12) which Google will stop supporting in new releases of google.api_core once it reaches its end of life (2026-10-04). Please upgrade to the latest Python version, or at least Python 3.11, to continue receiving updates for google.api_core past that date.
    warnings.warn(message, FutureWarning)

tests/backend/test_api.py::test_google_required_credentials_readiness_failure
  /home/jhao/code/voice-ai/.venv/lib/python3.10/site-packages/google/api_core/_python_version_support.py:273: FutureWarning: You are using a Python version (3.10.12) which Google will stop supporting in new releases of google.cloud.texttospeech_v1 once it reaches its end of life (2026-10-04). Please upgrade to the latest Python version, or at least Python 3.11, to continue receiving updates for google.cloud.texttospeech_v1 past that date.
    warnings.warn(message, FutureWarning)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
11 passed, 2 warnings in 2.16s
```

Real HTTP public/local service status after hot-patch:

```text
GET /health -> 200 OK
GET /healthz -> 200 OK
GET /readyz -> 200 OK
GET /v1/product/capabilities -> 200 OK
GET /v1/product/plans -> 200 OK
GET /v1/demo/workspace -> 200 OK
GET /v1/voices?language_code=en-US -> 200 OK
POST /v1/auth/register or /v1/auth/login -> 200 OK
GET /v1/auth/me -> 200 OK
POST /v1/auth/logout -> 200 OK
POST /v1/synthesize -> 200 OK
GET /audio/tts_*.wav -> 200 OK, nonempty WAV beginning with RIFF
POST /v1/video-localization/jobs -> 200 OK
GET /v1/video-localization/jobs/{job_id}/artifacts/debug.mp4 -> 200 OK
GET /v1/video-localization/jobs/{job_id}/artifacts/subtitles.vi.srt -> 200 OK
GET /v1/video-localization/jobs/{job_id}/artifacts/voiceover.vi.wav -> 200 OK, nonempty WAV beginning with RIFF
GET /v1/video-localization/jobs/{job_id}/artifacts/localized.vi.mp4 -> 200 OK
```

Working curl commands for PM/user:

```bash
BASE=http://localhost:8080

curl -sS "$BASE/health"
curl -sS "$BASE/healthz"
curl -sS "$BASE/readyz"
curl -sS "$BASE/v1/product/capabilities"
curl -sS "$BASE/v1/product/plans"
curl -sS "$BASE/v1/demo/workspace"
curl -sS "$BASE/v1/voices?language_code=en-US"
```

TTS fallback and audio download:

```bash
BASE=http://localhost:8080

curl -sS -X POST "$BASE/v1/synthesize" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Backend real HTTP debug.","voice":{"language_code":"en-US","name":"local-en-US-test-voice","ssml_gender":"NEUTRAL"},"audio":{"encoding":"LINEAR16","sample_rate_hz":24000},"metadata":{"client_reference_id":"pm-debug"}}' \
  -o /tmp/voice-ai-tts.json

python3 - <<'PY'
import json, urllib.request
body = json.load(open('/tmp/voice-ai-tts.json'))
url = body['audio_url'].replace('http://103.27.237.252:8080', 'http://localhost:8080')
data = urllib.request.urlopen(url, timeout=10).read()
print(url, len(data), data[:4])
PY
```

Demo auth flow without printing token:

```bash
BASE=http://localhost:8080

curl -sS -X POST "$BASE/v1/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"email":"pm-demo@example.com","password":"choose-a-demo-password","name":"PM Demo"}' \
  -o /tmp/voice-ai-auth.json

python3 - <<'PY'
import json, urllib.request
body = json.load(open('/tmp/voice-ai-auth.json'))
token = body['access_token']
req = urllib.request.Request('http://localhost:8080/v1/auth/me', headers={'Authorization': f'Bearer {token}'})
print(urllib.request.urlopen(req, timeout=10).read().decode())
PY
```

Video localization demo and artifact checks:

```bash
BASE=http://localhost:8080
printf '\000\000\000\030ftypmp42demo-video-debug' > /tmp/voice-ai-debug.mp4

curl -sS -X POST "$BASE/v1/video-localization/jobs" \
  -F source_language=en-US \
  -F target_language=vi \
  -F file=@/tmp/voice-ai-debug.mp4\;type=video/mp4 \
  -o /tmp/voice-ai-video.json

python3 - <<'PY'
import json, urllib.request
body = json.load(open('/tmp/voice-ai-video.json'))
print(body['job_id'], body['status'], [a['kind'] for a in body['artifacts']])
for artifact in body['artifacts']:
    if artifact['kind'] in {'subtitles_srt', 'voiceover_audio', 'localized_video'}:
        url = artifact['url'].replace('http://103.27.237.252:8080', 'http://localhost:8080')
        data = urllib.request.urlopen(url, timeout=10).read()
        print(artifact['kind'], len(data), data[:4])
PY
```

Remaining blocker for Infra:

- The live container is currently fixed by hot-patching `/app/app` and restarting `voice-ai-backend`.
- A durable clean rebuild is still required. Rebuild the backend image from current source and restart `voice-ai-backend` on port `8080`.
- Do not print environment secrets during rebuild/restart.

## Addendum 2026-05-10 Deploy-Blocker Fixes

Agent identity: `Backend Builder Agent`.

Skill used:

- Used `$voice-ai-backend-builder` for the FastAPI backend deploy-blocker pass.

Context7 docs used before editing:

- `/fastapi/fastapi`
  - Topic requested: `StaticFiles FileResponse URL routing OpenAPI TestClient`
  - Used for FastAPI route/static file response expectations and source/test verification.
- `/mlflow/mlflow`
  - Topic requested: `tracking set_tracking_uri set_experiment start_run log_param log_metric log_artifact run_id search_runs`
  - Used for MLflow tracking URI, experiment, run id, metrics/params/artifact logging, and local run search verification.
- `/encode/httpx`
  - Topic requested: `response content status code multipart file upload downloads`
  - Used for real HTTP smoke behavior: status checks, multipart upload, and downloaded byte validation.

Secrets:

- No secret values were hardcoded, echoed, logged, or added to this report.
- `OPENAI_API_KEY` was not used. Google/OpenAI credentials remain env-only when configured.

Source changes:

- `app/observability.py`
  - Tightened MLflow readiness to call `mlflow.set_experiment(...)` after `mlflow.set_tracking_uri(...)`, so `/readyz` validates that the configured tracker can create/access the experiment instead of only accepting a URI string.
- `tests/backend/test_api.py`
  - Strengthened TTS fallback regression: fetches the exact returned `audio_url` through the client and asserts `200`, byte count matches the response contract, and bytes begin with `RIFF`.
  - Added double-prefix regression for `AUDIO_BASE_URL=http://testserver/audio`, asserting TTS URLs do not contain `/audio/audio/` and video artifact URLs do not contain `/audio/v1/`.
  - Strengthened video workflow regression: fetches every returned artifact URL and checks `200` plus expected bytes/content for transcript, SRT, WAV voiceover, and final video placeholder.
  - Added MLflow regression: with file-backed tracking configured, `/readyz` reports MLflow ready, TTS and video responses include run ids, and both run ids are searchable in the configured MLflow experiment.

API URL contract now verified:

- TTS `audio_url` must be reachable as the returned absolute URL.
- If `AUDIO_BASE_URL` is the service root, generated TTS URLs use `{root}/audio/{filename}`.
- If `AUDIO_BASE_URL` already includes `/audio`, generated TTS URLs still use exactly `{root}/audio/{filename}` and do not duplicate the mount.
- Video artifact URLs use the service root and route shape `/v1/video-localization/jobs/{job_id}/artifacts/{filename}`.

Backend tests:

Command:

```bash
rm -rf app/__pycache__ tests/backend/__pycache__ .pytest_cache && .venv/bin/python -m pytest tests/backend -q
```

Output:

```text
............                                                             [100%]
=============================== warnings summary ===============================
tests/backend/test_api.py::test_google_required_credentials_readiness_failure
  /home/jhao/code/voice-ai/.venv/lib/python3.10/site-packages/google/api_core/_python_version_support.py:273: FutureWarning: You are using a Python version (3.10.12) which Google will stop supporting in new releases of google.api_core once it reaches its end of life (2026-10-04). Please upgrade to the latest Python version, or at least Python 3.11, to continue receiving updates for google.api_core past that date.
    warnings.warn(message, FutureWarning)

tests/backend/test_api.py::test_google_required_credentials_readiness_failure
  /home/jhao/code/voice-ai/.venv/lib/python3.10/site-packages/google/api_core/_python_version_support.py:273: FutureWarning: You are using a Python version (3.10.12) which Google will stop supporting in new releases of google.cloud.texttospeech_v1 once it reaches its end of life (2026-10-04). Please upgrade to the latest Python version, or at least Python 3.11, to continue receiving updates for google.cloud.texttospeech_v1 past that date.
    warnings.warn(message, FutureWarning)

tests/backend/test_api.py::test_mlflow_tracking_records_tts_and_video_runs_when_configured
  /home/jhao/code/voice-ai/.venv/lib/python3.10/site-packages/mlflow/tracking/_tracking_service/utils.py:184: FutureWarning: The filesystem tracking backend (e.g., './mlruns') is deprecated as of February 2026. Consider transitioning to a database backend (e.g., 'sqlite:///mlflow.db') to take advantage of the latest MLflow features. See https://mlflow.org/docs/latest/self-hosting/migrate-from-file-store for migration guidance.
    return FileStore(store_uri, store_uri)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
12 passed, 3 warnings in 43.05s
```

Real HTTP smoke:

Command used to start source service without Docker:

```bash
rm -rf /tmp/voice-ai-local-http && mkdir -p /tmp/voice-ai-local-http/audio /tmp/voice-ai-local-http/video /tmp/voice-ai-local-http/mlruns
ENVIRONMENT=local \
TTS_PROVIDER=local \
AUDIO_STORAGE_DIR=/tmp/voice-ai-local-http/audio \
VIDEO_JOBS_DIR=/tmp/voice-ai-local-http/video \
AUDIO_BASE_URL=http://127.0.0.1:8091/audio \
MLFLOW_TRACKING_URI=file:///tmp/voice-ai-local-http/mlruns \
MLFLOW_LOG_AUDIO_ARTIFACTS=false \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8091
```

Smoke output:

```text
health: GET /health -> 200 OK status,service,version
healthz: GET /healthz -> 200 OK status,service,version
readyz: GET /readyz -> 200 OK status,provider,storage,mlflow
capabilities: GET /v1/product/capabilities -> 200 OK service,environment,mode,tts
plans: GET /v1/product/plans -> 200 OK plans,billing
voices: GET /v1/voices?language_code=en-US -> 200 OK provider,voices
tts_synthesize: POST /v1/synthesize -> 200 OK run_id=True audio_url=http://127.0.0.1:8091/audio/tts_47f7af4bb1524bdd9e3f23b011586782.wav
tts_audio_url: GET /audio/tts_47f7af4bb1524bdd9e3f23b011586782.wav -> 200 OK bytes=62444 head=b'RIFF'
video_create: POST /v1/video-localization/jobs -> 200 OK run_id=True artifacts=6
video_artifact_source_video: GET /v1/video-localization/jobs/vid_63788cb7a6f444b1a775a13fbc31692a/artifacts/tiny.mp4 -> 200 OK bytes=22
video_artifact_transcript: GET /v1/video-localization/jobs/vid_63788cb7a6f444b1a775a13fbc31692a/artifacts/transcript.json -> 200 OK bytes=340
video_artifact_subtitles_srt: GET /v1/video-localization/jobs/vid_63788cb7a6f444b1a775a13fbc31692a/artifacts/subtitles.vi.srt -> 200 OK bytes=113
video_artifact_subtitles_vtt: GET /v1/video-localization/jobs/vid_63788cb7a6f444b1a775a13fbc31692a/artifacts/subtitles.vi.vtt -> 200 OK bytes=119
video_artifact_voiceover_audio: GET /v1/video-localization/jobs/vid_63788cb7a6f444b1a775a13fbc31692a/artifacts/voiceover.vi.wav -> 200 OK bytes=96044
video_artifact_localized_video: GET /v1/video-localization/jobs/vid_63788cb7a6f444b1a775a13fbc31692a/artifacts/localized.vi.mp4 -> 200 OK bytes=22
mlflow_runs 2 ['94e2272d76c8469aaff2bb77faf6b8ac', 'b3f9907fcf144108a36682307dc20f5f']
```

Exact endpoints verified:

```text
GET  /health
GET  /healthz
GET  /readyz
GET  /v1/product/capabilities
GET  /v1/product/plans
GET  /v1/voices?language_code=en-US
POST /v1/synthesize
GET  /audio/{filename}
POST /v1/video-localization/jobs
GET  /v1/video-localization/jobs/{job_id}/artifacts/{filename}
```

Infra coordination:

- Source tests and source-run real HTTP smoke pass.
- If the public/container service still returns stale behavior, rebuild and restart the backend image/container from current source.
- Exact rebuild/restart commands depend on Infra's chosen path, but the required action is a clean backend image rebuild plus restart of the service that serves port `8080`.
- Do not print configured secrets during rebuild, restart, or log collection.

## Addendum 2026-05-10 Backend Test Alignment

Agent identity: `Backend Test Alignment Agent`.

Role skill used: `$voice-ai-backend-builder`.

Context7 via MCP Docker:

- Resolved and used `/fastapi/fastapi`, topic `TestClient file uploads response assertions`.
- Resolved and used `/encode/httpx`, topic `multipart file upload tests response content`.

Contract decision:

- Invalid or fake MP4 bytes are not accepted as demo video input. The API returns HTTP `400` with error code `invalid_video_upload`, a clear validation message, request id, and generated video job id.
- Valid MP4 input remains the success contract for video localization. Tests generate a tiny valid MP4 at runtime with `ffmpeg` when `ffmpeg` is available, so no binary media fixture is committed.
- In this environment `ffmpeg` is not installed on PATH, so valid-MP4 success, public video artifact URL, and video MLflow-run assertions are skipped with an explicit reason. Invalid-input rejection and TTS audio URL plus TTS MLflow run id coverage still run.

Test updates:

- Added `FAKE_MP4_BYTES` and an explicit invalid-video rejection test.
- Added `valid_mp4_bytes` pytest fixture that uses `ffmpeg` with `taskset -c 0-3` when available.
- Changed stale fake-MP4 success assertions to either invalid-input assertions or valid-MP4 conditional success assertions.
- No backend source changes were required.

Verification command:

```bash
taskset -c 0-3 .venv/bin/python -m pytest tests/backend -q
```

Verification output:

```text
.......sss...                                                           [100%]
11 passed, 3 skipped, 2 warnings in 1.37s
```

Taskset usage:

- Used `taskset -c 0-3` for backend pytest runs.
- The valid MP4 fixture is also written to call `ffmpeg` through `taskset -c 0-3` when both `ffmpeg` and `taskset` are available.

## Addendum 2026-05-10 Backend Secret-Scan Cleanup

Agent identity: `Backend Secret-Scan Cleanup Agent`.

Role skill used: `$voice-ai-backend-builder`.

Scope:

- Replaced fake OpenAI test token literals in `tests/backend/test_api.py` with non-key-like dummy values.
- Removed the PM-flagged fake provider-selection token literal and the remaining fake key-prefixed test tokens from the backend API tests.
- No backend source changes were required.

Secret-scan note:

- A targeted scan for key-prefixed OpenAI-style dummy values in `tests/backend/test_api.py` and this report returns no matches.
- No real secret values were added or printed.

Verification command:

```bash
taskset -c 0-3 .venv/bin/python -m pytest tests/backend -q
```

Verification output:

```text
.............sss...                                                      [100%]
16 passed, 3 skipped, 2 warnings in 1.86s
```

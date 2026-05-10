# QA Public Runtime Acceptance - 2026-05-10

## Scope And Build Under Test

- Role: QA Acceptance Agent.
- Repo: `/home/jhao/code/voice-ai`.
- Public frontend tested: `http://103.27.237.252:4174/`.
- Public backend tested: `http://103.27.237.252:8080/`.
- Public MLflow tested: `http://103.27.237.252:5000/`.
- Local branch observed: `main`; task context said `wip/voice-ai-production-prototype`.
- Worktree had pre-existing uncommitted infra/runtime changes; no product code/config was modified.
- Report-only verification. Context7 was not applicable because no tests, code, or configs were modified.

## Result

Acceptance status: **FAIL for claiming backend works as production TTS/video localization**.

The public runtime is reachable and contract endpoints mostly work, but it is currently a local demo deployment:

- TTS provider is `local`, `fallback=true`, model `deterministic-wav-tone-demo`.
- Generated TTS audio is a 2-second WAV tone, not spoken Vietnamese.
- Video localization provider is `local`, `fallback=true`, model `deterministic-video-localization-demo`.
- Auth and billing/product endpoints are demo/local only.
- MLflow records are created internally, but public MLflow API access by IP returns `403 Invalid Host header`.

## Pass/Fail Matrix

| Area | Status | Evidence |
| --- | --- | --- |
| Frontend root loads | PASS | `GET http://103.27.237.252:4174/` returned 200 and served bundle `/assets/index-ByTxRiZ8.js`. |
| Frontend public API integration | PASS | Bundle derives public API as `http://<frontend-host>:8080`; for this host that resolves to `http://103.27.237.252:8080`. |
| Backend health | PASS | `/health` and `/healthz` returned 200 with `{"status":"ok","service":"voice-ai","version":"0.1.0"}`. |
| OpenAPI | PASS | `/openapi.json` returned 200, 12,285 bytes; paths include auth, product, voices, synthesize, and video localization. |
| Readiness | PARTIAL | `/readyz` returned `status=ready`, provider `local`, storage `local`, MLflow ready, video mode `local`, ffmpeg available. Ready is true for demo mode, not production provider readiness. |
| Voices | PARTIAL | `/v1/voices?language_code=vi-VN` returned one local voice: `local-vi-VN-test-voice`, provider `local`. |
| TTS synthesize contract | PASS | `/v1/synthesize` returned 200 with job `tts_e2fac1b26f154a74823e12ae9784bb7f`, request `req_eff071150c704b9ea0c6761c7b26cd48`. |
| TTS audio quality | FAIL | Response provider was `local`, fallback true, model `deterministic-wav-tone-demo`; artifact was 96,044-byte 2.0s mono WAV at 24 kHz, approximate tone frequency 267.75 Hz. This matches the user report that audio is only a beep/tone. |
| TTS validation errors | PASS | Invalid synthesize body returned 422 with structured `validation_error` details and request id. |
| Invalid video upload | PASS | JSON uploaded as `application/json` to `/v1/video-localization/jobs` returned 400 `unsupported_media_type`; logs recorded `video_localization_rejected` for invalid upload. |
| Valid video upload | PARTIAL | Valid MP4 upload returned 200 and six artifacts, job `vid_3abfd9d4524947ae8ebd17184e653b2a`, request `req_6eba83e6c56b407282bc811bfe1e09b9`. Provider is still local deterministic demo. |
| Final video artifact | PASS for demo artifact | Container `ffprobe` on localized MP4 showed h264 video, aac audio, mov_text subtitle, duration 2.0s, size 46,228 bytes. |
| Auth endpoints | PARTIAL | Register/login/me/logout work in local demo mode; `/v1/auth/me` without token returns 401 `missing_demo_token`. Auth response warns local demo only, not production identity. |
| Product endpoints | PARTIAL | Capabilities/plans returned 200 but advertise `environment=local`, `mode=demo`, billing unavailable, pricing copy only. |
| Logs | PARTIAL | Backend structured logs include route, request id, provider, status, latency. Some containers were recreated during testing, so older log history disappeared from current `docker logs`. |
| MLflow evidence | PARTIAL | Backend responses included MLflow run ids for current TTS/video. MLflow container logs showed run create/log/update calls. Public MLflow API by IP returned 403 `Invalid Host header`. |
| Provider/env status | FAIL for production | Container env status: `OPENAI_API_KEY=unset`, `GOOGLE_APPLICATION_CREDENTIALS=unset`, `MLFLOW_TRACKING_URI=set`, `TTS_PROVIDER=set`. No secret values were printed. |

## Commands Run And Results

- `curl -sS -D /tmp/qa-health.headers http://103.27.237.252:8080/health -o /tmp/qa-health.json`
  - Result: HTTP 200, service `voice-ai`, version `0.1.0`.
- `curl -sS -D /tmp/qa-openapi.headers http://103.27.237.252:8080/openapi.json -o /tmp/qa-openapi.json`
  - Result: HTTP 200, 12,285 bytes; endpoints included `/v1/synthesize`, `/v1/video-localization/jobs`, auth, product, readiness.
- `curl -sS -D /tmp/qa-frontend.headers http://103.27.237.252:4174/ -o /tmp/qa-frontend.html`
  - Result: HTTP 200, frontend HTML loaded `/assets/index-ByTxRiZ8.js`.
- `curl -sS http://103.27.237.252:4174/assets/index-ByTxRiZ8.js -o /tmp/qa-frontend-bundle.js`
  - Result: bundle logic maps non-local frontend host to `http://<host>:8080`, so public frontend points at public backend.
- `curl -sS http://103.27.237.252:8080/readyz`
  - Result: HTTP 200, ready with provider `local`, storage `local`, MLflow configured/ready, video localization mode `local`.
- `curl -sS 'http://103.27.237.252:8080/v1/voices?language_code=vi-VN'`
  - Result: provider `local`, one Vietnamese local test voice.
- `curl -sS -X POST http://103.27.237.252:8080/v1/synthesize ...`
  - Result: HTTP 200, current job `tts_e2fac1b26f154a74823e12ae9784bb7f`, provider `local`, model `deterministic-wav-tone-demo`, MLflow run `e1a1843c94ff4c7cb88ab2d7aa68b6b8`.
- `curl -sS "$audio_url" -o /tmp/qa-audio-current.wav` plus Python `wave` probe.
  - Result: WAV, 96,044 bytes, 2.0 seconds, mono, 24 kHz, RMS 8442, approximate tone frequency 267.75 Hz.
- `curl -sS -X POST http://103.27.237.252:8080/v1/synthesize` with invalid body.
  - Result: HTTP 422, structured validation errors for short `language_code` and `speaking_rate` over max.
- `curl -sS -X POST http://103.27.237.252:8080/v1/video-localization/jobs -F file=@/tmp/qa-synth.json;type=application/json`
  - Result: HTTP 400, `unsupported_media_type`, request id present.
- `curl -sS -X POST http://103.27.237.252:8080/v1/video-localization/jobs -F file=@docs/subagents/evidence/video/final-gate-valid-source-20260510.mp4;type=video/mp4 ...`
  - Result: HTTP 200, current job `vid_3abfd9d4524947ae8ebd17184e653b2a`, provider `local`, model `deterministic-video-localization-demo`, six artifacts, MLflow run `4b2e6df5fe574103b494f972f1fb0fd9`.
- `docker exec voice-ai-backend ffprobe ... /app/data/video-jobs/vid_3abfd9d4524947ae8ebd17184e653b2a/localized.vi.mp4`
  - Result: h264 video, aac audio, mov_text subtitle, duration 2.0s, size 46,228 bytes.
- `curl -sS http://103.27.237.252:8080/v1/product/capabilities` and `/v1/product/plans`
  - Result: HTTP 200, demo/local mode, local fallback true, production billing false.
- `curl -sS -X POST /v1/auth/register`, `GET /v1/auth/me`, `POST /v1/auth/logout`
  - Result: demo auth works with bearer token; unauthenticated `/me` returns 401. Token value omitted from this report.
- `docker logs --since 60s voice-ai-backend`
  - Result: structured log lines for current requests, including `synthesis_completed` and `video_localization_completed` with provider `local`.
- `docker logs --since 60s voice-ai-mlflow`
  - Result: MLflow run create/log-batch/update calls for run ids above.
- `curl -sS http://103.27.237.252:5000/api/3.0/mlflow/server-info`
  - Result: HTTP 403, `Invalid Host header - possible DNS rebinding attack detected`.

## Public URLs Tested

- `http://103.27.237.252:4174/`
- `http://103.27.237.252:4174/assets/index-ByTxRiZ8.js`
- `http://103.27.237.252:8080/health`
- `http://103.27.237.252:8080/healthz`
- `http://103.27.237.252:8080/readyz`
- `http://103.27.237.252:8080/openapi.json`
- `http://103.27.237.252:8080/v1/voices?language_code=vi-VN`
- `http://103.27.237.252:8080/v1/synthesize`
- `http://103.27.237.252:8080/v1/video-localization/jobs`
- `http://103.27.237.252:8080/v1/product/capabilities`
- `http://103.27.237.252:8080/v1/product/plans`
- `http://103.27.237.252:8080/v1/auth/register`
- `http://103.27.237.252:8080/v1/auth/me`
- `http://103.27.237.252:8080/v1/auth/logout`
- `http://103.27.237.252:5000/`
- `http://103.27.237.252:5000/api/3.0/mlflow/server-info`

## Defects

### P0 - TTS output is deterministic beep/tone, not speech

Repro:

1. POST to `http://103.27.237.252:8080/v1/synthesize` with Vietnamese text and `voice.name=local-vi-VN-test-voice`.
2. Download the returned `audio_url`.
3. Probe or play the WAV artifact.

Observed:

- Provider: `local`, `fallback=true`.
- Model: `deterministic-wav-tone-demo`.
- Artifact: 2.0s WAV tone, 96,044 bytes, mono 24 kHz.

Expected before claiming backend works:

- A real speech provider path should be active and ready, and generated audio should contain intelligible Vietnamese speech matching the input text.

### P0 - Production provider credentials are absent

Observed:

- Runtime readiness says active provider is `local`.
- Container env status: `OPENAI_API_KEY=unset`, `GOOGLE_APPLICATION_CREDENTIALS=unset`.

Expected before claiming backend works:

- Configure a real provider path and verify `/readyz`, `/v1/voices`, `/v1/synthesize`, and logs show the intended production provider, without exposing secret values.

### P1 - Video localization is local deterministic demo, not real STT/translation/dubbing

Repro:

1. Upload `docs/subagents/evidence/video/final-gate-valid-source-20260510.mp4` to `/v1/video-localization/jobs`.
2. Inspect response provider and generated transcript.

Observed:

- Provider: `local`, `fallback=true`, model `deterministic-video-localization-demo`.
- Transcript text is generated from file metadata: `Demo transcript from uploaded English video, 45596 bytes.`
- Vietnamese translation is demo text derived from that placeholder.

Expected before claiming video backend works:

- Real STT should transcribe media content, translation should be actual Vietnamese, dubbing should be speech, and artifacts should be generated from real media semantics.

### P1 - Public MLflow API is blocked by host validation

Repro:

1. `curl http://103.27.237.252:5000/api/3.0/mlflow/server-info`

Observed:

- HTTP 403: `Invalid Host header - possible DNS rebinding attack detected`.
- Internal backend-to-MLflow logging works and creates run ids, but public verification by IP is blocked.

Expected before claiming observability works publicly:

- Either document that MLflow is internal-only, or configure allowed hosts/proxy access for the intended public observability endpoint.

### P2 - Runtime containers were recreated during acceptance

Observed:

- `docker ps` showed backend/MLflow age reset during the pass.
- `docker inspect` after recreation showed restart count `0`, started at `2026-05-10T08:08:54Z`.
- Older `docker logs` evidence disappeared because the container instances changed.

Expected before release readiness:

- Stabilize service lifecycle and preserve logs through container recreation, or route logs to durable aggregation.

### P2 - Product/auth endpoints are explicitly demo-only

Observed:

- `/v1/product/capabilities` reports `environment=local`, `mode=demo`, billing unavailable.
- `/v1/product/plans` returns demo-only plans.
- Auth responses warn local demo identity only.

Expected before production claim:

- Real identity and billing/product state must replace demo endpoints, or UI/API copy must clearly present this as a demo.

## What Must Be Fixed Before Claiming Backend Works

1. Activate and verify a real TTS provider. Current `/v1/synthesize` proves only deterministic local tone generation.
2. Ensure generated audio is intelligible speech, not a fixed WAV tone; add an acceptance check that fails on `deterministic-wav-tone-demo`.
3. Activate real video localization dependencies or clearly mark the video backend as demo. Current transcript/translation/dub artifacts are deterministic placeholders.
4. Decide MLflow exposure model. If public, fix Host header/allowed-host config; if internal-only, document the verification path.
5. Stabilize runtime lifecycle and log retention so acceptance evidence is not lost when containers are recreated.
6. Replace or clearly gate demo-only auth, product, and billing endpoints before any production claim.

## Residual Risk

- No external docs or current provider behavior were checked because this pass focused on deployed runtime behavior and did not modify tests/code.
- Browser-driven E2E was not run; frontend integration was verified by HTTP load and bundle inspection.
- Public runtime may continue changing because containers were recreated during the acceptance window.

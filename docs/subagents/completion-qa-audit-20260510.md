# Completion QA Acceptance Audit - 2026-05-10

Role: QA Acceptance Auditor  
Skill used: `voice-ai-qa-acceptance`  
Repo: `/home/jhao/code/voice-ai`  
Build under test: `main` at latest commit `9cd8d36` with local branch `main...origin/main [ahead 8]`  
Public frontend: `http://103.27.237.252:4174/`  
Public backend: `http://103.27.237.252:8080/`  
MLflow: local `http://127.0.0.1:5000/`; public IP `:5000` returned 403 host validation  
Evidence directory: `docs/subagents/evidence/qa-audit-20260510/`

Context7 was not applicable because this audit did not modify app code, tests, fixtures, or scripts. Official/current docs checked with built-in web search: OpenAI TTS, OpenAI STT, Cloud Run secrets/environment variables, and MLflow Tracking.

## Official Source Checks

- OpenAI TTS docs: Audio API has a speech endpoint using `gpt-4o-mini-tts`; request inputs are model, text, and voice; OpenAI lists `marin` and `cedar`; WAV is a supported output format. Source: https://platform.openai.com/docs/guides/text-to-speech
- OpenAI STT docs: file upload transcription supports `mp4` and other audio/video formats with a 25 MB upload limit. Source: https://platform.openai.com/docs/guides/speech-to-text
- Cloud Run docs: secrets should be made accessible through Secret Manager as environment variables or volumes, and env changes create revisions. Sources: https://cloud.google.com/run/docs/configuring/services/secrets and https://cloud.google.com/run/docs/configuring/services/environment-variables
- MLflow docs: Tracking records runs with metadata, params, metrics, and artifacts. Source: https://www.mlflow.org/docs/latest/ml/tracking

## Acceptance Matrix

| Area | Status | Evidence | Notes |
| --- | --- | --- | --- |
| Public frontend URL | Pass | `frontend.headers.txt`, `frontend.html`, `frontend-browser-snapshot.json`, `frontend-desktop.png` | HTTP 200, title `Voice AI Production Studio`, default backend `http://103.27.237.252:8080`, no Playwright page/console errors. |
| Backend health/readiness | Pass | `healthz.json`, `readyz.json` | `/healthz` OK. `/readyz` ready with provider `openai`, local storage ready, MLflow ready, FFmpeg available. |
| Voice catalog | Pass | `voices.json` | Provider `openai`; includes `marin`, `cedar`, and other current OpenAI voices. |
| TTS real OpenAI voice | Pass | `tts-openai.json` | `job_id=tts_5c33346a5bdc4e4bb4af05a94f69556d`, provider `openai`, fallback `false`, model `gpt-4o-mini-tts`, voice `marin`, MLflow run `39faf7e1228045279c61b2327e3a71bb`. |
| Audio artifact download/playability | Pass | `tts-openai.wav`, `tts-openai-ffprobe.json`, `tts-audio.headers.txt` | 348,044-byte RIFF/WAV, PCM 16-bit mono, 24 kHz, duration 7.25s. |
| English-to-Vietnamese video localization | Pass | `video-english.json`, `video-english-transcript.json`, `video-english-ffprobe.json`, downloaded SRT/VTT/WAV/MP4 files | OpenAI path, fallback `false`, transcript and Vietnamese translation present, voiceover WAV and localized MP4 produced. Final MP4 has H.264 video, AAC audio, mov_text subtitle. |
| Chinese-to-Vietnamese video localization | Pass | `tts-chinese-source.json`, `chinese-source.mp4`, `video-chinese.json`, `video-chinese-transcript.json`, `video-chinese-ffprobe.json`, downloaded SRT/VTT/WAV/MP4 files | Generated Chinese source video for audit, then localized via OpenAI path. Transcript Chinese and Vietnamese translation present. Final MP4 has H.264 video, AAC audio, mov_text subtitle. |
| Auth/register/login | Pass | `auth-register-redacted.json`, `auth-login-redacted.json`, `auth-me.json`, `auth-logout.json` | Register/login/me/logout worked. Evidence redacts bearer tokens and records only token presence. |
| Billing disabled when Stripe missing | Pass | `capabilities.json`, `billing-plans.json`, `billing-checkout.json`, `billing-checkout-status.txt` | Capabilities report billing unavailable and production billing false. Checkout returns HTTP 503 `billing_not_configured`. Frontend disables checkout buttons. |
| MLflow run evidence | Pass for local/internal tracking | `mlflow-runs-summary.json`, `mlflow-local-server-info.txt` | Local MLflow API returned HTTP 200. TTS, English video, and Chinese video runs are `FINISHED` with provider/job/request tags, params, metrics, success=1. |
| Public MLflow access | Blocked/expected internal-only | `mlflow-public-server-info.txt`, `mlflow-public.headers.txt` | Public IP `:5000` returned HTTP 403 `Invalid Host header`. This is acceptable only if MLflow is intentionally internal-only. |
| Structured log evidence | Pass | `backend-structured-logs.txt` | Logs include request id, route, method, status, latency, provider/job metadata for TTS and video. No raw TTS text or transcript content observed in captured structured logs. |
| Docker/runtime status | Pass for local prototype | `runtime-status.txt`, `docker-ps.txt`, `docker-compose-config.txt` | Backend container healthy, MLflow container running, frontend preview active, compose config exit code 0. OpenAI env is set; Google credentials are unset. |
| Cloud Run/deploy readiness | Blocked for production proof | `gcloud-command.txt`, deploy docs/templates reviewed | `gcloud_not_found`; no live Cloud Run revision, Artifact Registry digest, GCS object, Secret Manager proof, Cloud Tasks/job proof, or rollback evidence captured. Templates and runbook exist. |
| E2E/unit/backend test evidence | Pass | `pytest-backend-pythonpath.txt`, `frontend-lint.txt`, `frontend-unit.txt`, `frontend-build.txt`, `frontend-e2e.txt` | Backend: 30 passed, 3 skipped, 2 warnings with `PYTHONPATH=.`. Frontend lint passed, unit 4 passed, build passed, Playwright E2E 12 passed with existing `LD_LIBRARY_PATH` browser dependency workaround. |
| Privacy/secret scan evidence | Pass with false-positive caveat | `literal-secret-scan-tracked-files.json`, `secret-scan-tracked-files.json` | Literal scan of 152 tracked files found 0 OpenAI/Stripe/private-key literals. Broader assignment scan found only redacted/placeholders/references and test values. |
| Product API validation behavior | Fail | `tts-openai-error.json`, `tts-openai-error.headers.txt`, `backend-structured-logs.txt` | Malformed nested synth input returned HTTP 500 because validation errors include a non-JSON-serializable `ValueError`. Expected structured 422. |

## Commands Run

```bash
curl -fsS http://103.27.237.252:4174/
curl -fsS http://103.27.237.252:8080/healthz
curl -fsS http://103.27.237.252:8080/readyz
curl -fsS 'http://103.27.237.252:8080/v1/voices?language_code=vi-VN'
curl -fsS http://103.27.237.252:8080/v1/product/capabilities
curl -fsS -X POST http://103.27.237.252:8080/v1/synthesize ...
curl -fsS "$AUDIO_URL" -o tts-openai.wav
docker exec voice-ai-backend ffprobe ... /app/data/audio/tts_5c33346a5bdc4e4bb4af05a94f69556d.wav
curl -fsS -X POST http://103.27.237.252:8080/v1/video-localization/jobs -F file=@/tmp/voice-ai-video-speech/source-speaking.mp4 ...
curl -fsS -X POST http://103.27.237.252:8080/v1/video-localization/jobs -F file=@docs/subagents/evidence/qa-audit-20260510/chinese-source.mp4 ...
docker exec voice-ai-backend ffprobe ... localized.vi.mp4
curl -fsS -X POST http://103.27.237.252:8080/v1/auth/register ...
curl -fsS -X POST http://103.27.237.252:8080/v1/auth/login ...
curl -fsS http://103.27.237.252:8080/v1/billing/subscription
curl -sS -X POST http://103.27.237.252:8080/v1/billing/checkout-session ...
PYTHONPATH=. .venv/bin/python - <<'PY'  # MLflow run lookup
taskset -c 0-3 env PYTHONPATH=. .venv/bin/pytest tests/backend/test_api.py
taskset -c 0-3 npm run lint
taskset -c 0-3 npm test
taskset -c 0-3 npm run build
taskset -c 0-3 env LD_LIBRARY_PATH=/tmp/voice-ai-browser-deps/extracted/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH npm run test:e2e -- --reporter=line
./scripts/local-services.sh status
docker ps --format ...
docker compose config --quiet
git status --short --branch
```

Concise results are in the evidence files. One initial backend test command without `PYTHONPATH=.` failed collection with `ModuleNotFoundError: No module named 'app'`; the corrected command passed and both outputs are preserved.

## Defects

| Severity | Defect | Reproduction | Impact |
| --- | --- | --- | --- |
| P1 | Malformed synth payload returns HTTP 500 instead of structured 422. | POST `/v1/synthesize` with nested `{"input":{"text":"..."}}` shape. | Public API error contract is not robust; backend logs traceback. |
| P1 | Production deploy proof is missing. | `gcloud` is unavailable; no Cloud Run/GCS/Secret Manager/Cloud Tasks/live rollback evidence. | Cannot certify commercial production release against PM release criteria. |
| P1 | Runtime artifacts are served from local `/app/data/...`. | TTS/video responses include local `audio_path`/artifact paths; storage mode is local. | Prototype works, but production durability/access-control proof is absent. |
| P2 | Public MLflow endpoint rejects by host validation. | `curl http://103.27.237.252:5000/api/3.0/mlflow/server-info` returns 403. | Fine for internal-only MLflow, but public observability is not available. |
| P2 | API docs are partly stale. | `docs/api-contract.md` still describes `/v1/videos` and `/v1/localization-jobs`; OpenAPI exposes `/v1/video-localization/jobs`. | Integrators may follow outdated endpoint names. |

## Blockers And Missing Credentials

- `gcloud` is not installed/available in this session, so Cloud Run deploy/readback, Secret Manager readback, GCS object proof, and rollback proof are blocked.
- `GOOGLE_APPLICATION_CREDENTIALS` is unset by runtime status; current product path is OpenAI-backed, not Google Speech/Translation/TTS.
- Stripe secrets are absent by design; billing checkout correctly returns `billing_not_configured`.
- GitHub publication remains blocked outside this audit scope: branch is ahead of origin and this session has no GitHub push credentials.

## Residual Risk

- The public product is a user-testable prototype running on a Vite preview frontend plus Docker/tmux backend services, not a Cloud Run production deployment.
- Auth works, but runtime capability reports `production_identity=true` while storage is SQLite; production identity durability, tenant isolation, quota, and key lifecycle still need deployment-grade proof.
- MLflow run metadata is present and privacy-safe in sampled runs, but production retention/access policy and public/internal observability policy remain undecided.
- Video tests used short synthetic samples. Long videos, background processing, retries, cancellation, quota/rate-limit handling, and storage lifecycle were not proven live.
- Tracked-file secret scan found no literal secrets, but it does not inspect untracked `.env` or external secret stores.

## Final Recommendation

**Complete only with accepted risks for controlled public prototype testing.** The public frontend, real OpenAI TTS, audio download/playback, English and Chinese video localization, auth flow, billing-disabled behavior, MLflow tracking, structured logs, Docker runtime, and automated tests all have fresh evidence.

**Not complete for commercial production release.** Production acceptance remains blocked by missing Cloud Run/GCS/Secret Manager/Cloud Tasks/rollback proof, local storage, absent Stripe billing, public/internal observability decision, and the P1 validation error-contract defect.

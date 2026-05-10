# QA Acceptance Report

Date: 2026-05-10T14:59:00+07:00

Scope: final gate for `/home/jhao/code/voice-ai` against:

- Public frontend: `http://103.27.237.252:4174`
- Public backend: `http://103.27.237.252:8080`
- Local automated test and Docker/infra checks

Result: **Not deploy-ready**. Public frontend, backend discovery endpoints, local fallback TTS audio, valid-MP4 demo localization, automated tests, and compose validation pass. Release is blocked because successful public TTS/video responses still have `mlflow_run_id: null`, fake MP4 upload is accepted as a successful video job, and the product remains local/demo mode rather than production Google STT/Translation/TTS.

## Context7 / MCP Docker

- No tests, fixtures, scripts, or app code were modified in this QA pass, so Context7 was not required for implementation.
- Evidence-only files were written under `docs/subagents/`.

## Runtime Constraint

- Used `taskset -c 0-3` for CPU-heavy/repeated work where feasible: backend pytest, frontend lint/unit/build, Playwright screenshots/checks/E2E, Docker FFmpeg fixture generation, and Docker FFprobe validation.
- Simple `curl`, `jq`, `file`, `wc`, `docker compose config --quiet`, and `./scripts/local-services.sh status` checks were not CPU-heavy and were run without `taskset`.

## Acceptance Matrix

| Area | Status | Evidence |
| --- | --- | --- |
| Public frontend load | Pass | Desktop/mobile screenshots captured: `docs/subagents/evidence/images/final-gate-public-desktop-20260510.png`, `docs/subagents/evidence/images/final-gate-public-mobile-20260510.png`. First viewport shows the prototype studio and video workflow heading. |
| Frontend runtime errors | Pass | `docs/subagents/evidence/api/final-gate-frontend-browser-check-20260510.json`: no page errors, no console errors, no `crypto.randomUUID` errors on desktop or mobile. |
| Frontend default API | Pass | Browser check found `#base-url` value `http://103.27.237.252:8080` on desktop and mobile, not localhost. |
| Public backend health/readiness | Pass | `/health`, `/healthz`, `/readyz` returned HTTP 200. Readiness reports local provider/storage ready, MLflow configured/ready, video localization ready, and FFmpeg available. |
| Public voices/capabilities/plans | Pass | `/v1/voices?language_code=vi-VN`, `/v1/product/capabilities`, and `/v1/product/plans` returned HTTP 200. Capabilities mode is `demo`; plans are `demo-free` and `starter-placeholder`. |
| Public TTS | Fail for final gate | `POST /v1/synthesize` returned HTTP 200 and a valid RIFF/WAV download, but `observability.mlflow_run_id` was `null`. Warning: MLflow `/api/2.0/mlflow/experiments/get-by-name` returned 403 `Invalid Host header`. |
| Audio artifact | Pass | `docs/subagents/evidence/audio/final-gate-tts-audio-20260510.wav`, 96,044 bytes, RIFF/WAVE PCM mono 24 kHz. |
| Fake MP4 rejection | Fail | `docs/subagents/evidence/api/final-gate-video-fake-response-20260510.txt`: 23-byte text file uploaded as `video/mp4` returned HTTP 200 `status: succeeded` instead of a clear validation error. |
| Valid MP4 localization | Partial pass | Generated a 2s valid MP4 fixture with Docker FFmpeg. Public video job succeeded and artifacts downloaded: SRT, VTT, transcript, WAV, final MP4. `ffprobe` shows final MP4 has H.264 video, AAC audio, and mov_text subtitle streams. MLflow run id is still null and provider is local demo fallback. |
| Automated backend tests | Pass | `taskset -c 0-3 .venv/bin/python -m pytest tests/backend -q`: 11 passed, 3 skipped, 2 warnings. |
| Frontend lint/unit/build | Pass | `taskset -c 0-3 npm run lint`, `npm test`, and `npm run build` passed. |
| Playwright desktop/mobile | Pass | With LD_LIBRARY_PATH browser workaround and `taskset -c 0-3`, desktop E2E: 2 passed; mobile E2E: 2 passed. |
| Docker/infra status | Pass with caveat | `./scripts/local-services.sh status` shows tmux sessions up, backend `voice-ai:durable-20260510` healthy on 8080, frontend preview on 4174, MLflow container on 5000. `docker compose config --quiet` passed. Caveat: runtime MLflow API calls from app still fail host validation. |
| Production Google STT/Translation/TTS | Blocked | No Google-backed staging evidence or credentials were available. Public service is local/demo fallback. |
| Durable production storage | Blocked | Public API returns local `/app/data/...` artifact paths; no bucket/object/signed URL evidence. |

## Key Commands

```bash
./scripts/local-services.sh status
docker compose config --quiet
curl -sS http://103.27.237.252:8080/health
curl -sS http://103.27.237.252:8080/healthz
curl -sS http://103.27.237.252:8080/readyz
curl -sS http://103.27.237.252:8080/v1/product/capabilities
curl -sS http://103.27.237.252:8080/v1/product/plans
curl -sS 'http://103.27.237.252:8080/v1/voices?language_code=vi-VN'
curl -sS -H 'Content-Type: application/json' -H 'X-Request-ID: qa_final_gate_tts_20260510' --data @/tmp/final-gate-tts-payload.json http://103.27.237.252:8080/v1/synthesize
curl -sS -F 'file=@docs/subagents/evidence/video/final-gate-fake-20260510.mp4;type=video/mp4;filename=fake.mp4' -F 'source_language=en-US' -F 'target_language=vi' http://103.27.237.252:8080/v1/video-localization/jobs
taskset -c 0-3 docker run --rm --entrypoint ffmpeg -v /home/jhao/code/voice-ai/docs/subagents:/out voice-ai:durable-20260510 ...
curl -sS -F 'file=@docs/subagents/evidence/video/final-gate-valid-source-20260510.mp4;type=video/mp4;filename=valid-source.mp4' -F 'source_language=en-US' -F 'target_language=vi' http://103.27.237.252:8080/v1/video-localization/jobs
taskset -c 0-3 docker run --rm --entrypoint ffprobe -v /home/jhao/code/voice-ai/docs/subagents:/out voice-ai:durable-20260510 ...
taskset -c 0-3 .venv/bin/python -m pytest tests/backend -q
taskset -c 0-3 npm run lint
taskset -c 0-3 npm test
taskset -c 0-3 npm run build
taskset -c 0-3 env LD_LIBRARY_PATH=/tmp/voice-ai-browser-deps/extracted/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH npm run test:e2e -- --project=desktop --reporter=line
taskset -c 0-3 env LD_LIBRARY_PATH=/tmp/voice-ai-browser-deps/extracted/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH npm run test:e2e -- --project=mobile --reporter=line
```

## Evidence Files

- `docs/subagents/evidence/api/final-gate-health-20260510.txt`
- `docs/subagents/evidence/api/final-gate-healthz-20260510.txt`
- `docs/subagents/evidence/api/final-gate-readyz-20260510.txt`
- `docs/subagents/evidence/api/final-gate-capabilities-20260510.txt`
- `docs/subagents/evidence/api/final-gate-plans-20260510.txt`
- `docs/subagents/evidence/api/final-gate-voices-20260510.txt`
- `docs/subagents/evidence/api/final-gate-tts-response-20260510.txt`
- `docs/subagents/evidence/audio/final-gate-tts-audio-20260510.wav`
- `docs/subagents/evidence/api/final-gate-video-fake-response-20260510.txt`
- `docs/subagents/evidence/video/final-gate-valid-source-20260510.mp4`
- `docs/subagents/evidence/api/final-gate-video-valid-response-20260510.txt`
- `docs/subagents/evidence/api/final-gate-video-transcript-20260510.json`
- `docs/subagents/evidence/video/final-gate-video-subtitles-20260510.srt`
- `docs/subagents/evidence/video/final-gate-video-subtitles-20260510.vtt`
- `docs/subagents/evidence/audio/final-gate-video-voiceover-20260510.wav`
- `docs/subagents/evidence/video/final-gate-video-localized-20260510.mp4`
- `docs/subagents/evidence/api/final-gate-video-ffprobe-20260510.json`
- `docs/subagents/evidence/images/final-gate-public-desktop-20260510.png`
- `docs/subagents/evidence/images/final-gate-public-mobile-20260510.png`
- `docs/subagents/evidence/api/final-gate-frontend-browser-check-20260510.json`

## Defects

1. **P1: Public MLflow tracking fails for successful TTS and video jobs.**
   - Repro: public `POST /v1/synthesize` or valid public `POST /v1/video-localization/jobs`.
   - Evidence: both responses have `observability.mlflow_run_id: null`; warning says MLflow endpoint returns 403 `Invalid Host header`.
   - Impact: required final-gate criterion `mlflow_run_id present` fails.

2. **P1: Invalid/fake MP4 is accepted as a successful localization job.**
   - Repro: upload `docs/subagents/evidence/video/final-gate-fake-20260510.mp4`, a 23-byte text file, as `video/mp4`.
   - Evidence: backend returned HTTP 200 with `status: succeeded`, generated subtitle/audio artifacts, and copied the fake upload as `localized.vi.mp4`.
   - Impact: upload validation is not reliable and fake media does not fail clearly.

3. **P2: Public workflow is still demo/local provider mode.**
   - Evidence: capabilities mode is `demo`; TTS/video provider is local fallback; plans are demo placeholders.
   - Impact: acceptable for prototype demos only, not production-grade Google STT/Translation/TTS release.

## Decision

**Not deploy-ready.** Core prototype smoke is much stronger after the latest runtime state, including passing desktop/mobile Playwright and valid MP4 muxing. Final gate still fails because MLflow run IDs are missing, fake MP4 uploads are accepted, and production Google STT/Translation/TTS remains unproven.

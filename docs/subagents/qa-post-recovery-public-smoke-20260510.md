# QA Post-Recovery Public Smoke - 2026-05-10

Role: QA Acceptance - Post Recovery Public Smoke  
Build under test: commit `f2ba690ea43d4c7b5899e04aea757c266ce4d9be`  
Frontend: `http://103.27.237.252:4174/`  
Backend: `http://103.27.237.252:8080/`  
Mode: read-only runtime audit, no product code or deployment files changed.

Context7: not applicable. This pass did not modify tests, fixtures, scripts, app code, or library usage.

## Result

Overall status: **BLOCKED for final production claim**.

The recovered public runtime is serving the redesigned frontend shell and a fresh OpenAI TTS job succeeds with downloadable WAV audio. Production acceptance remains blocked by missing visual screenshot evidence, MLflow artifact permission warnings, active unrelated build/apt processes on the host, local host runtime/storage, `ffmpeg_available=false`, disabled billing, and absent Cloud Run/GCS/Secret Manager/Cloud Tasks evidence.

## Acceptance Matrix

| Check | Status | Evidence |
| --- | --- | --- |
| Public frontend loads | PASS | `GET /` returned 200. HTML title is `Voice AI Localization Studio`; assets are `assets/index-CPkM3X2O.js` and `assets/index-BSQREeFd.css`. |
| Redesigned product shell visible | PARTIAL | Bundle contains the redesigned studio shell markers such as `studio-shell`, `Voice studio workspace`, workflow tabs, TTS and video localization UI. Browser screenshot capture was blocked by missing Chromium dependency `libgbm.so.1`. |
| Desktop/mobile screenshots | BLOCKED | Playwright Chromium launched but exited with `error while loading shared libraries: libgbm.so.1`; Firefox browser was not installed. No screenshot files were produced. |
| Forbidden body strings | PASS | Frontend HTML body had no hits for `Starter Placeholder`, `pricing-copy-only`, `local-demo`, `Public studio workspace`, `Prototype workspace`, `Session console`, `Checkout disabled`. |
| `/healthz` | PASS | HTTP 200: `{"status":"ok","service":"voice-ai","version":"0.1.0"}`. |
| `/readyz` | PASS with caveats | HTTP 200 ready. Provider `openai` ready, storage `local` ready, MLflow ready, video mode `auto`, provider `openai`, `ffmpeg_available=false`. |
| `/v1/product/capabilities` | PASS with blockers | HTTP 200. Environment `public`, TTS active provider `openai`, video demo mode false, billing unavailable, auth not production identity. |
| Fresh public TTS job | PASS with observability warning | Job `tts_96f69f5b43ab4bbfb311a6b812886fb3`, provider `openai`, fallback `false`, model `gpt-4o-mini-tts`. |
| TTS audio artifact | PASS | `HEAD` audio URL returned HTTP 200, `content-type: audio/x-wav`, `content-length: 331244`. File probe: RIFF/WAVE PCM 16-bit mono 24000 Hz, actual data duration about 6.9s. |
| MLflow health | PASS | `GET http://127.0.0.1:5000/health` returned `OK`. |
| MLflow run id on TTS | FAIL | TTS response had `observability.mlflow_run_id=null` and warning `MLflow tracking failed: [Errno 13] Permission denied: '/mlflow'`. |
| Process cleanliness | FAIL | Active unrelated `docker build` and `apt-get update` processes were present. |
| Docker/disk summary | PARTIAL | `docker system df`: Images 1.991GB, containers 1.511MB, build cache 54.77MB. `/` has 16G free, 66% used. Backend is host `.venv` uvicorn, not a backend container. |

## Commands And Results

```bash
git rev-parse HEAD
git status --short --branch
```

Result: current HEAD is `f2ba690ea43d4c7b5899e04aea757c266ce4d9be`; branch status `## main...origin/main`.

```bash
curl -fsS -D frontend.headers.txt http://103.27.237.252:4174/ -o frontend.html
rg -n 'Starter Placeholder|pricing-copy-only|local-demo|Public studio workspace|Prototype workspace|Session console|Checkout disabled' frontend.html
```

Result: HTTP 200; title `Voice AI Localization Studio`; assets `index-CPkM3X2O.js` and `index-BSQREeFd.css`; no forbidden body string hits.

```bash
curl -fsS http://103.27.237.252:8080/healthz
curl -fsS http://103.27.237.252:8080/readyz
curl -fsS http://103.27.237.252:8080/v1/product/capabilities
```

Result: all returned HTTP 200. `/readyz` reports provider `openai`, storage `local`, MLflow ready, video provider `openai`, and `ffmpeg_available=false`. Capabilities report billing `available=false`, `production_billing=false`, auth `production_identity=false`.

```bash
curl -fsS -H 'Content-Type: application/json' \
  --data-binary @/tmp/qa-post-tts-payload.json \
  http://103.27.237.252:8080/v1/synthesize
```

Result: job `tts_96f69f5b43ab4bbfb311a6b812886fb3`, status `succeeded`, provider `openai`, fallback `false`, model `gpt-4o-mini-tts`, request id `req_6d6001430ef3433a9a722b32f5df2315`.

Audio URL:

`http://103.27.237.252:8080/audio/tts_96f69f5b43ab4bbfb311a6b812886fb3.wav`

```bash
curl -fsSI "$AUDIO_URL"
file tts-audio.wav
python3 riff_probe.py
```

Result: HTTP 200, `content-length: 331244`, `content-type: audio/x-wav`; RIFF/WAVE PCM, 16-bit mono, 24000 Hz, actual data bytes `331200`, approximate duration `6.9s`.

```bash
curl -fsS http://127.0.0.1:5000/health
```

Result: `OK`.

```bash
taskset -c 0-3 npx playwright screenshot --browser=chromium --viewport-size=1440,1000 \
  http://103.27.237.252:4174/ docs/subagents/evidence/images/qa-post-recovery-public-smoke-desktop-20260510.png
```

Result: failed before page capture because Chromium headless shell could not load `libgbm.so.1`. Firefox screenshot attempt also failed because the Playwright Firefox executable was not installed.

```bash
ps -eo pid,ppid,stat,etime,cmd | rg -i '[d]ocker build|[a]pt-get|[p]ip( |$)|[n]pm install|[p]laywright install'
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker system df
df -h /
```

Result: active unrelated `docker build` and `apt-get update` processes were present. Docker had `voice-ai-mlflow` plus an unrelated `python:3.10-slim-bookworm` container. Backend listener was host `uvicorn` PID `26096` on `:8080`, frontend Vite preview PID `12534` on `:4174`, MLflow container on `:5000`.

## Evidence Paths

- Raw smoke evidence directory: `docs/subagents/evidence/qa-post-recovery-public-smoke-20260510/`
- Screenshot attempt log: `docs/subagents/evidence/qa-post-recovery-public-smoke-20260510/playwright-screenshot-attempt.txt`
- Screenshots: not produced because Playwright could not launch a browser.

## Production Blockers Remaining

1. Cloud Run, GCS, Secret Manager, and Cloud Tasks live evidence is absent.
2. Backend is a host `.venv` uvicorn process, not a durable backend Docker image/container.
3. Runtime storage remains local; artifact durability through GCS is not proven.
4. Billing/Stripe remains disabled: `billing.available=false`, `production_billing=false`.
5. Video final render remains blocked for production readiness because `/readyz` reports `ffmpeg_available=false`.
6. MLflow artifact/run logging is not clean: TTS response returned no run id and still reports permission denied for `/mlflow`.
7. Host process cleanliness failed because unrelated `docker build` and `apt-get update` processes were active during the audit.
8. Browser screenshot evidence is missing until the Playwright host dependency issue is fixed.

## Residual Risk

The public recovered TTS path is usable for this smoke check, but this is not enough for a final production claim. The runtime can regress if the host uvicorn process stops, local audio files are deleted, or the host build pressure changes. A final gate should rerun this smoke after a durable backend image/deploy path, clean MLflow artifact permissions, FFmpeg runtime availability, and cloud service evidence are in place.

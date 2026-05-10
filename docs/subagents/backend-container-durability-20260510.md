# Backend Container Durability - 2026-05-10

Role: Backend Container Durability Engineer  
Time: 2026-05-10 21:33 +0700  
Start commit: `f2ba690`  

## Outcome

I did not start a backend Docker build in this pass.

Reason: the required preflight found active, unrelated Docker/apt work that had not cleared after repeated checks. Starting another backend build would have violated the safety rule to check that no `docker build`, `apt-get`, or `pip install` processes are active before building.

The current public host backend on `:8080` was preserved and remained healthy. No product code, Docker config, runtime secrets, frontend files, screenshots, Git history, or `.env.runtime` values were changed. This report is the only file I added.

Context7: not used. No FastAPI/backend library code was modified.

## Path Chosen

The repo already has the right repeatable backend container path:

- `Dockerfile` builds the FastAPI backend from `python:3.12-slim`.
- It intentionally installs `curl`, `ca-certificates`, `espeak-ng`, and `ffmpeg`.
- It installs `requirements.txt`.
- It runs as non-root `appuser`.
- It exposes `8080` and has a `/healthz` healthcheck.
- `scripts/local-services.sh` already defaults to `IMAGE=voice-ai:durable-20260510` and runs the backend container on the `voice-ai-local` network.

So the safe path is a controlled rebuild of the existing Dockerfile into `voice-ai:durable-20260510`, then a container smoke on alternate host port `18080` before any public cutover.

## Preflight Commands And Results

Git/runtime inventory:

```bash
git rev-parse --short HEAD
git status --short
ss -ltnp | rg ':(4174|5000|8080|18080)\b' || true
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}'
```

Results:

- `HEAD=f2ba690`.
- Existing untracked files were present before my report: `docs/subagents/evidence/qa-post-recovery-public-smoke-20260510/` and `docs/subagents/qa-post-recovery-public-smoke-20260510.md`.
- Public host backend was listening on `0.0.0.0:8080` as `uvicorn` pid `26096`.
- Frontend preview was listening on `0.0.0.0:4174`.
- MLflow container `voice-ai-mlflow` was running on `:5000`.
- No `voice-ai:*` backend image existed locally.

Build safety checks:

```bash
ps -eo pid,ppid,stat,etime,cmd | rg -i '[d]ocker build|[a]pt-get|[p]ip install' || true
df -h /
docker system df
curl -fsSI --connect-timeout 5 --max-time 10 http://deb.debian.org/debian/ | sed -n '1,8p'
curl -fsSI --connect-timeout 5 --max-time 10 https://pypi.org/simple/pip/ | sed -n '1,8p'
```

Results:

- `/` had about `16G` free, `66%` used.
- Docker build cache was initially `0B`, then later showed `54.77MB` from unrelated active build work.
- Host Debian reachability returned `HTTP/1.1 200 OK`.
- Host PyPI reachability returned `HTTP/2 200`.
- Active unrelated processes remained:
  - `docker run --rm python:3.10-slim-bookworm ... apt-get ...`
  - `apt-get -o Acquire::Retries=5 update`
  - `docker build --file /root/.ssh/npm/AutoClipperAI/Dockerfile.dev --tag autoclipperai_autoclip-dev ...`
  - another `apt-get update` inside that build.

Container network spot check:

```bash
taskset -c 0-3 docker run --rm -i python:3.10-slim-bookworm python - <<'PY'
import urllib.request
for url in ['http://deb.debian.org/debian/', 'https://pypi.org/simple/pip/']:
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            print(f'{url} -> {resp.status}')
    except Exception as exc:
        print(f'{url} -> ERROR {type(exc).__name__}: {exc}')
PY
```

Result:

- `http://deb.debian.org/debian/ -> 200`
- `https://pypi.org/simple/pip/ -> ERROR URLError: <urlopen error _ssl.c:1000: The handshake operation timed out>`

This reinforced the decision not to start a pip/apt-heavy backend image build while the host already had stuck containerized install work.

## Required Verification Status

1. Durable backend image exists locally: **not complete**. `docker image inspect voice-ai:durable-20260510` returned no image.
2. Container smoke for `/healthz` and `/readyz`: **not run**, because no image was built.
3. `ffmpeg -version` inside image/runtime: **not run**, because no image was built. The Dockerfile includes `ffmpeg`; this still needs runtime verification.
4. Container-backed OpenAI TTS smoke: **not run**, because no image was built. `.env.runtime` has the needed OpenAI env values set, but I did not print or modify them.
5. Host public runtime remains healthy: **pass**.
6. Final process/cache state checked: **pass for inspection, no cleanup performed**. I did not prune because no backend build artifacts were created by this pass, and active unrelated Docker work was still running.

## Host Public Runtime Verification

Commands:

```bash
curl -fsS --max-time 5 http://127.0.0.1:8080/healthz
curl -fsS --max-time 8 http://127.0.0.1:8080/readyz
```

Results:

```json
{"status":"ok","service":"voice-ai","version":"0.1.0"}
```

Readiness summary:

- `status=ready`
- active provider `openai`, ready
- local storage ready
- MLflow configured and ready
- video localization ready in `auto` mode
- host runtime still reports `ffmpeg_available=false`
- dispatch mode `local_inline`, ready

## Env Status

Checked from `.env.runtime` without printing values:

- `TTS_PROVIDER=set`
- `OPENAI_API_KEY=set`
- `OPENAI_TTS_MODEL=set`
- `OPENAI_TTS_VOICE=set`
- `OPENAI_TTS_RESPONSE_FORMAT=set`
- `LOCALIZATION_PROVIDER=set`
- `PUBLIC_DEMO_PROFILE=set`
- `REQUIRE_REAL_TTS=set`
- `MLFLOW_TRACKING_URI=unset`

## Production Readiness

Container path status: **not yet production-ready**.

The Dockerfile is a reasonable local durable/runtime path, but production readiness is blocked until the image is actually built and smoked. The current service remains a host `.venv` recovery runtime, not a durable backend container runtime.

## Next Commands

Run these only after this returns no active build/install work:

```bash
ps -eo pid,ppid,stat,etime,cmd | rg -i '[d]ocker build|[a]pt-get|[p]ip install' || true
```

Build the durable image:

```bash
taskset -c 0-3 docker build --progress=plain -t voice-ai:durable-20260510 .
docker image inspect voice-ai:durable-20260510 --format 'id={{.Id}} size={{.Size}}'
```

Smoke on alternate port, preserving the host backend on `:8080`:

```bash
docker rm -f voice-ai-backend-durable-smoke >/dev/null 2>&1 || true
taskset -c 0-3 docker run -d --rm \
  --name voice-ai-backend-durable-smoke \
  --network voice-ai-local \
  --env-file .env.runtime \
  -e ENVIRONMENT=local \
  -e PORT=8080 \
  -e AUDIO_STORAGE_DIR=/app/data/audio \
  -e AUDIO_BASE_URL=http://103.27.237.252:18080/audio \
  -e MLFLOW_TRACKING_URI=http://voice-ai-mlflow:5000 \
  -e VIDEO_JOB_DISPATCH_MODE=local_inline \
  -e FFMPEG_PATH=ffmpeg \
  -v "$PWD/data/audio:/app/data/audio" \
  -v "$PWD/data/video-jobs:/app/data/video-jobs" \
  -v "$PWD/data/artifacts:/app/data/artifacts" \
  -v "$PWD/artifacts/mlflow:/mlflow/artifacts" \
  -p 127.0.0.1:18080:8080 \
  voice-ai:durable-20260510
```

Verify health, readiness, and FFmpeg:

```bash
curl -fsS http://127.0.0.1:18080/healthz
curl -fsS http://127.0.0.1:18080/readyz
docker exec voice-ai-backend-durable-smoke ffmpeg -version | sed -n '1,3p'
```

Run container-backed OpenAI TTS smoke without printing secrets:

```bash
curl -fsS -X POST http://127.0.0.1:18080/v1/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"Xin chao, day la bai kiem tra container backend Voice AI.","voice":{"language_code":"vi-VN"},"audio":{"encoding":"LINEAR16","sample_rate_hz":24000},"metadata":{"smoke":"backend-container-durability-20260510"}}'
```

Verify the returned audio URL/path and local file header. If the response contains an `audio_url` on `:18080`, run:

```bash
curl -fsSI '<audio_url_from_response>' | sed -n '1,8p'
```

Final cleanup/status:

```bash
docker rm -f voice-ai-backend-durable-smoke
docker builder prune -f
ps -eo pid,ppid,stat,etime,cmd | rg -i '[d]ocker build|[a]pt-get|[p]ip install' || true
docker system df
curl -fsS http://127.0.0.1:8080/healthz
```

Only after all container smoke checks pass should PM schedule a public cutover from host `.venv` on `:8080` to the container runtime.

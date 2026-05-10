# Infra/Observability Agent

## Scope And Skill

Used role skill: `$voice-ai-infra-observability` from `/home/jhao/.codex/skills/voice-ai-infra-observability/SKILL.md`.

Ownership respected: only infra/deploy/docs/subagent files were edited. I did not edit app or frontend source.

Official/current sources checked on 2026-05-10:

- Cloud Run FastAPI quickstart: https://cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-fastapi-service
- Google GitHub Actions auth and Workload Identity Federation: https://github.com/google-github-actions/auth
- Google GitHub Actions deploy-cloudrun: https://github.com/google-github-actions/deploy-cloudrun
- Cloud Run logging: https://cloud.google.com/run/docs/logging
- Cloud Run monitoring overview: https://docs.cloud.google.com/run/docs/monitoring-overview
- Cloud Run service request timeout: https://cloud.google.com/run/docs/configuring/request-timeout
- Cloud Tasks HTTP target tasks: https://cloud.google.com/tasks/docs/creating-http-target-tasks
- MLflow Tracking and Tracking UI/server docs: https://www.mlflow.org/docs/latest/ml/tracking

## Running Services

Started persistent local services in a dedicated tmux server socket named `voice-ai`:

```text
$ tmux -L voice-ai list-sessions
voice-ai-backend: 1 windows (created Sun May 10 13:42:17 2026)
voice-ai-frontend: 1 windows (created Sun May 10 13:42:17 2026)
voice-ai-mlflow: 1 windows (created Sun May 10 13:42:17 2026)
```

Docker containers:

```text
$ docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
NAMES              IMAGE                           PORTS                    STATUS
voice-ai-mlflow    ghcr.io/mlflow/mlflow:v3.12.0   0.0.0.0:5000->5000/tcp   Up About a minute
voice-ai-backend   voice-ai:infra-video-check      0.0.0.0:8080->8080/tcp   Up 2 minutes (healthy)
```

Frontend:

```text
$ tail -n 8 logs/frontend.log
> voice-ai-frontend@0.1.0 preview
> vite preview --host 0.0.0.0 --host 0.0.0.0 --port 4174

  Local:   http://localhost:4174/
  Network: http://103.27.237.252:4174/
```

## URLs

Local URLs:

- Frontend preview: http://localhost:4174/
- Backend API: http://localhost:8080/
- Backend health: http://localhost:8080/healthz
- Backend readiness: http://localhost:8080/readyz
- MLflow UI: http://localhost:5000/

Best-effort server/public candidate URLs from `hostname -I`:

- Frontend preview: http://103.27.237.252:4174/
- Backend API: http://103.27.237.252:8080/
- Backend health: http://103.27.237.252:8080/healthz
- MLflow candidate: http://103.27.237.252:5000/

Observed externally-routable checks from this server:

```text
$ curl -fsS http://103.27.237.252:8080/healthz
{"status":"ok","service":"voice-ai","version":"0.1.0"}

$ curl -I --max-time 5 http://103.27.237.252:4174/
HTTP/1.1 200 OK
Content-Type: text/html
```

MLflow public candidate currently returns `403 Forbidden` because MLflow v3.12.0 enables host/security checks. Localhost MLflow works. Exposing MLflow publicly needs explicit allowed-hosts/reverse-proxy configuration.

## Commands Used To Start Services

Current reproducible helper:

```bash
./scripts/local-services.sh status
./scripts/local-services.sh restart
./scripts/local-services.sh stop
./scripts/local-services.sh start
```

The helper starts:

- `voice-ai-mlflow`: `ghcr.io/mlflow/mlflow:v3.12.0`, port `5000`, mounted `./mlruns` and `./artifacts/mlflow`.
- `voice-ai-backend`: `voice-ai:infra-video-check`, port `8080`, mounted `./data/audio`, `./data/video-jobs`, `./data/artifacts`.
- `voice-ai-frontend`: `npm run preview -- --host 0.0.0.0 --port 4174`.

Logs:

- Backend: `logs/backend.log`
- Frontend: `logs/frontend.log`
- MLflow: `logs/mlflow.log`

Attach/read live sessions:

```bash
tmux -L voice-ai attach -t voice-ai-backend
tmux -L voice-ai attach -t voice-ai-frontend
tmux -L voice-ai attach -t voice-ai-mlflow
```

Detach from tmux with `Ctrl-b`, then `d`.

## Implemented Infra

Files added/updated:

- `Dockerfile`: production-oriented Python runtime, non-root user, Cloud Run port binding, healthcheck, FFmpeg/FFprobe installed for video localization, deterministic fallback package pins.
- `.dockerignore`: excludes local state, logs, media, credentials, and generated artifacts.
- `.env.example`: secret-safe placeholders only; no real API key values.
- `docker-compose.yml`: local app + MLflow + optional worker profile, audio/video/artifact mounts.
- `.github/workflows/ci.yml`: install/test/compose validation/container build plus video smoke hook.
- `.github/workflows/deploy-cloud-run.yml`: guarded manual Cloud Run deploy using Workload Identity/secrets placeholders.
- `deploy/README.md`: Cloud Run/IAM/API/runbook notes including video localization constraints.
- `scripts/cloud-run-deploy.sh`: manual Cloud Run container deploy.
- `scripts/cloud-run-iam-bootstrap.sh`: API enablement, Artifact Registry, service accounts, Cloud Tasks queue, bucket IAM.
- `scripts/cloud-run-observe.sh`: Cloud Run logs/revisions/metric hints.
- `scripts/video-workflow-smoke.sh`: FFmpeg/FFprobe image smoke hook.
- `scripts/local-services.sh`: tmux-based local service start/stop/status.
- `docs/subagents/infra-report.md`: this report.

## Video Workflow Status

Implemented in infra scaffolding:

- Runtime image has FFmpeg and FFprobe.
- Local volumes exist for audio, video jobs, and artifacts.
- Env placeholders cover upload size, stage timeout, GCS artifact bucket/prefixes, Cloud Tasks queue/location/handler, and MLflow video experiment.
- Cloud Run deploy defaults are video-aware: `--timeout=3600`, `--memory=4Gi`, `--cpu=2`, `--concurrency=1`.
- CI has a video smoke hook that checks FFmpeg/FFprobe in the built image.
- Runbook documents Cloud Tasks + Cloud Run handler pattern and Cloud Run Jobs fallback for larger jobs.

Not implemented in infra because it requires app/product code or cloud credentials:

- Real Cloud Tasks enqueue/handler execution in production.
- Durable GCS artifact writes from the runtime.
- End-to-end uploaded-video processing benchmark.
- Public MLflow exposure; currently localhost works, public candidate is blocked by MLflow host security.
- Cloud Run deployment execution; scripts/workflows are credential-ready but were not run against GCP.

## Validation Evidence

Syntax/config checks:

```text
$ bash -n scripts/cloud-run-deploy.sh scripts/cloud-run-iam-bootstrap.sh scripts/cloud-run-observe.sh scripts/video-workflow-smoke.sh scripts/local-services.sh
# exit 0

$ docker compose config --quiet
# exit 0

$ docker build --check .
Check complete, no warnings found.
```

Image build:

```text
$ docker build -t voice-ai:infra-video-check .
#12 naming to docker.io/library/voice-ai:infra-video-check done
#12 DONE 87.5s
```

Container FFmpeg check:

```text
$ docker inspect --format '{{.State.Health.Status}}' voice-ai-backend
healthy

$ docker exec voice-ai-backend ffmpeg -version | sed -n '1p'
ffmpeg version 7.1.3-0+deb13u1 Copyright (c) 2000-2025 the FFmpeg developers

$ docker exec voice-ai-backend ffprobe -version | sed -n '1p'
ffprobe version 7.1.3-0+deb13u1 Copyright (c) 2007-2025 the FFmpeg developers
```

Video smoke hook:

```text
$ ./scripts/video-workflow-smoke.sh voice-ai:infra-video-check
Checking FFmpeg in voice-ai:infra-video-check
ffmpeg version 7.1.3-0+deb13u1 Copyright (c) 2000-2025 the FFmpeg developers
Checking FFprobe in voice-ai:infra-video-check
ffprobe version 7.1.3-0+deb13u1 Copyright (c) 2007-2025 the FFmpeg developers
No app video smoke hook found; FFmpeg/FFprobe container checks completed.
```

Backend checks:

```text
$ curl -fsS http://127.0.0.1:8080/healthz
{"status":"ok","service":"voice-ai","version":"0.1.0"}

$ curl -fsS http://127.0.0.1:8080/readyz
{"status":"ready","provider":{"name":"local","ready":true,"detail":null},"storage":{"mode":"local","ready":true,"detail":null},"mlflow":{"configured":true,"ready":true,"detail":null}}

$ curl -fsS http://127.0.0.1:8080/v1/voices
{"provider":"local","voices":[{"name":"local-en-US-test-voice","language_codes":["en-US"],"ssml_gender":"NEUTRAL","natural_sample_rate_hz":24000,"supported_encodings":["LINEAR16","MP3","OGG_OPUS"]},{"name":"local-vi-VN-test-voice","language_codes":["vi-VN"],"ssml_gender":"NEUTRAL","natural_sample_rate_hz":24000,"supported_encodings":["LINEAR16","MP3","OGG_OPUS"]}]}
```

Frontend and MLflow local checks:

```text
$ curl -I --max-time 5 http://127.0.0.1:4174/
HTTP/1.1 200 OK
Content-Type: text/html

$ curl -I --max-time 5 http://127.0.0.1:5000/
HTTP/1.1 200 OK
server: uvicorn
content-type: text/html; charset=utf-8
```

## Secret Handling

- No user-provided API keys were used, logged, or written.
- `.env.example` contains placeholders only. `API_KEYS=CHANGE_ME_LOCAL_ONLY` is a placeholder, not a real secret.
- The local PM test backend is running with `API_KEYS` empty, so API-key auth is disabled for this local preview. Do not use this mode for production.
- GitHub Actions deploy uses Workload Identity placeholders and Secret Manager references: secret values are never echoed by the workflow.
- Reports must redact any future secret material as `[redacted]`.

## Operational Notes And Blockers

- The default tmux server on this host could not access Docker: `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`. I avoided disrupting existing tmux sessions by using a separate tmux socket: `tmux -L voice-ai`.
- Another frontend preview was already listening on `0.0.0.0:4173` from a separate process. I left it untouched and started this agent's frontend on `4174`.
- The server IP candidate is `103.27.237.252`. Public reachability depends on host firewall/provider rules; I verified HTTP responses from this server, not from an outside network.
- Cloud deployment needs actual GCP project, Workload Identity provider, service accounts, Secret Manager secret names, buckets, and Cloud Tasks queue configuration.

## GitHub Push Readiness Addendum

Added `.gitignore` for safe repository initialization and push. It excludes generated/local files:

- Python virtualenvs/caches: `.venv/`, `venv/`, `__pycache__/`, `.pytest_cache/`, coverage caches.
- Frontend generated files: `frontend/node_modules/`, `frontend/dist/`, `frontend/build/`, `frontend/test-results/`, `frontend/playwright-report/`.
- Local env/credentials: `.env`, `.env.*`, key/certificate files, Google credential JSON patterns; `.env.example` remains included.
- Runtime output: `logs/`, `mlruns/`, `artifacts/`, SQLite/DB files.
- Uploaded/generated media: `data/audio/`, `data/video/`, `data/video-jobs/`, `data/artifacts/`, common audio/video/subtitle extensions.
- OS/editor files.

Files intended to remain commit-ready include source, docs, tests, CI workflows, scripts, `Dockerfile`, compose files, `requirements.txt`, and `frontend/package-lock.json`.

This directory is not currently a Git repository:

```text
$ test -d .git && echo git-repo || echo not-a-git-repo
not-a-git-repo
```

Because there is no `.git/` directory yet, `git check-ignore` cannot run normally here. I used `rg --files --hidden --ignore-file .gitignore` as the non-mutating readiness check; the resulting file list excludes `.venv`, `frontend/node_modules`, `frontend/dist`, `frontend/test-results`, `logs`, `mlruns`, `artifacts`, and `data` runtime media while keeping source/docs/workflows/scripts/package locks visible.

Secret scan summary, redacted:

```text
$ rg --files-with-matches ...common secret/key patterns... .
Secret-pattern scan summary: 182 matches across 24 files
High-confidence secret literal scan summary: 0 matches across 0 files
```

Interpretation: broad keyword matches are expected placeholders or documentation references in files such as `.env.example`, deploy docs, workflows, scripts, and reports. The high-confidence literal scan found no Google API key, OpenAI-style key, GitHub token, Slack token, AWS access key, or private-key block. No secret values were copied into this report; any future secret material must be redacted as `[redacted]`.

## Persistent Frontend Progress Link

The single user-facing progress link for PM review is:

- http://103.27.237.252:4174/

Current verification:

```text
$ tmux -L voice-ai list-sessions
voice-ai-backend: 1 windows (created Sun May 10 13:42:17 2026)
voice-ai-frontend: 1 windows (created Sun May 10 13:42:17 2026)
voice-ai-mlflow: 1 windows (created Sun May 10 13:42:17 2026)

$ ss -ltnp | rg ':4174\b|State'
State  Recv-Q Send-Q Local Address:Port  Peer Address:PortProcess
LISTEN 0      511          0.0.0.0:4174       0.0.0.0:*    users:(("node",pid=609904,fd=23))

$ curl -I --max-time 5 http://103.27.237.252:4174/
HTTP/1.1 200 OK
Content-Type: text/html
```

Keep using `./scripts/local-services.sh status|restart|stop|start` for service lifecycle. The frontend preview is intentionally bound to `0.0.0.0:4174`.

## Backend Refresh Addendum

Context: PM saw `404` from the running backend on `/health`, `/v1/product/capabilities`, and `/v1/product/plans`. Source inspection showed the latest backend code defines `/healthz`, `/readyz`, `/v1/product/capabilities`, and `/v1/product/plans`; the running backend container was stale.

Commands run:

```bash
rg -n "@app\\.(get|post|put|delete|patch)|health|capabilities|plans" app tests docs
docker build -t voice-ai:infra-video-check .
tmux -L voice-ai kill-session -t voice-ai-backend
docker rm -f voice-ai-backend
tmux -L voice-ai new-session -d -s voice-ai-backend -c /home/jhao/code/voice-ai "<backend docker run command with local demo env; no secrets>"
```

Current backend status:

```text
$ tmux -L voice-ai list-sessions
voice-ai-backend: 1 windows (created Sun May 10 13:56:53 2026)
voice-ai-frontend: 1 windows (created Sun May 10 13:42:17 2026)
voice-ai-mlflow: 1 windows (created Sun May 10 13:42:17 2026)

$ docker inspect --format '{{.State.Health.Status}}' voice-ai-backend
healthy

$ docker exec voice-ai-backend ffmpeg -version | sed -n '1p'
ffmpeg version 7.1.3-0+deb13u1 Copyright (c) 2000-2025 the FFmpeg developers
```

Working backend endpoints after refresh:

```text
$ curl -sS -o /tmp/out -w 'HTTP %{http_code}\n' http://127.0.0.1:8080/healthz
HTTP 200
{"status":"ok","service":"voice-ai","version":"0.1.0"}

$ curl -sS -o /tmp/out -w 'HTTP %{http_code}\n' http://127.0.0.1:8080/readyz
HTTP 200
{"status":"ready","provider":{"name":"local","ready":true,"detail":null},"storage":{"mode":"local","ready":true,"detail":null},"mlflow":{"configured":true,"ready":true,"detail":null},"video_localization":{"mode":"local","ready":true,"ffmpeg_available":true,"detail":"local demo mode can create artifacts without ffmpeg; real muxing requires ffmpeg"}}

$ curl -sS -o /tmp/out -w 'HTTP %{http_code}\n' http://127.0.0.1:8080/v1/product/capabilities
HTTP 200

$ curl -sS -o /tmp/out -w 'HTTP %{http_code}\n' http://127.0.0.1:8080/v1/product/plans
HTTP 200
```

Public/server candidate URLs verified from this server:

- `http://103.27.237.252:8080/healthz` -> `HTTP 200`
- `http://103.27.237.252:8080/readyz` -> `HTTP 200`
- `http://103.27.237.252:8080/v1/product/capabilities` -> `HTTP 200`
- `http://103.27.237.252:8080/v1/product/plans` -> `HTTP 200`

Superseded by the parallel service debug addendum below: after the latest backend rebuild and restart, `/health` is now exposed and returns `HTTP 200`.

Frontend link remains running and unchanged:

- `http://103.27.237.252:4174/` -> `HTTP 200`

## Parallel Service Debug Addendum

Timestamp: `2026-05-10 14:31:33 +07`

Role/skill used: Infra/Observability Agent using `$voice-ai-infra-observability`.

Context7 status: not used in this addendum because no Docker, Vite, FastAPI, script, or config files were modified. This pass changed only live tmux/docker runtime commands and this report. For MLflow runtime flag debugging, I used the installed image help output from `ghcr.io/mlflow/mlflow:v3.12.0 mlflow server --help`, specifically `--allowed-hosts`, `--cors-allowed-origins`, `--serve-artifacts`, `--default-artifact-root`, and `--artifacts-destination`.

Current tmux sessions:

```text
$ tmux -L voice-ai list-sessions
voice-ai-backend: 1 windows (created Sun May 10 14:30:33 2026)
voice-ai-frontend: 1 windows (created Sun May 10 13:42:17 2026)
voice-ai-mlflow: 1 windows (created Sun May 10 14:26:51 2026)
```

Current containers:

```text
$ docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
NAMES              IMAGE                           PORTS                    STATUS
voice-ai-backend   voice-ai:infra-video-check      0.0.0.0:8080->8080/tcp   Up About a minute (healthy)
voice-ai-mlflow    ghcr.io/mlflow/mlflow:v3.12.0   0.0.0.0:5000->5000/tcp   Up 4 minutes
```

Backend freshness evidence:

```text
$ docker exec voice-ai-backend sh -lc 'sha256sum /app/app/main.py /app/app/frontend_support.py /app/requirements.txt; ffmpeg -version | head -n 1'
64bb072a5f5ead7d571d0aaef713fac46848217c0a7226cbfb0c50515dc6fbf8  /app/app/main.py
79b3490007eedfc950352557a6796aa27bc4312560191a1222d52212d9a2672b  /app/app/frontend_support.py
80dce953d4be2e588d1297abb19b18844b1152dc8fedffe37d540d5e4e21a329  /app/requirements.txt
ffmpeg version 7.1.3-0+deb13u1 Copyright (c) 2000-2025 the FFmpeg developers

$ sha256sum app/main.py app/frontend_support.py requirements.txt
64bb072a5f5ead7d571d0aaef713fac46848217c0a7226cbfb0c50515dc6fbf8  app/main.py
79b3490007eedfc950352557a6796aa27bc4312560191a1222d52212d9a2672b  app/frontend_support.py
80dce953d4be2e588d1297abb19b18844b1152dc8fedffe37d540d5e4e21a329  requirements.txt
```

Backend rebuild/restart commands used:

```bash
docker build --no-cache -t voice-ai:infra-video-check -f - . <<'EOF'
FROM voice-ai:infra-video-check
USER root
COPY app /app/app
COPY requirements.txt /app/requirements.txt
RUN chown -R appuser:appuser /app/app /app/requirements.txt
USER appuser
EOF

tmux -L voice-ai kill-session -t voice-ai-backend >/dev/null 2>&1 || true
docker rm -f voice-ai-backend >/dev/null 2>&1 || true
docker network inspect voice-ai-local >/dev/null 2>&1 || docker network create voice-ai-local >/dev/null
tmux -L voice-ai new-session -d -s voice-ai-backend -c /home/jhao/code/voice-ai "<docker run voice-ai:infra-video-check on 0.0.0.0:8080 with local demo env, MLflow URI, and local data/mlflow mounts; no secrets>"
```

The backend restart includes these local-only mounts:

```text
/home/jhao/code/voice-ai/data/audio -> /app/data/audio
/home/jhao/code/voice-ai/data/video-jobs -> /app/data/video-jobs
/home/jhao/code/voice-ai/data/artifacts -> /app/data/artifacts
/home/jhao/code/voice-ai/mlruns -> /mlflow
/home/jhao/code/voice-ai/artifacts/mlflow -> /mlflow/artifacts
```

The added `/mlflow` and `/mlflow/artifacts` mounts fixed the earlier TTS warning `MLflow tracking failed: [Errno 13] Permission denied: '/mlflow'`. No secret values were printed or stored; the local PM demo backend runs with `API_KEYS=` empty and external providers unset.

Public endpoint matrix:

```text
http://103.27.237.252:8080/health                  PASS HTTP 200 {"status":"ok","service":"voice-ai","version":"0.1.0"}
http://103.27.237.252:8080/healthz                 PASS HTTP 200 {"status":"ok","service":"voice-ai","version":"0.1.0"}
http://103.27.237.252:8080/readyz                  PASS HTTP 200 status=ready, mlflow.ready=true, ffmpeg_available=true
http://103.27.237.252:8080/v1/product/capabilities PASS HTTP 200 mode=demo, tts.available=true, video_localization.available=true
http://103.27.237.252:8080/v1/product/plans        PASS HTTP 200 plan ids: demo-free, starter-placeholder
http://103.27.237.252:8080/v1/voices               PASS HTTP 200 voices: local-en-US-test-voice, local-vi-VN-test-voice
http://103.27.237.252:8080/v1/synthesize           PASS HTTP 200 status=succeeded, audio_url returned, mlflow_run_id=9b3b2d0b7f5646fbb427b754c1ebd3a9, warnings=[]
http://103.27.237.252:4174/                        PASS HTTP 200 frontend preview, 945 byte index
http://103.27.237.252:5000/                        PASS HTTP 200 MLflow UI, 701 byte index
```

Exact TTS smoke command/output:

```text
$ curl -sS -o /tmp/voice-ai-tts-smoke-mounted.json -w 'HTTP %{http_code}\n' -X POST http://103.27.237.252:8080/v1/synthesize -H 'Content-Type: application/json' -d '{"text":"Infra public smoke after MLflow mount","voice":{"language_code":"en-US"},"audio":{"encoding":"MP3"},"metadata":{"client_reference_id":"infra-final-mounted-mlflow"}}'
HTTP 200

{"job_id":"tts_beac60034869454bb329d7f8a6c14570","status":"succeeded","audio_url":"http://103.27.237.252:8080/audio/tts_beac60034869454bb329d7f8a6c14570.wav","audio_path":"/app/data/audio/tts_beac60034869454bb329d7f8a6c14570.wav","duration_ms":1850,"latency_ms":99,"provider":{"name":"local","fallback":true,"model":"deterministic-wav-tone"},"voice":{"language_code":"en-US","name":null,"ssml_gender":null},"audio":{"encoding":"LINEAR16","bytes":88844,"sample_rate_hz":24000,"checksum_sha256":"01ced22d81f93e99f264b749a64700ad21a61ede18947c0fc3ed1b129c82df75","content_type":"audio/wav"},"observability":{"request_id":"req_270fc6e781ea410ca90bdf2fc3ee3f63","mlflow_run_id":"9b3b2d0b7f5646fbb427b754c1ebd3a9","warnings":[]},"metadata":{"client_reference_id":"infra-final-mounted-mlflow"}}
```

Frontend status:

- Single user-facing progress link remains `http://103.27.237.252:4174/`.
- It was not restarted in this addendum because the existing preview returned `HTTP 200` after the latest frontend build artifacts were already present.
- Restart command if needed:

```bash
tmux -L voice-ai kill-session -t voice-ai-frontend >/dev/null 2>&1 || true
tmux -L voice-ai new-session -d -s voice-ai-frontend -c /home/jhao/code/voice-ai/frontend "npm run preview -- --host 0.0.0.0 --port 4174 2>&1 | tee -a ../logs/frontend.log"
```

MLflow status:

- Public UI: `http://103.27.237.252:5000/` -> `HTTP 200`.
- Server command allows local Docker hostnames and the public host header, and writes to local ignored directories:

```bash
tmux -L voice-ai new-session -d -s voice-ai-mlflow -c /home/jhao/code/voice-ai "docker run --rm --name voice-ai-mlflow --network voice-ai-local -p 0.0.0.0:5000:5000 -v /home/jhao/code/voice-ai/mlruns:/mlflow -v /home/jhao/code/voice-ai/artifacts/mlflow:/mlflow/artifacts ghcr.io/mlflow/mlflow:v3.12.0 mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:////mlflow/mlflow.db --default-artifact-root /mlflow/artifacts --serve-artifacts --allowed-hosts localhost,localhost:5000,127.0.0.1,127.0.0.1:5000,voice-ai-mlflow,voice-ai-mlflow:5000,103.27.237.252,103.27.237.252:5000 --cors-allowed-origins http://localhost:4174,http://103.27.237.252:4174 2>&1 | tee -a logs/mlflow.log"
```

Current backend failures/blockers:

- None for the requested public health/readiness/product/voices/TTS endpoints.
- Production cloud deploy still requires real GCP project, Workload Identity provider, service accounts, Secret Manager names, GCS buckets, and queue configuration.

## Stability Addendum - Local Services

Timestamp: `2026-05-10 14:54 +07`

Role/skill used: Infra Stability Agent using `$voice-ai-infra-observability`.

Context7 status: not applicable for this pass. The only code change was a Bash service helper; no framework or library API behavior was changed.

CPU constraint: used `taskset -c 0-3` for the controlled restart, status checks, Docker inspect/image checks, Docker events review, and HTTP probes. `scripts/local-services.sh` now also prefixes Docker-run tmux commands, frontend builds, and Vite preview/dev commands with `taskset -c ${TASKSET_CPUSET:-0-3}` when `taskset` is installed.

### Stop Investigation

Likely cause of the earlier `docker ps` empty result: service lifecycle, not an observed app crash.

- The app sessions live on tmux socket `voice-ai`, so plain `tmux ls` only showing another session is expected. Use `tmux -L voice-ai list-sessions`.
- The helper runs backend and MLflow as foreground `docker run --rm` processes inside tmux sessions. If those tmux sessions are killed, or if `./scripts/local-services.sh stop/restart` runs, Docker removes the containers. In that state, `docker ps` correctly shows no `voice-ai-*` containers.
- Docker events show `voice-ai-backend` and `voice-ai-mlflow` were destroyed at `2026-05-10 14:43:53 +07`, then recreated by a later restart at `2026-05-10 14:49:15 +07`.
- The controlled verification restart for this addendum killed and recreated both containers at `2026-05-10 14:53:16 +07`.

### Script Reliability Changes

Updated `scripts/local-services.sh`:

- `status` now prints the tmux socket, backend image, frontend mode, port, taskset setting, session list, Docker table, frontend HEAD response, and backend `/healthz` response.
- `restart/start` now checks whether `frontend/dist/index.html` is missing or older than frontend source/config/package files. If stale, it runs `npm run build` before starting preview.
- Frontend preview is still bound to `0.0.0.0:4174`; `FRONTEND_MODE=dev` can start Vite dev mode on the same host/port if needed.
- `restart/start` waits for backend `/healthz` and frontend `/` before returning.
- `TASKSET_CPUSET` defaults to `0-3`; set `TASKSET_CPUSET=` only if CPU pinning should be disabled by editing the helper or running on a host without `taskset`.

Current operator commands:

```bash
taskset -c 0-3 ./scripts/local-services.sh status
taskset -c 0-3 ./scripts/local-services.sh restart
taskset -c 0-3 ./scripts/local-services.sh stop
```

Attach or inspect tmux sessions:

```bash
tmux -L voice-ai list-sessions
tmux -L voice-ai attach -t voice-ai-backend
tmux -L voice-ai attach -t voice-ai-frontend
tmux -L voice-ai attach -t voice-ai-mlflow
```

Detach with `Ctrl-b`, then `d`.

### Current Live Status

After the controlled restart:

```text
$ taskset -c 0-3 ./scripts/local-services.sh status
tmux socket: voice-ai
taskset: taskset -c 0-3
backend image: voice-ai:durable-20260510
frontend mode: preview; port: 4174
voice-ai-backend: 1 windows (created Sun May 10 14:53:16 2026)
voice-ai-frontend: 1 windows (created Sun May 10 14:53:16 2026)
voice-ai-mlflow: 1 windows (created Sun May 10 14:53:16 2026)
NAMES              IMAGE                           PORTS                    STATUS
voice-ai-mlflow    ghcr.io/mlflow/mlflow:v3.12.0   0.0.0.0:5000->5000/tcp   Up
voice-ai-backend   voice-ai:durable-20260510       0.0.0.0:8080->8080/tcp   Up (healthy)
HTTP/1.1 200 OK
{"status":"ok","service":"voice-ai","version":"0.1.0"}
```

Live links verified from this host:

- Public frontend: `http://103.27.237.252:4174/` -> `HTTP 200`
- Public backend health: `http://103.27.237.252:8080/healthz` -> `HTTP 200`
- Local MLflow UI: `http://127.0.0.1:5000/` -> `HTTP 200`
- Public MLflow candidate: `http://103.27.237.252:5000/` -> `HTTP 403` after the latest helper restart because the helper uses MLflow default host security settings.

### Durable Image / Hot Patch Check

- Durable image exists: `voice-ai:durable-20260510`
- Image ID: `sha256:b82362c008f4d0a472cdae3c37cd8b45858ce72470efa53311189061359203a8`
- Created: `2026-05-10T14:35:43.586963142+07:00`
- Running backend image: `voice-ai:durable-20260510`
- Running backend image ID matches the durable image ID above.
- Backend container mounts only local data/artifact directories into `/app/data/*`; it does not bind-mount `/app/app`, so it is not running app source as a hot patch.

If backend source changes after test fixes, rebuild and restart with:

```bash
taskset -c 0-3 docker build -t voice-ai:durable-20260510 .
taskset -c 0-3 ./scripts/local-services.sh restart
```

### Persistence Notes And Risks

- Keep the public frontend link open by keeping the `voice-ai-frontend` tmux session alive on socket `voice-ai`; use the helper restart if it exits.
- Backend and MLflow containers are intentionally ephemeral because they run with `--rm`; their persistent state is the host-mounted `data/`, `mlruns/`, and `artifacts/mlflow/` directories.
- A host reboot, tmux server kill, Docker daemon restart, or manual `./scripts/local-services.sh stop` will remove the containers and close the public links until `taskset -c 0-3 ./scripts/local-services.sh restart` runs again.
- Public MLflow exposure is not preserved by the helper; it is currently safest as localhost-only unless the helper is extended with explicit MLflow `--allowed-hosts` and CORS settings.
- The local preview runs with local/demo provider settings and empty `API_KEYS`; do not treat this as a production security posture.

## Real TTS Runtime Env Pass-Through Addendum

Timestamp: `2026-05-10 15:02 +07`

Role/skill used: Infra Real TTS Runtime Agent using `$voice-ai-infra-observability`.

Context7 status: used MCP Docker Context7 for Docker runtime environment handling.

- Library ID: `/docker/docs`
- Topic: `docker run environment variables --env --env-file secret handling`
- Relevant guidance applied: `docker run -e NAME`/`--env NAME` passes environment variables into the container, while secrets should not be baked into image `ENV`/`ARG` or printed into logs.

### Runtime Script Changes

Updated `scripts/local-services.sh`:

- Removed the hardcoded backend `-e TTS_PROVIDER=local`.
- Added a backend env allowlist passed through tmux and Docker by variable name: `TTS_PROVIDER`, `API_KEYS`, `OPENAI_API_KEY`, `OPENAI_TTS_MODEL`, `OPENAI_TTS_VOICE`, `OPENAI_TTS_RESPONSE_FORMAT`, `GCP_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS`, and `GOOGLE_CLOUD_REGION`.
- Kept the default provider as `local` only when the caller does not set `TTS_PROVIDER`.
- Added status output that reports provider and secret presence without printing secret values.
- Kept backend/frontend/MLflow lifecycle under the existing tmux socket and taskset behavior.

Updated `.env.example`:

- Added OpenAI TTS placeholders only: `OPENAI_API_KEY=`, `OPENAI_TTS_MODEL=gpt-4o-mini-tts`, `OPENAI_TTS_VOICE=coral`, and `OPENAI_TTS_RESPONSE_FORMAT=wav`.

### Safe Real TTS Restart

Use this from a shell where command tracing is disabled. Replace placeholders locally; do not paste or commit real keys.

```bash
set +x
export TTS_PROVIDER=openai
export OPENAI_API_KEY="<set in shell or secret manager>"
export OPENAI_TTS_MODEL="${OPENAI_TTS_MODEL:-gpt-4o-mini-tts}"
export OPENAI_TTS_VOICE="${OPENAI_TTS_VOICE:-coral}"
export OPENAI_TTS_RESPONSE_FORMAT="${OPENAI_TTS_RESPONSE_FORMAT:-wav}"
taskset -c 0-3 ./scripts/local-services.sh restart
taskset -c 0-3 ./scripts/local-services.sh status
```

Expected safe status shape:

```text
backend tts provider: openai
backend OPENAI_API_KEY: set
backend openai tts: model=gpt-4o-mini-tts voice=coral format=wav
```

The status command must never print the `OPENAI_API_KEY` value.

### Verification

Commands run:

```bash
bash -n scripts/local-services.sh
taskset -c 0-3 ./scripts/local-services.sh status
env -u OPENAI_API_KEY TTS_PROVIDER=local taskset -c 0-3 ./scripts/local-services.sh restart
taskset -c 0-3 ./scripts/local-services.sh status
```

Observed result after safe local restart:

```text
backend health is reachable at http://127.0.0.1:8080/healthz
frontend is reachable at http://127.0.0.1:4174/
backend tts provider: local
backend OPENAI_API_KEY: unset
backend openai tts: model=default voice=default format=default
backend GOOGLE_APPLICATION_CREDENTIALS: unset
{"status":"ok","service":"voice-ai","version":"0.1.0"}
```

No real OpenAI key was used, echoed, written to files, or included in this report.

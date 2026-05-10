# Backend Runtime Recovery - 2026-05-10

Role: Backend Infra Runtime Recovery Engineer  
Time: 2026-05-10 21:22 +0700  
Branch start state: `## main...origin/main` at PM-provided pushed commit `698f031`

## Recovery Path Chosen

Recovered the backend with the existing host `.venv` and `uvicorn` in a tmux session, instead of retrying Docker.

Why:

- The backend Docker image/container was missing.
- A previous Docker build had failed with Docker daemon EOF, and a later build was blocked on Debian `apt-get update` retries.
- At inspection time, another repo had an active `docker build`/`apt-get update`, so a controlled backend Docker build was not safe.
- The repo `.venv` already had most runtime dependencies; only `google-cloud-tasks` and `stripe` were missing.
- `.env.runtime` had `TTS_PROVIDER=openai`, `REQUIRE_REAL_TTS=1`, and `OPENAI_API_KEY` present.

No product code was changed. The only filesystem change from this worker is this report. Operationally, I installed the two missing runtime dependencies into `.venv`.

Context7: not used. This was runtime recovery with no code/API/library usage changes.

## Commands Run And Results

Inspection:

```bash
git status --short --branch
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}'
docker system df
ss -ltnp | rg ':(4174|5000|8080)\b'
df -h /
```

Result:

- Git was clean: `## main...origin/main`.
- Only `voice-ai-mlflow` container was running on `:5000`.
- No backend image/container existed.
- Frontend was listening on `:4174`.
- `:8080` was free.
- `/` had about 16G free.

Dependency verification:

```bash
.venv/bin/python - <<'PY'
mods = ['fastapi','uvicorn','pydantic','openai','mlflow','google.cloud.texttospeech','google.cloud.storage','google.cloud.tasks','jwt','stripe','pwdlib','multipart']
for mod in mods:
    try:
        __import__(mod)
        print(f'{mod}: ok')
    except Exception as e:
        print(f'{mod}: missing: {e.__class__.__name__}: {e}')
PY
```

Result: `.venv` was missing `google.cloud.tasks` and `stripe`.

Install:

```bash
taskset -c 0-3 .venv/bin/python -m pip install 'google-cloud-tasks>=2.16,<3.0' 'stripe>=12,<16'
```

Result: installed `google-cloud-tasks-2.22.0`, `grpc-google-iam-v1-0.14.4`, and `stripe-15.1.0`.

Runtime config check, without printing secrets:

```bash
set -a; . ./.env.runtime; set +a
python3 - <<'PY'
import os
for key in ['TTS_PROVIDER','OPENAI_TTS_MODEL','OPENAI_TTS_VOICE','OPENAI_TTS_RESPONSE_FORMAT','LOCALIZATION_PROVIDER','PUBLIC_DEMO_PROFILE','REQUIRE_REAL_TTS']:
    print(f'{key}={os.getenv(key, "")}')
print('OPENAI_API_KEY_SET=' + ('yes' if os.getenv('OPENAI_API_KEY') else 'no'))
PY
```

Result:

- `TTS_PROVIDER=openai`
- `OPENAI_TTS_MODEL=gpt-4o-mini-tts`
- `OPENAI_TTS_VOICE=marin`
- `OPENAI_TTS_RESPONSE_FORMAT=wav`
- `LOCALIZATION_PROVIDER=auto`
- `PUBLIC_DEMO_PROFILE=production`
- `REQUIRE_REAL_TTS=1`
- `OPENAI_API_KEY_SET=yes`

Backend start:

```bash
tmux -L voice-ai new-session -d -s voice-ai-backend-recovery -c /home/jhao/code/voice-ai \
  "set -a; . ./.env.runtime; set +a; export PORT=8080 ENVIRONMENT=public AUDIO_STORAGE_DIR=data/audio AUDIO_BASE_URL=http://103.27.237.252:8080/audio MLFLOW_TRACKING_URI=http://127.0.0.1:5000 VIDEO_JOB_DISPATCH_MODE=local_inline PYTHONUNBUFFERED=1; taskset -c 0-3 .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers 2>&1 | tee -a logs/backend-runtime-recovery-20260510.log"
```

Result:

- tmux session: `voice-ai-backend-recovery`
- process: `uvicorn`, PID `26096`
- listening: `0.0.0.0:8080`
- log: `logs/backend-runtime-recovery-20260510.log`

## Service URLs And Health

Backend:

- Local health: `http://127.0.0.1:8080/healthz`
- Public health: `http://103.27.237.252:8080/healthz`
- Capabilities: `http://127.0.0.1:8080/v1/product/capabilities`
- Public audio base: `http://103.27.237.252:8080/audio`

Health result:

```json
{"status":"ok","service":"voice-ai","version":"0.1.0"}
```

Capabilities summary:

- Environment: `public`
- Active TTS provider: `openai`
- TTS max input chars: `4096`
- Video localization mode: `auto`
- `ffmpeg_available=false` on the host runtime
- Auth configured: `false`
- Billing configured: `false`

Readiness:

```json
{"status":"ready","provider":{"name":"openai","ready":true},"storage":{"mode":"local","ready":true},"mlflow":{"configured":true,"ready":true},"video_localization":{"mode":"auto","ready":true,"ffmpeg_available":false,"provider":"openai","dispatch":{"mode":"local_inline","ready":true}}}
```

Frontend:

- Public URL: `http://103.27.237.252:4174/`
- Result: HTTP 200, `Content-Type: text/html`
- Public HTML references:
  - `/assets/index-CPkM3X2O.js`
  - `/assets/index-BSQREeFd.css`
- Both files exist in `frontend/dist/assets` and match the built dist files from `2026-05-10 18:45`.

## TTS Smoke

Command:

```bash
curl -fsS -X POST http://127.0.0.1:8080/v1/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"Xin chao, day la bai kiem tra phuc hoi backend Voice AI bang OpenAI TTS.","voice":{"language_code":"vi-VN"},"audio":{"encoding":"LINEAR16","sample_rate_hz":24000},"metadata":{"smoke":"backend-runtime-recovery-20260510"}}'
```

Result:

- Job id: `tts_13d790584bcf4de5bef33d45bd7203d1`
- Provider: `openai`
- Fallback: `false`
- Model: `gpt-4o-mini-tts`
- Audio URL: `http://103.27.237.252:8080/audio/tts_13d790584bcf4de5bef33d45bd7203d1.wav`
- Audio path: `data/audio/tts_13d790584bcf4de5bef33d45bd7203d1.wav`
- Audio bytes: `372044`
- Public audio HEAD: HTTP 200, `content-type: audio/x-wav`, `content-length: 372044`
- Local header check: RIFF/WAVE true

Observed warning:

- The API returned `MLflow tracking failed: [Errno 13] Permission denied: '/mlflow'`.
- The backend log still showed MLflow created run URL `http://127.0.0.1:5000/#/experiments/1/runs/9ce2400142d94436b423928deb4f1fd0`.
- Core TTS success was not blocked.

## Disk And Cleanup

Before cleanup:

- Docker build cache: about `264.2MB` plus one retained `35.76MB` cache item.
- `/`: about `16G` free, `66%` used.

Cleanup run:

```bash
docker builder prune -f
docker builder prune -af
```

After cleanup:

```text
Images          3         1         1.789GB   483.3MB (27%)
Containers      1         1         1.47MB    0B (0%)
Local Volumes   2         0         0B        0B
Build Cache     0         0         0B        0B
/               48G       30G       16G       65%
```

I did not prune dangling images because `mcp/context7:<none>` is unrelated to this backend runtime and may be useful to other active tooling. I did not touch the running MLflow container or frontend preview.

## Process Check

Final listeners:

```text
0.0.0.0:8080  uvicorn pid 26096
0.0.0.0:4174  node/vite preview pid 12534
0.0.0.0:5000  voice-ai-mlflow container
```

Final zombie/hung-process check:

```bash
ps -eo pid,ppid,stat,etime,cmd | rg -i '[d]ocker build|[a]pt-get|[p]ip ' || true
ps -eo pid,ppid,stat,etime,cmd | awk '$3 ~ /Z/ {print}'
```

Result: no matching `docker build`, `apt-get`, `pip`, or zombie processes remained.

## Remaining Blockers

- There is still no durable backend Docker image. The public backend is currently a host `.venv` uvicorn process in tmux.
- Host runtime has no `ffmpeg` binary, so video localization capability reports `ffmpeg_available=false`. TTS is healthy.
- Host runtime has no `espeak-ng`; local fallback TTS would not work if OpenAI credentials were removed. Current public runtime uses OpenAI and is healthy.
- MLflow server is reachable and readiness passes, but synthesis artifact logging returned a non-blocking `/mlflow` permission warning from the host client path.

## Next Commands For PM/User

Check backend:

```bash
tmux -L voice-ai capture-pane -pt voice-ai-backend-recovery -S -120
curl -fsS http://127.0.0.1:8080/healthz
curl -fsS http://127.0.0.1:8080/v1/product/capabilities
```

Restart host backend if needed:

```bash
tmux -L voice-ai kill-session -t voice-ai-backend-recovery
tmux -L voice-ai new-session -d -s voice-ai-backend-recovery -c /home/jhao/code/voice-ai \
  "set -a; . ./.env.runtime; set +a; export PORT=8080 ENVIRONMENT=public AUDIO_STORAGE_DIR=data/audio AUDIO_BASE_URL=http://103.27.237.252:8080/audio MLFLOW_TRACKING_URI=http://127.0.0.1:5000 VIDEO_JOB_DISPATCH_MODE=local_inline PYTHONUNBUFFERED=1; taskset -c 0-3 .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers 2>&1 | tee -a logs/backend-runtime-recovery-20260510.log"
```

Rebuild durable backend image later, only after confirming no other builds are running and Debian network is healthy:

```bash
ps -eo pid,ppid,stat,etime,cmd | rg -i '[d]ocker build|[a]pt-get|[p]ip ' || true
curl -fsSI --connect-timeout 5 http://deb.debian.org/debian/ | sed -n '1,5p'
taskset -c 0-3 docker build --progress=plain -t voice-ai:durable-20260510 .
```

Then run the container only after preserving the working host runtime or scheduling a short cutover window.

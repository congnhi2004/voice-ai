# Infra Local Speech Runtime Report - 2026-05-10

## Files Changed

- `Dockerfile`
  - Added Debian package `espeak-ng` to the existing runtime `apt-get install --no-install-recommends` layer.
  - Left backend provider code, frontend code, compose service shape, and local service helper behavior unchanged.
- `docs/subagents/infra-local-speech-runtime-report-20260510.md`
  - This runtime verification and restart report.

## Docs And Context7 Sources

- Context7 via MCP Docker:
  - Resolved Docker docs as `/docker/docs`.
  - Fetched topic: `Dockerfile RUN apt-get install no-install-recommends healthcheck entrypoint build cache`.
  - Used for Dockerfile install-layer guidance: combine `apt-get update` and `apt-get install`, use `--no-install-recommends`, and remove `/var/lib/apt/lists/*`.
- Docker official docs:
  - https://docs.docker.com/build/building/best-practices/
  - Confirmed the same Debian-based image `apt-get` pattern.
- eSpeak NG official GitHub:
  - https://github.com/espeak-ng/espeak-ng
  - Confirms eSpeak NG is a command-line TTS program and can produce WAV output.
- Debian package docs:
  - https://packages.debian.org/sid/espeak-ng
  - Confirms package `espeak-ng` is a command-line speech synthesizer package.
- Debian manpage:
  - https://manpages.debian.org/bullseye/espeak-ng/espeak-ng.1.en.html
  - Confirmed `--voices=<language code>` voice listing and command-line examples.

## Image And Build Status

- Config and lint checks:
  - `docker compose config --quiet` passed.
  - `docker build --check .` passed with no warnings.
  - `bash -n scripts/local-services.sh` passed.
- Backend tests after the backend fallback worker changes appeared in the workspace:
  - Initial `taskset -c 0-3 ./.venv/bin/pytest tests/backend/test_api.py -q` failed because `PYTHONPATH` did not include the repo root.
  - `PYTHONPATH=. taskset -c 0-3 ./.venv/bin/pytest tests/backend/test_api.py -q` passed: `17 passed, 3 skipped, 2 warnings`.
- Docker image build:
  - `taskset -c 0-3 docker build -t voice-ai:durable-20260510 .` passed.
  - Final image ID: `sha256:daf0416f7f3da04a9299df9839decce5ca4b1fb718bdf360433a76f79d666234`.
  - Image size from Docker inspect: `480181828` bytes.

## Runtime Verification Of Speech Engine

- Verified inside `voice-ai:durable-20260510`:
  - `command -v espeak-ng` -> `/usr/bin/espeak-ng`.
  - `espeak-ng --version` -> `eSpeak NG text-to-speech: 1.52.0`.
  - `espeak-ng --voices=vi` lists:
    - `vi` / `Vietnamese_(Northern)`
    - `vi-vn-x-central` / `Vietnamese_(Central)`
    - `vi-vn-x-south` / `Vietnamese_(Southern)`
- Verified WAV generation inside the image:
  - `espeak-ng -v vi-vn-x-central -w /tmp/vi.wav ...`
  - Generated file was `132106` bytes and started with RIFF/WAVE header.
- Verified running public backend container after restart:
  - `docker exec voice-ai-backend command -v espeak-ng` -> `/usr/bin/espeak-ng`.
  - `GET http://103.27.237.252:8080/readyz` returns provider `name=local`, `ready=true`, `detail="speech engine: espeak-ng"`.
  - `GET /v1/voices?language_code=vi-VN` returns `local-vi-VN-espeak-ng-central`.
  - `POST /v1/synthesize` with Vietnamese text returned provider `{"name":"local","fallback":true,"model":"espeak-ng-spoken-wav"}`, sample rate `22050`, audio bytes `159684`.
  - Downloaded audio started with RIFF/WAVE header.
- FFmpeg sanity check still passes in the image:
  - `ffmpeg -version` reports `7.1.3-0+deb13u1`.

## Restart Command

The backend fallback worker changes were present before restart, so I restarted the public stack in explicit local mode without printing or requiring secrets:

```bash
env -u OPENAI_API_KEY TTS_PROVIDER=local IMAGE=voice-ai:durable-20260510 taskset -c 0-3 ./scripts/local-services.sh restart
```

The helper reported:

- backend health reachable at `http://127.0.0.1:8080/healthz`
- frontend reachable at `http://127.0.0.1:4174/`

Current lifecycle/status command:

```bash
taskset -c 0-3 ./scripts/local-services.sh status
```

## Public URL Impact

- Public frontend remains up:
  - `http://103.27.237.252:4174/` returned `HTTP/1.1 200 OK`.
- Public backend now runs image `voice-ai:durable-20260510` with local TTS provider:
  - `backend tts provider: local`
  - `backend OPENAI_API_KEY: unset`
  - `GET http://103.27.237.252:8080/readyz` reports `speech engine: espeak-ng`.
- Expected user-visible change:
  - Local fallback should now produce spoken WAV audio through eSpeak NG instead of deterministic sine beep, assuming the frontend calls the restarted backend on port `8080`.

## Residual Risks

- eSpeak NG uses formant synthesis. It is spoken audio, but not natural neural TTS quality.
- The public stack is still managed by tmux and local Docker. A host reboot, Docker daemon restart, tmux server kill, or manual stop will require the restart command above.
- If another operator restarts with `TTS_PROVIDER=openai` and a valid key, public behavior will switch back to OpenAI metadata and `fallback=false`.
- If backend source changes again after this report, rebuild `voice-ai:durable-20260510` and rerun the `/readyz`, `/v1/voices`, and `/v1/synthesize` checks.

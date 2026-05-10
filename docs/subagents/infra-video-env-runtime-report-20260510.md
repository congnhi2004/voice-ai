# Infra Video Env Runtime Report - 2026-05-10

## Scope

Infra-only update for local backend runtime environment pass-through. No backend app, frontend app, deploy, root docs, or unrelated report files were edited.

## Files Changed

- `scripts/local-services.sh`
- `.env.example`
- `docs/subagents/infra-video-env-runtime-report-20260510.md`

## Runtime Env Pass-Through

The local backend container now passes these video localization environment variables from `.env.runtime` or the selected `RUNTIME_ENV_FILE` into Docker:

- `LOCALIZATION_PROVIDER`
- `OPENAI_TRANSCRIPTION_MODEL`
- `OPENAI_TRANSLATION_MODEL`

The script no longer hardcodes `LOCALIZATION_PROVIDER=local` in the backend `docker run` command.

## Status Reporting

`scripts/local-services.sh status` now reports only set/unset state for:

- `LOCALIZATION_PROVIDER`
- `OPENAI_TRANSCRIPTION_MODEL`
- `OPENAI_TRANSLATION_MODEL`

No secret values are printed by the status path.

## Documentation

`.env.example` now documents:

- `LOCALIZATION_PROVIDER=auto`
- `OPENAI_TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe`
- `OPENAI_TRANSLATION_MODEL=gpt-4o-mini`

## Context7

- Library ID: `/docker/cli`
- Topic: `docker run environment variables --env`
- Relevant guidance used: Docker `docker run -e NAME` passes the value from the host environment into the container when the variable is exported.

## Verification

Commands run:

```bash
taskset -c 0-3 bash -n scripts/local-services.sh
taskset -c 0-3 bash scripts/local-services.sh status
taskset -c 0-3 bash scripts/local-services.sh restart
taskset -c 0-3 bash scripts/local-services.sh status
taskset -c 0-3 curl -fsS --max-time 3 http://127.0.0.1:8080/readyz
```

Post-restart status confirmed:

- `backend LOCALIZATION_PROVIDER: set`
- `backend OPENAI_TRANSCRIPTION_MODEL: set`
- `backend OPENAI_TRANSLATION_MODEL: set`

Post-restart `/readyz` confirmed:

```json
{
  "video_localization": {
    "mode": "auto",
    "ready": true,
    "ffmpeg_available": true,
    "provider": "openai",
    "detail": "auto mode uses OpenAI when OPENAI_API_KEY is set; local fallback remains available without credentials"
  }
}
```

## PM Acceptance Command

```bash
taskset -c 0-3 bash scripts/local-services.sh restart && taskset -c 0-3 curl -fsS --max-time 3 http://127.0.0.1:8080/readyz
```

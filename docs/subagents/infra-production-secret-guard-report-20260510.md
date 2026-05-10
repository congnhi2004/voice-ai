# Infra Production Secret Guard Report - 2026-05-10

Role: Infra Production Secret Guard Agent
Skill: `voice-ai-infra-observability`
Scope: `scripts/local-services.sh`, `.env.example`, and this report. No backend, frontend, Dockerfile, or other report files were edited.

## Files Changed

- `scripts/local-services.sh`
  - Loads an untracked runtime env file before applying runtime defaults.
  - Default lookup is `.env.runtime` when present, otherwise `.env.local`; operators can override with `RUNTIME_ENV_FILE=/path/to/file`.
  - Adds production guard support through `PUBLIC_DEMO_PROFILE=production` or `REQUIRE_REAL_TTS=1`.
  - Rejects `start` and `restart` before container teardown when the guarded public profile would run `TTS_PROVIDER=local`, unsupported providers, or a real provider without required credentials.
  - Keeps developer local mode possible when the guard is not enabled.
  - Changes runtime `status` output for backend envs to set/unset only.
- `.env.example`
  - Documents placeholder-only public runtime guard settings.
  - Documents that real values belong in untracked `.env.runtime` or `.env.local`.
- `.gitignore`
  - No change needed. Existing rules already ignore `.env` and `.env.*` while allowing `.env.example`.
- `docs/subagents/infra-production-secret-guard-report-20260510.md`
  - This verification and operator handoff.

## Context7 Sources

- MCP Docker Context7 `resolve_library_id`: selected `/docker/compose`.
- MCP Docker Context7 `get_library_docs`: topic `env_file environment variable precedence interpolation`.
- Relevant notes used:
  - Compose supports `env_file`/`environment` style runtime configuration and `docker compose config` for effective config validation.
  - Compose publishing can include envs if explicitly requested, so runtime secret files should stay untracked and out of publish artifacts.

## Server Configuration

Create this file on the public server only. Do not commit it:

```bash
cd /home/jhao/code/voice-ai
install -m 600 /dev/null .env.runtime
editor .env.runtime
```

Recommended production public runtime contents:

```bash
PUBLIC_DEMO_PROFILE=production
REQUIRE_REAL_TTS=1
TTS_PROVIDER=openai
OPENAI_API_KEY=CHANGE_ME_ON_SERVER_ONLY
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE=marin
OPENAI_TTS_RESPONSE_FORMAT=wav
```

Safe restart and status commands:

```bash
cd /home/jhao/code/voice-ai
taskset -c 0-3 ./scripts/local-services.sh restart
taskset -c 0-3 ./scripts/local-services.sh status
```

Use an alternate untracked file if needed:

```bash
RUNTIME_ENV_FILE=/secure/path/voice-ai.env taskset -c 0-3 ./scripts/local-services.sh restart
```

## Tests

Commands run:

```bash
taskset -c 0-3 bash -n scripts/local-services.sh
taskset -c 0-3 ./scripts/local-services.sh status
```

Results:

- Shell syntax check passed.
- Status completed against the running public stack.
- Status printed only set/unset for backend TTS and credential-related envs.
- No secret values were printed.

Safe runtime env load check with a temporary non-secret file:

```bash
RUNTIME_ENV_FILE=/tmp/non-secret-test-env taskset -c 0-3 ./scripts/local-services.sh status
```

Result:

- Status reported `runtime env file: loaded`.
- The running backend was not restarted by this check.
- Backend env output stayed set/unset only.

Guard rejection check:

```bash
RUNTIME_ENV_FILE=/tmp/guard-missing.env taskset -c 0-3 ./scripts/local-services.sh restart
```

Temporary file contents used for the check:

```bash
PUBLIC_DEMO_PROFILE=production
REQUIRE_REAL_TTS=1
TTS_PROVIDER=local
```

Result:

- Command exited `1`.
- Error: `Refusing to start production public profile: TTS_PROVIDER=local would use local fallback audio.`
- `voice-ai-backend` stayed running before and after the rejected restart.

## Why This Prevents Accidental eSpeak/Local Voice

Previously, `scripts/local-services.sh` defaulted to `TTS_PROVIDER=local`, so a manual restart without OpenAI envs could silently put the public web back on local eSpeak fallback while health checks stayed green.

With `.env.runtime` present and guarded by `PUBLIC_DEMO_PROFILE=production` or `REQUIRE_REAL_TTS=1`, the restart path loads the server-side OpenAI env first and validates it before stopping the existing stack. If OpenAI is not configured, or if the provider would be `local`, the script exits before touching the running containers. That keeps the public profile from silently degrading to local fallback audio.

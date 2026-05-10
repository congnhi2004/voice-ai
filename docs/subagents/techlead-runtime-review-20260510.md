# Tech Lead Runtime Review - 2026-05-10

Role: Techlead Runtime Reviewer
Skill: `voice-ai-techlead-reviewer`
Scope: uncommitted runtime/env changes and public runtime readiness for real OpenAI TTS, local fallback behavior, MLflow host handling, GitHub push readiness, and public URL acceptance.
Write scope honored: this report only.

## Release Recommendation

**Block release for user-facing/public acceptance.** The public services are reachable, but the live backend is still running local fallback TTS with `OPENAI_API_KEY` unset, so the reported "audio only a beep" behavior is expected. MLflow host allowlisting is improved, but public TTS responses can still return `mlflow_run_id: null` with artifact logging warnings. This is acceptable for a clearly labeled local demo, not for real OpenAI TTS acceptance.

## Findings

### P1 - Public backend is not using real OpenAI TTS

Evidence:

- `taskset -c 0-3 ./scripts/local-services.sh status` reported:
  - `backend tts provider: local`
  - `backend OPENAI_API_KEY: unset`
  - `backend openai tts: model=default voice=default format=default`
- `GET http://103.27.237.252:8080/readyz` returned `provider.name=local`, `provider.ready=true`.
- `GET http://103.27.237.252:8080/v1/voices` returned only local voices.
- Public synth request `X-Request-ID: techlead-runtime-review-20260510` returned:
  - `provider: {"name":"local","fallback":true,"model":"deterministic-wav-tone-demo"}`
  - `audio_url: http://103.27.237.252:8080/audio/tts_861a2a00b5a049c381ebab0256e96fc4.wav`
  - `audio.bytes: 96044`, `content_type: audio/wav`

Affected surface:

- Public backend `http://103.27.237.252:8080/`
- Public frontend `http://103.27.237.252:4174/`
- Runtime env pass-through in `scripts/local-services.sh:17-27`, `scripts/local-services.sh:65-75`, `scripts/local-services.sh:113-114`

Impact:

- Users will hear deterministic tone/beep output, not natural TTS.
- `readyz` can be green while the app is only ready for demo fallback, not real TTS acceptance.

Required fix:

- Restart runtime with `TTS_PROVIDER=openai` and `OPENAI_API_KEY` set in the process environment, then verify `status`, `/readyz`, `/v1/voices`, and `/v1/synthesize` all report `provider.name=openai` and `fallback=false`.
- Keep reporting only set/unset for `OPENAI_API_KEY`; do not print the secret.

### P1 - MLflow readiness is improved but artifact logging is still not acceptance-clean

Evidence:

- Previous logs showed MLflow rejecting `voice-ai-mlflow:5000` with `Invalid Host header`; the new `--allowed-hosts` appears active. Current `logs/mlflow.log` includes `Allowed hosts: voice-ai-mlflow, voice-ai-mlflow:5000, localhost, and 7 more` and later `200 OK` for `GET /api/2.0/mlflow/experiments/get-by-name`.
- Official MLflow docs say `--allowed-hosts` controls accepted Host headers to prevent DNS rebinding attacks.
- Current public synth response still returned `observability.mlflow_run_id: null` with warning `MLflow tracking failed: [Errno 13] Permission denied: '/mlflow'`.
- `docker exec voice-ai-backend ...` showed `MLFLOW_TRACKING_URI=http://voice-ai-mlflow:5000`; `/mlflow` was not present in that container at the time checked.
- `app/observability.py:22-32` readiness only checks `set_experiment`; it does not verify a full run create/log artifact path.
- `app/observability.py:100-111` logs metadata and optionally audio artifacts; exceptions cause `MlflowResult(run_id=None, warning=...)` at `app/observability.py:113-114`.

Affected surface:

- Runtime MLflow tracking and `/readyz`
- `scripts/local-services.sh:104-114`
- `docker-compose.yml:43-63`
- `app/observability.py:22-32`, `app/observability.py:100-114`

Impact:

- `/readyz` can report MLflow ready while TTS responses lose the run id.
- Acceptance evidence is incomplete, especially for public URL demos where generated audio should link to traceable telemetry.

Required fix:

- Make readiness verify the same operation required by acceptance, or add a separate smoke check that creates a temporary run and logs the expected artifact class.
- Fix artifact storage mode for remote MLflow: either disable audio artifact upload for this local public demo, mount and permission `/mlflow` correctly in the backend container, or configure MLflow artifact serving so the client does not try to write to an unavailable local `/mlflow` path.
- Retest `POST /v1/synthesize` and require non-null `mlflow_run_id` with no observability warnings.

### P1 - Branch is not push-ready from this server

Evidence:

- Local branch reports `main`, not the context branch `wip/voice-ai-production-prototype`.
- `git status --short --branch` showed uncommitted modifications in `.env.example`, `docker-compose.yml`, `docs/subagents/infra-report.md`, and `scripts/local-services.sh`.
- `git remote -v` uses HTTPS: `https://github.com/congnhi2004/voice-ai.git`.
- `GIT_TERMINAL_PROMPT=0 git push --dry-run origin HEAD` failed with `fatal: could not read Username for 'https://github.com': terminal prompts disabled`.
- Official GitHub docs say a personal access token can be used instead of a password for Git operations over HTTPS, and tokens should be treated like passwords.

Affected surface:

- Release/PR publication from this server.

Impact:

- This server cannot currently push the branch non-interactively.
- The branch mismatch risks committing runtime changes to `main` instead of the intended working branch.

Required fix:

- Confirm the intended branch and switch only when safe with the current dirty worktree.
- Configure GitHub authentication through a secure credential manager, GitHub CLI, SSH key, or PAT entered through the normal credential flow. Do not write tokens into repo files or logs.
- Commit only after the runtime fixes and report are reviewed.

### P2 - Runtime pass-through is directionally correct but defaults still preserve demo fallback

Evidence:

- `.env.example:20-24` adds OpenAI TTS placeholders without a secret value.
- `docker-compose.yml:12-16` and `docker-compose.yml:81-86` pass OpenAI TTS env vars into app/worker.
- `scripts/local-services.sh:17-27` allowlists OpenAI env vars and `scripts/local-services.sh:140-145` reports secret presence without printing the value.
- `scripts/local-services.sh:65-67` still defaults `TTS_PROVIDER` to `local`.
- Backend provider code supports OpenAI and validates missing key/format/voice at `app/providers.py:238-294`.
- Official OpenAI docs confirm `/v1/audio/speech`, `gpt-4o-mini-tts`, `coral`, and `wav` response format are valid/current.

Affected surface:

- Runtime startup path for local public demo and compose.

Impact:

- The changes enable real TTS when the environment is set, but they do not themselves make the public service use OpenAI.
- Operators can accidentally restart back into local beep mode and see green health checks.

Required fix:

- Add an operator-facing post-restart acceptance gate: `TTS_PROVIDER=openai`, key set, `/readyz` provider openai, `/v1/voices` provider openai, synth provider openai/fallback false, playable audio URL, MLflow run id present.
- Consider making user-testing startup fail fast when `TTS_PROVIDER=openai` is requested but `OPENAI_API_KEY` is unset.

## Public URL Acceptance

Checked:

- `GET http://103.27.237.252:8080/healthz`: `200`, `{"status":"ok","service":"voice-ai","version":"0.1.0"}`
- `GET http://103.27.237.252:8080/readyz`: `200`, but provider is `local`
- `HEAD http://103.27.237.252:8080/openapi.json`: `200`
- `HEAD http://103.27.237.252:4174/`: `200`
- `GET http://103.27.237.252:8080/v1/product/capabilities`: `active_provider=local`, `local_fallback=true`, `mode=demo`
- `GET http://103.27.237.252:8080/v1/demo/workspace`: `demo_only=true`, `mlflow_configured=true`
- `HEAD http://103.27.237.252:5000/`: `200` after MLflow allow-hosts change

Acceptance result:

- Public URLs are reachable.
- Real TTS acceptance fails because active provider is local fallback.
- MLflow acceptance is partial: host handling works, but public TTS response did not include a usable run id for the review request.

## Official Docs Checked

- OpenAI Text to Speech guide: `https://developers.openai.com/api/docs/guides/text-to-speech`
  - Confirmed `/v1/audio/speech`, `gpt-4o-mini-tts`, `coral`, configurable output format, and `wav` support.
- GitHub PAT docs: `https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens`
  - Confirmed PAT use for HTTPS Git command-line auth and token secrecy guidance.
- MLflow network security docs: `https://mlflow.org/docs/latest/self-hosting/security/network/`
  - Confirmed `--allowed-hosts` purpose and remote tracking server host allowlist pattern.

## Context7

Not used. This review did not need current framework/library API details beyond official service/runtime documentation already checked through built-in web search. No product code or library API changes were made.

## Verification Commands

- `git status --short --branch`
- `git diff -- .env.example docker-compose.yml scripts/local-services.sh docs/subagents/infra-report.md`
- `taskset -c 0-3 ./scripts/local-services.sh status`
- `taskset -c 0-3 curl -fsS http://103.27.237.252:8080/healthz`
- `taskset -c 0-3 curl -fsS http://103.27.237.252:8080/readyz`
- `taskset -c 0-3 curl -fsSI http://103.27.237.252:8080/openapi.json`
- `taskset -c 0-3 curl -fsSI http://103.27.237.252:4174/`
- `taskset -c 0-3 curl -fsS http://103.27.237.252:8080/v1/voices`
- `taskset -c 0-3 curl -fsS -H 'Content-Type: application/json' -H 'X-Request-ID: techlead-runtime-review-20260510' -d '{...}' http://103.27.237.252:8080/v1/synthesize`
- `taskset -c 0-3 curl -fsSI http://103.27.237.252:5000/`
- `taskset -c 0-3 tail -n 120 logs/backend.log`
- `taskset -c 0-3 tail -n 120 logs/mlflow.log`
- `taskset -c 0-3 docker exec voice-ai-backend sh -c 'id; printf "MLFLOW_TRACKING_URI=%s\n" "$MLFLOW_TRACKING_URI"; ls -ld /mlflow 2>&1 || true; ls -ld /app /app/data /app/data/audio 2>&1 || true'`
- `GIT_TERMINAL_PROMPT=0 git push --dry-run origin HEAD`
- `taskset -c 0-3 bash -n scripts/local-services.sh`

Tests not run:

- `taskset -c 0-3 python -m pytest tests/backend/test_api.py -q` failed because `python` is not installed on PATH.
- `taskset -c 0-3 python3 -m pytest tests/backend/test_api.py -q` failed because `/usr/bin/python3` has no `pytest` module.

## Residual Risk

- I did not run a real OpenAI synthesis because `OPENAI_API_KEY` is unset and secrets must not be printed or inferred.
- The OpenAI provider has mocked unit coverage in `tests/backend/test_api.py`, but it was not executable in this server environment due missing pytest.
- The public service is currently a local demo with in-memory auth and local filesystem storage; this remains unsuitable for production release without the existing production storage/auth work.

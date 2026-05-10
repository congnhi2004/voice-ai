# Backend OpenAI Voice Quality Report - 2026-05-10

## Sources

- OpenAI official API reference, Audio speech: `https://platform.openai.com/docs/api-reference/audio/voice-object?lang=curl`
  - Current built-in TTS voices include `alloy`, `ash`, `ballad`, `coral`, `echo`, `fable`, `onyx`, `nova`, `sage`, `shimmer`, `verse`, `marin`, and `cedar`.
  - `gpt-4o-mini-tts` is an available speech model.
- OpenAI official text-to-speech guide: `https://platform.openai.com/docs/guides/text-to-speech`
  - Recommends `marin` or `cedar` for best quality.
  - Requires clear disclosure that generated TTS voice is AI-generated and not a human voice.
- OpenAI official TTS output format docs: `https://platform.openai.com/docs/guides/text-to-speech/quickstart?lang=curl`
  - Documents `mp3`, `opus`, `aac`, `flac`, `wav`, and `pcm`; this backend pass preserved existing `wav`/`mp3` behavior to avoid widening API encoding semantics outside the requested voice fix.
- Context7:
  - `/openai/openai-python`, topic `audio speech create text to speech response_format`.
  - `/fastapi/fastapi`, topic `TestClient exception handlers HTTPException validation testing`.

## Changed Files

- `app/config.py`
  - OpenAI default voice is now `marin` instead of `coral`.
  - `coral` remains valid when explicitly configured or requested.
- `app/providers.py`
  - OpenAI built-in voice catalog now includes `marin` and `cedar`.
  - `/v1/voices` lists `marin` and `cedar` first for OpenAI, while preserving existing voices including `coral`, `alloy`, `nova`, etc.
  - Invalid OpenAI request/config voices raise a specific `UnsupportedVoiceError`.
- `app/main.py`
  - OpenAI invalid request voice now returns `400` with `error.code=unsupported_voice` instead of silently falling back or surfacing as a generic provider failure.
- `tests/backend/test_api.py`
  - Added coverage for `marin`/`cedar` readiness, listing, request acceptance, default `marin`, existing `coral`, and invalid voice rejection.

Note: these files already had uncommitted local speech fallback edits in the workspace before this pass; this report covers the OpenAI voice-quality changes made in this pass.

## Behavior Change

- `OPENAI_TTS_VOICE=marin` no longer makes `/readyz` fail.
- `OPENAI_TTS_VOICE=cedar` is also accepted.
- If no per-request OpenAI voice name is supplied, the backend uses `marin` by default for better quality.
- Existing request/config voices such as `coral`, `alloy`, `nova`, `echo`, and the rest of the prior catalog still work.
- A bad per-request OpenAI voice such as `not-a-real-openai-voice` returns `400 unsupported_voice` with the supported voice list.
- No secrets were added to code or tests. Tests use dummy API keys and mocked OpenAI clients only.

## Test Results

Command:

```bash
taskset -c 0-3 env PYTHONPATH=. .venv/bin/pytest tests/backend/test_api.py -q
```

Result:

```text
21 passed, 3 skipped, 2 warnings in 1.95s
```

Earlier attempts:

- `taskset -c 0-3 pytest tests/backend/test_api.py -q` failed because `pytest` is not on PATH.
- `.venv/bin/pytest` without `PYTHONPATH=.` failed test collection because `app` was not importable from that invocation.

## PM Acceptance Steps For Public Runtime

1. Deploy/restart backend with the existing secret mechanism; do not print `OPENAI_API_KEY`.
2. Configure:

```bash
TTS_PROVIDER=openai
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE=marin
OPENAI_TTS_RESPONSE_FORMAT=wav
```

3. Verify readiness:

```bash
curl -sS "$BASE/readyz"
```

Expected: HTTP `200`, provider `openai`, provider ready `true`.

4. Verify voice catalog:

```bash
curl -sS "$BASE/v1/voices?language_code=vi-VN"
```

Expected: provider `openai`, voices include `marin`, `cedar`, and `coral`.

5. Verify synthesis without exposing secrets:

```bash
curl -sS "$BASE/v1/synthesize" \
  -H "Content-Type: application/json" \
  -d '{"text":"Xin chào, đây là kiểm thử giọng OpenAI marin.","voice":{"language_code":"vi-VN","name":"marin","ssml_gender":"NEUTRAL"},"audio":{"encoding":"LINEAR16","sample_rate_hz":24000},"metadata":{"client_reference_id":"pm-openai-marin-smoke"}}'
```

Expected: HTTP `200`, provider `openai`, audio URL/path returned, generated audio is real OpenAI TTS.

6. Optional fallback confirmation:

```bash
curl -sS "$BASE/v1/synthesize" \
  -H "Content-Type: application/json" \
  -d '{"text":"Xin chào, đây là kiểm thử giọng coral.","voice":{"language_code":"vi-VN","name":"coral","ssml_gender":"NEUTRAL"},"audio":{"encoding":"LINEAR16","sample_rate_hz":24000},"metadata":{"client_reference_id":"pm-openai-coral-smoke"}}'
```

Expected: HTTP `200`; `coral` still works as the conservative fallback voice.

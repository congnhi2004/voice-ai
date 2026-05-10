# Backend Local Speech Fallback Report - 2026-05-10

## Files Changed

- `app/providers.py`
  - Replaced deterministic sine-tone local TTS with an eSpeak NG subprocess backend.
  - Local provider metadata now reports `model=espeak-ng-spoken-wav`.
  - Local synthesis now calls `espeak-ng -w <tmp>/speech.wav ... <text>`, validates WAV/RIFF output, and reads actual WAV duration/sample rate from the generated file.
  - Local readiness now fails clearly when the binary is missing.
  - OpenAI and Google provider behavior remains intact; only `ProviderSynthesisResult` gained `sample_rate_hz`.
- `app/config.py`
  - Added `ESPEAK_NG_PATH`, defaulting to `espeak-ng`.
- `app/main.py`
  - Response and MLflow sample-rate metadata now use the actual provider output sample rate.
- `tests/backend/test_api.py`
  - Updated local fallback expectations from deterministic tone to eSpeak NG speech metadata.
  - Added fake eSpeak NG subprocess coverage for local WAV generation.
  - Added missing-binary coverage proving the local provider fails clearly instead of producing a beep.

## Docs, Web, and Context7 Sources

- eSpeak NG GitHub README: confirms eSpeak NG is a command-line speech synthesizer, supports more than 100 languages/accents, and can produce WAV output.
  - https://github.com/espeak-ng/espeak-ng
- eSpeak command docs: `-w <wave file>` writes speech output to a WAV file, `-v` selects a voice, `--voices=<language code>` lists matching voices.
  - https://espeak.sourceforge.net/commands.html
- eSpeak NG languages docs: Vietnamese voice identifiers include `vi`, `vi-vn-x-central`, and `vi-vn-x-south`.
  - https://github.com/espeak-ng/espeak-ng/blob/master/docs/languages.md
- Context7:
  - Resolved `/fastapi/fastapi`.
  - Fetched topic: `TestClient response_model HTTPException tests`.

## Behavior Change

- Before: local TTS always generated a deterministic sine beep and reported `deterministic-wav-tone-demo`.
- After: local TTS requires eSpeak NG and generates spoken WAV/RIFF audio through the local speech engine.
- If eSpeak NG is unavailable:
  - `/readyz` returns provider not ready with `espeak-ng binary is not available; install espeak-ng or set ESPEAK_NG_PATH`.
  - `/v1/synthesize` returns `503 synthesis_failed` with the same clear dependency error.
- This deliberately avoids silently falling back to a beep.

## Tests Run

- `taskset -c 0-3 pytest tests/backend/test_api.py`
  - Failed because `pytest` was not on PATH.
- `taskset -c 0-3 python3 -m pytest tests/backend/test_api.py`
  - Failed because system Python has no `pytest` module.
- `PYTHONPATH=. taskset -c 0-3 ./.venv/bin/pytest tests/backend/test_api.py`
  - Passed: `17 passed, 3 skipped, 2 warnings`.
  - The 3 skipped tests are FFmpeg-backed MP4 fixture tests skipped by the existing fixture when local FFmpeg is unavailable in this environment.

## Sample Audio Check

- This local workstation currently does not have `espeak-ng` in PATH, so I could not generate a real eSpeak sample artifact here.
- The backend test path uses a fake eSpeak subprocess that writes a WAV/RIFF file and verifies:
  - provider metadata is `{"name":"local","fallback":true,"model":"espeak-ng-spoken-wav"}`;
  - the command starts with `espeak-ng -b 1 -v en-us`;
  - audio content starts with `RIFF`;
  - stored WAV has one channel, nonzero frames, and sample-rate metadata comes from the actual WAV.

## Remaining Infra Dependency

- Runtime image/host must have `espeak-ng` installed and available as `espeak-ng`, or set `ESPEAK_NG_PATH` to the installed binary.
- No OpenAI secrets or provider settings were changed.
- OpenAI remains selected when `TTS_PROVIDER=openai` or `TTS_PROVIDER=auto` with a healthy `OPENAI_API_KEY`.

## PM Public URL Acceptance Criteria

For public runtime at `http://103.27.237.252:4174/` with backend API on the same deployed backend:

1. Restart backend with eSpeak NG installed in the runtime container/host.
2. `GET /readyz` returns HTTP 200 and provider:
   - `name=local`
   - `ready=true`
   - `detail` includes `speech engine: espeak-ng`
3. `GET /v1/voices?language_code=vi-VN` returns a local Vietnamese eSpeak voice such as `local-vi-VN-espeak-ng-central`.
4. `POST /v1/synthesize` with Vietnamese text returns HTTP 200 and provider:
   - `name=local`
   - `fallback=true`
   - `model=espeak-ng-spoken-wav`
5. Downloaded `audio_url` starts with `RIFF`, opens as WAV, has nonzero frames, and audibly contains spoken speech rather than a pure tone/beep.
6. The response must not contain `deterministic-wav-tone-demo`.
7. If `OPENAI_API_KEY` is later activated with `TTS_PROVIDER=openai` or healthy `auto`, the same endpoint should report OpenAI metadata and `fallback=false`.

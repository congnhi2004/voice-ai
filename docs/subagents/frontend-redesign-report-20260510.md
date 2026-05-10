# Frontend redesign report - 2026-05-10

## Objective

Redesign the public frontend into a production-grade Voice AI product surface where the first viewport lets a user test text-to-real-voice immediately.

## Research sources and design decisions

- OpenAI Text to speech docs: https://platform.openai.com/docs/guides/text-to-speech?lang=node
  - Decision: make TTS the first workflow; expose voice, language, output encoding, speed, pitch, gain, audio playback, and download. Added clear AI-generated voice disclosure in the TTS form.
- OpenAI Audio API reference: https://platform.openai.com/docs/api-reference/audio/voice-object?lang=curl
  - Decision: align copy and voice selection around current built-in OpenAI voice IDs returned by the public backend.
- 21st.dev help: https://help.21st.dev/
  - Decision: use a modern prompt/studio pattern rather than a landing-page-only hero.
- ElevenLabs help: https://help.elevenlabs.io/hc/en-us/articles/40507998995601-What-features-are-available-in-the-ElevenLabs-mobile-app
  - Decision: keep generated clips, playback, library/history, and voice selection visible as first-class product concepts.
- Murf Studio basics: https://help.murf.ai/murf-studio-basics
  - Decision: voice choice, script editor, voice settings, preview, and export should be visible in the studio flow.
- Synthesia AI Dubbing docs: https://docs.synthesia.io/docs/video-dubbing
  - Decision: preserve video localization as a secondary workflow with upload, source language, transcript/SRT/audio/video artifacts, and review states.
- HeyGen Translate page: https://www.heygen.com/translate/
  - Decision: trust/product copy should frame video translation around dubbing, subtitles, and localization use cases below the TTS-first viewport.
- Context7: `/vitejs/vite/v7.0.0`, topic `env variables public base path build preview`
  - Decision: keep `VITE_API_BASE_URL` and runtime public-host derivation; do not expose non-`VITE_` env vars; verify with `npm run build` and public bundle inspection.

## Files changed

- `frontend/index.html`
- `frontend/src/api.ts`
- `frontend/src/e2e/app.spec.ts`
- `frontend/src/main.ts`
- `frontend/src/styles.css`

## UX states implemented

- First viewport now defaults to `Text to real voice studio`.
- TTS flow includes script input, OpenAI/backend status, voice selection, language selection, encoding, speaking rate, pitch, volume gain, generate button, loading skeleton, empty state, error banner, audio player, metadata, download link, and browser-local history.
- Added visible AI voice disclosure in the TTS workflow.
- Video localization remains available as a second tab with upload, source language, Vietnamese voice, subtitle burn option, demo review state, pipeline stages, artifacts, preview panes, and job history.
- Product, workflow, pricing, trust/security, docs, login/register demo surfaces remain below the functional studio.

## API and public URL verification

- Public frontend checked at `http://103.27.237.252:4174/`; returned the updated title `Voice AI Text to Real Voice Studio`.
- Public backend checked at `http://103.27.237.252:8080/readyz`; returned `status=ready`, provider `openai`, storage ready, MLflow ready.
- Public voices checked at `http://103.27.237.252:8080/v1/voices`; returned OpenAI voices including `alloy`, `ash`, `ballad`, `coral`, `echo`, `fable`, `nova`, `onyx`, `sage`, `shimmer`, and `verse`.
- Public TTS smoke test posted to `/v1/synthesize`; returned `status=succeeded`, provider `openai`, model `gpt-4o-mini-tts`, and a downloadable WAV artifact.
- Public bundle inspection confirms API base derivation still uses `http(s)://<public-host>:8080`; for `103.27.237.252:4174`, this resolves to `http://103.27.237.252:8080`.
- Video FormData was corrected to match the public OpenAPI fields: `file`, `source_language`, `target_language`, and `voice_name`.

## Test commands and results

- `taskset -c 0 npm run lint` - passed.
- `taskset -c 0 npm run test` - passed, 4 Vitest tests.
- `taskset -c 0 npm run build` - passed, Vite production build completed.
- `taskset -c 0 npm run test:e2e` - blocked by environment dependency, not app assertion failure. Chromium failed to launch because `libgbm.so.1` is missing. Attempted system install with `sudo apt-get install ...`, but sudo requires a password in this environment.

## Screenshots

- Required new Playwright screenshots were not captured because Chromium cannot launch without `libgbm.so.1`.
- Expected evidence directory remains `docs/subagents/evidence/images/`.
- Playwright generated failure traces under `frontend/test-results/`, but those are not visual acceptance screenshots.

## Remaining risks

- Visual desktop/mobile overlap and console checks still need to be rerun after installing the missing Playwright system dependency.
- The public frontend is updated by the current built `dist`, but a production deployment process should rebuild/restart explicitly if the server is not watching this workspace.
- Auth UI is still demo-workspace oriented; public OpenAPI exposes local-demo auth endpoints, but production identity/billing are not available yet.

# Frontend Video Acceptance Report - 2026-05-10

## Scope

Role: Frontend Video Acceptance Agent.

Write scope honored:

- `frontend/**`
- `docs/subagents/frontend-video-acceptance-report-20260510.md`

No backend, infra, scripts, root docs, or other reports were edited.

## Current Sources Checked

- Public OpenAPI surface: `http://103.27.237.252:8080/openapi.json`
  - Confirmed current public video endpoint is `POST /v1/video-localization/jobs`, `GET /v1/video-localization/jobs/{job_id}`, and artifact route `GET /v1/video-localization/jobs/{job_id}/artifacts/{filename}`.
- Public capabilities surface: `http://103.27.237.252:8080/v1/product/capabilities`
  - Confirmed source languages `en-US`, `en`, `zh-CN`, `zh`; target languages `vi`, `vi-VN`; artifacts include source video, transcript, SRT, VTT, voiceover audio, localized video.
- MDN file upload/media patterns:
  - File input `accept` is a chooser hint, not complete validation.
  - Native media controls and `preload="metadata"` remain appropriate for review playback without autoplay.

## Context7

- `/websites/v7_vite_dev`, topic `import.meta.env build static asset base url TypeScript vanilla app`
- `/microsoft/playwright`, topic `test locator setInputFiles route screenshot projects`

## Files Changed

- `frontend/src/api.ts`
  - Expanded video localization types for real job payloads: `running`, `canceled`, provider, input filename/bytes, segments, warnings, error, MLflow run id, artifact arrays, string artifact manifests, and VTT URLs.
- `frontend/src/main.ts`
  - Added client-side video upload validation for MP4, MOV, M4V, WebM, non-empty files, and 250 MB MVP limit.
  - Removed automatic deterministic demo-result fallback on backend failure. Backend failures now remain visible as errors.
  - Added segment-derived Vietnamese script and SRT previews when backend returns `segments` instead of fixed script text.
  - Made script/SRT previews readonly unless backend explicitly returns `script.editable: true`.
  - Added flexible artifact resolution for object maps, artifact metadata arrays, and string artifact names.
  - Added VTT download card, provider/updated/MLflow metadata, progressbar ARIA values, warning rendering, and broader pipeline stage matching.
- `frontend/src/styles.css`
  - Added warning-state styling for backend warnings.
- `frontend/src/e2e/app.spec.ts`
  - Updated video E2E mock to use arbitrary backend-returned segment text, artifact metadata arrays, VTT, readonly preview assertions, and final video URL assertion.
  - Added unsupported-file upload validation coverage that ensures the backend is not called.

## UX States Covered

- TTS remains the public first-screen workflow.
- Video upload validates missing file, unsupported extension/MIME, empty file, and oversize file before submit.
- Source language selector supports English and Chinese variants currently exposed by the public capabilities endpoint.
- Target remains Vietnamese.
- Video job progress supports queued/running/processing/succeeded/failed/canceled style responses and maps backend stage terms such as extract, transcribe, translate, subtitle, synth/dub, render/mux.
- Result rendering supports:
  - Backend-returned Vietnamese script text.
  - Segment-derived Vietnamese transcript text.
  - Backend-returned SRT.
  - Segment-derived SRT fallback.
  - Transcript, SRT, VTT, Vietnamese audio, and final MP4 downloads.
  - Native audio and video preview controls.
  - Backend warnings and job errors.
  - Request id and MLflow run id metadata when returned.

## Tests

Passed:

```bash
npm run test
npm run lint
npm run build
```

Results:

- Unit: 4 passed.
- TypeScript lint: passed.
- Production build: passed.

Playwright:

```bash
npm run test:e2e
```

Result: blocked by missing browser system dependency:

```text
chrome-headless-shell: error while loading shared libraries: libgbm.so.1: cannot open shared object file: No such file or directory
```

I checked for a system browser and `libgbm`; neither was available. Passwordless sudo is not available, so I could not install `libgbm1` in this session.

## Screenshot Paths

No new screenshots were captured because Playwright could not launch Chromium without `libgbm.so.1`.

Expected screenshot paths once the dependency is installed:

- `docs/subagents/frontend-tts-desktop.png`
- `docs/subagents/frontend-tts-mobile.png`
- `docs/subagents/frontend-video-desktop.png`
- `docs/subagents/frontend-video-mobile.png`

## Backend Assumptions

- The current public endpoint accepts multipart video uploads at `/v1/video-localization/jobs` with `file`, `source_language`, `target_language`, and optional `voice_name`.
- Backend may return artifacts as:
  - named URL/path object fields,
  - artifact metadata arrays with `type` and `download_url`,
  - or string artifact names resolved through `/v1/video-localization/jobs/{job_id}/artifacts/{filename}`.
- Backend may return Vietnamese text in `script.vietnamese_text` or in segment fields such as `translated_text` / `vietnamese_text`.
- Editable transcript/subtitle drafts are unsupported unless backend explicitly returns `script.editable: true`.
- Client upload validation is a usability guard only. Backend must remain authoritative for content type, file structure, duration, size, and security checks.

## Residual Risks

- Playwright visual evidence is blocked until `libgbm1` or an equivalent browser dependency set is installed.
- Public capabilities still report video localization `demo_mode: true`; frontend is ready to render real results, but production acceptance depends on backend returning real STT/translation/dubbing artifacts.
- Artifact arrays without URLs are resolved to the current public artifact route by artifact name. If backend later uses typed download endpoints instead of filenames, the frontend may need one additional resolver branch.

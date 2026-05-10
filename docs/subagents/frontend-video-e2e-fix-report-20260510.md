# Frontend Video E2E Fix Report - 2026-05-10

## Root Cause

The video workflow was mostly present, but automation had two unstable entry points:

- The hero CTA visible text was `Open video workflow`, while its accessible name was `Open video localization workflow`. Exact role/name lookups could miss it.
- On mobile, `.studio-intro` is hidden, so the hero CTA is not accessible. A mobile script looking for `Open video workflow` had no visible button even though the tab existed.

The real public submit also exposed an artifact resolver bug. The backend returns artifact `kind` values such as `voiceover_audio` and `localized_video`, but the frontend ignored `kind` and matched by path/url text. That allowed `source_audio` and `source_video` to be selected before the Vietnamese audio and localized MP4.

## Files Changed

- `frontend/src/main.ts`
- `frontend/src/api.ts`
- `frontend/src/styles.css`
- `frontend/src/e2e/app.spec.ts`

Build output was regenerated under `frontend/dist/` by `npm run build`.

## Selector Contract

Stable accessible selectors now used and verified:

- Open video workflow: `page.getByRole("button", { name: "Open video workflow", exact: true })`
- Video tab: `page.getByRole("tab", { name: "Video localization", exact: true })`
- File input: `page.getByLabel("Source video", { exact: true })`
- Submit: `page.getByRole("button", { name: "Start Vietnamese localization", exact: true })`

Stable test IDs remain available:

- `data-testid="open-video-workflow"`
- `data-testid="workflow-video-localization-tab"`
- `data-testid="video-file-input"`
- `data-testid="start-video-localization"`
- `data-testid="video-job-id"`

## Implementation Notes

- Normalized the hero CTA accessible name to `Open video workflow`.
- Added a mobile-only toolbar shortcut with the same role/name because the hero intro is intentionally hidden on small viewports.
- Added direct `aria-label="Source video"` to the file input and `aria-label="Start Vietnamese localization"` to the submit button.
- Changed Playwright tests to use role/label locators and locator-based `setInputFiles`, matching Context7 Playwright guidance.
- Added `kind?: string` to `VideoLocalizationArtifact`.
- Changed artifact matching to include `kind` and prefer candidate order before artifact order, so `voiceover_audio` and `localized_video` win over source media.

## Context7

- Library ID: `/microsoft/playwright`
- Topic: `locators setInputFiles getByRole test id file upload actionability`
- Applied guidance: use user-facing role/label locators and locator-based `setInputFiles` for file uploads.

## Verification

Commands run from `frontend/`:

- `npm run lint` - passed.
- `npm run test` - passed, 4 tests.
- `npm run build` - passed.
- `LD_LIBRARY_PATH=/tmp/voice-ai-browser-deps/extracted/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-} npm run test:e2e` - passed, 8 tests.

Initial Playwright run without the dependency workaround failed before app execution because bundled Chromium could not load `libgbm.so.1`. The existing local workaround path was used for verification.

Public real-submit verification:

- URL: `http://103.27.237.252:4174/`
- Sample: `/tmp/voice-ai-video-speech/source-speaking.mp4`
- POST status: `200`
- Job ID: `vid_0e2dee92aeb44d3480459d8efaae432d`
- Script preview length: `122`
- Rendered artifact links:
  - Transcript: `http://103.27.237.252:8080/v1/video-localization/jobs/vid_0e2dee92aeb44d3480459d8efaae432d/artifacts/transcript.json`
  - SRT: `http://103.27.237.252:8080/v1/video-localization/jobs/vid_0e2dee92aeb44d3480459d8efaae432d/artifacts/subtitles.vi.srt`
  - VTT: `http://103.27.237.252:8080/v1/video-localization/jobs/vid_0e2dee92aeb44d3480459d8efaae432d/artifacts/subtitles.vi.vtt`
  - Vietnamese audio: `http://103.27.237.252:8080/v1/video-localization/jobs/vid_0e2dee92aeb44d3480459d8efaae432d/artifacts/voiceover.vi.wav`
  - Final MP4: `http://103.27.237.252:8080/v1/video-localization/jobs/vid_0e2dee92aeb44d3480459d8efaae432d/artifacts/localized.vi.mp4`

Screenshot:

- `docs/subagents/evidence/images/frontend-video-e2e-real-submit-fixed-20260510.png`

## Remaining Risk

- Public frontend is served by the local Vite preview process on port `4174`; it picked up the rebuilt `frontend/dist` asset hash during verification. If that process is restarted from stale files elsewhere, rerun `npm run build` first.
- Playwright in this environment still needs the temporary `LD_LIBRARY_PATH` browser dependency workaround unless the host installs the missing browser libraries properly.

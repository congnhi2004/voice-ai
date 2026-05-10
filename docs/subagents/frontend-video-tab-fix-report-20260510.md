# Frontend Video Tab Fix Report - 2026-05-10

## Root Cause

The public frontend already had a video localization form, but the workflow switch was fragile for public QA:

- The video workflow was conditionally mounted only after local state changed, so the initial DOM contained the TTS inputs and no `input[type="file"]`.
- The hero video CTA changed state and called `scrollIntoView` before re-rendering the video panel, which made click-based public checks vulnerable to seeing the old TTS panel.
- There was no focused E2E assertion for the exact blocker: clicking the `Video localization` tab must expose a file input and the video workflow controls.

## Files Changed

- `frontend/src/main.ts`
  - Added `switchWorkflow()` so all video entry points render the selected workflow first, then scroll/focus after the video panel exists.
  - Added `role="tabpanel"`/`aria-controls` wiring for the workflow panel.
  - Added `data-testid="video-file-input"` to the source video file input for stable public QA checks.
  - Kept Quick TTS as the first screen.
- `frontend/src/e2e/app.spec.ts`
  - Added `Video localization tab exposes the upload workflow`, asserting that the exact `Video localization` tab reveals:
    - `input[type="file"]`
    - source language selector
    - fixed Vietnamese target field
    - Vietnamese voice selector
    - start localization action

## API Contract Used

The frontend keeps the current multipart video localization request fields:

- `file`
- `source_language`
- `target_language` with value `vi`
- `voice_name`

## Context7

- `/vitejs/vite`, topic `vanilla TypeScript dev server build`
- `/microsoft/playwright`, topic `locators role getByTestId file input assertions screenshots`

## Verification Commands

Passed:

```bash
cd /home/jhao/code/voice-ai/frontend
npm run lint
npm run test
npm run build
```

Blocked by container runtime dependency:

```bash
cd /home/jhao/code/voice-ai/frontend
npm run test:e2e -- --project=desktop --grep "Video localization tab exposes"
```

Result: Playwright Chromium could not launch because `libgbm.so.1` is missing in the container. `sudo` is unavailable, so I could not install the system package or capture a new screenshot here.

## PM Acceptance Steps

1. Open the public frontend.
2. Confirm the first screen is still the Quick TTS workflow.
3. Click the exact `Video localization` tab in the workflow switch.
4. Confirm the DOM now contains `input[type="file"]`.
5. Confirm visible video controls:
   - source video file input
   - source language selector
   - target field showing Vietnamese script/SRT/dub/MP4
   - Vietnamese voice selector
   - `Start Vietnamese localization` action
   - output panel with progress, script/SRT previews, media previews, artifact links, and error surface
6. Upload a short English or Chinese MP4/MOV/WebM file.
7. Confirm the network request posts multipart form data to `/v1/video-localization/jobs` with `file`, `source_language`, `target_language=vi`, and `voice_name`.

# Frontend rescue redesign report - 2026-05-10

## Scope

Finished the frontend rescue pass for the Voice AI studio after live QA found desktop overlap and mobile hero clipping.

## Files changed

- `frontend/src/main.ts`
- `frontend/src/styles.css`
- `docs/subagents/evidence/images/frontend-rescue-redesign-desktop-20260510.png`
- `docs/subagents/evidence/images/frontend-rescue-redesign-mobile-20260510.png`
- `docs/subagents/frontend-rescue-redesign-20260510.md`

Existing dirty backend, docs, tests, and prior frontend contract changes were preserved.

## Decisions

- Removed the tall/dark side hero behavior from the first viewport and reduced it to a compact production masthead.
- Kept the working studio immediately below the masthead so desktop shows script input, mode tabs, Generate TTS CTA, voice/language/encoding controls, and output preview without scrolling at `1440x1000`.
- Replaced competing shared layout behavior with one final `.workspace-grid.workflow-lanes` rule: composer uses `minmax(0, 1fr)`, result uses `minmax(320px, 420px)`, then stacks at `max-width: 1100px`.
- Kept `.result-panel` static, width-auto, and inside the parent grid. Removed reliance on clipping the composer with `overflow: hidden`.
- Forced mobile `.studio-intro` to block layout with visible overflow and hidden intro status rail, fixing vertical/clipped text at `390x1000`.
- Kept diagnostics collapsed and below provider readiness/history. Account, provider readiness, history, and diagnostics are secondary details below the output panel.
- Preserved login/register/pricing/security/docs sections and existing API behavior/selectors.

## Research and docs used

- Context7 `/websites/v7_vite_dev`, topic `Vite environment variables and TypeScript build behavior`: confirmed client env behavior and standard build verification expectations.
- Current UI pattern references checked with Exa: LTX Studio TTS/dialog editor, Phrase Studio audio/video localization, and VMEG editing studio. Implementation decision: use a compact working studio with upload, script, voice, preview, progress, and artifacts instead of a marketing-heavy hero.

## Verification

- `cd frontend && taskset -c 0-3 npm run lint` - passed.
- `cd frontend && taskset -c 0-3 npm run test -- --run` - passed, 1 file / 6 tests.
- `cd frontend && taskset -c 0-3 npm run build` - passed, Vite production build completed.
- `cd frontend && LD_LIBRARY_PATH=/tmp/voice-ai-browser-deps/extracted/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH taskset -c 0-3 npm run test:e2e` - passed, 12 tests.

## Screenshots inspected

- Desktop: `docs/subagents/evidence/images/frontend-rescue-redesign-desktop-20260510.png`
- Mobile: `docs/subagents/evidence/images/frontend-rescue-redesign-mobile-20260510.png`
- E2E refreshed evidence: `docs/subagents/evidence/images/frontend-premium-tts-desktop.png`, `docs/subagents/evidence/images/frontend-premium-tts-mobile.png`, `docs/subagents/evidence/images/frontend-premium-video-desktop.png`, `docs/subagents/evidence/images/frontend-premium-video-mobile.png`

## Residual risks

- The screenshots validate the default TTS landing state and mocked e2e TTS/video states. They do not validate every real production backend payload shape.
- Several unrelated backend/docs/test files were already dirty in the workspace and were intentionally not reverted.

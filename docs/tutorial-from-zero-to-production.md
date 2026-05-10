# Tutorial: From Empty Workspace To Production Video Localization

## Audience

This tutorial is for PM, product, architecture, backend, frontend, infra, QA, security, and documentation agents working on Voice AI. It explains how to move from an empty workspace to a production-ready product that localizes Chinese or English videos into Vietnamese.

The goal is not only to build software. The goal is to build a product process where each decision, artifact, implementation slice, and release claim can be verified through durable evidence.

## 1. Starting Assumptions And Constraints

Start with these rules before any implementation:

- PM does not directly write product code or product docs. PM delegates to skilled subagents and verifies through reports, docs, UI, APIs, logs, MLflow or observability UIs, and completion audits.
- No subagent should be assigned until a clear project skill exists for that role.
- Treat each subagent like an employee: role, skill, ownership, criteria, verification, and report path must be explicit.
- Each subagent prompt must name skill(s), ownership/write scope, prohibited scope, verification method, and report path.
- All implementation, docs, UI design, deployment, and skill-writing work starts with current official/web research.
- Prefer built-in web search for research. Avoid heavy Exa usage unless the required source cannot be found through the built-in search path.
- Application source code and product documentation changes must be done by the assigned subagent, not by PM.
- Long-running or heavy repeated commands should use `taskset -c 0-3` where feasible to reduce server contention. Apply this to `pytest`, `npm run build`, `npm test`, Playwright, FFmpeg generation, and Docker build/rebuild commands unless the environment does not support CPU affinity.
- User-testing prototypes must use a real TTS provider for voice output. A local beep/tone fallback is allowed only when provider credentials are missing, and the UI/report must label it as fallback/demo audio rather than real Voice AI.
- PM must actively review while agents run by checking public URLs, scrolling desktop/mobile UI, running smoke commands, and inspecting screenshots instead of only waiting for completion reports.

The governance source of truth is `docs/pm-governance.md`.

## 2. Product Target

The production product lets a user:

1. Upload a Chinese or English source video.
2. Start a Vietnamese localization job.
3. Track job status and stage progress.
4. Download Vietnamese transcript/script.
5. Download Vietnamese SRT and VTT subtitles.
6. Download Vietnamese voice/dub audio.
7. Download a final localized MP4 with Vietnamese subtitles and Vietnamese audio.
8. Inspect operational evidence through logs, job status, artifact manifests, and MLflow/observability records.

The MVP pipeline is:

```text
Upload Chinese/English video
-> extract audio
-> Speech-to-Text transcription
-> translate transcript to Vietnamese
-> create Vietnamese script/subtitles
-> synthesize Vietnamese TTS/dub audio
-> render final MP4 with FFmpeg
-> store artifacts
-> log metrics and artifact references
-> deploy and audit release readiness
```

## 3. Research-First Workflow

Before writing implementation, docs, UI, deployment config, or skills, assign a qualified subagent to check current official/web sources.

Use two documentation channels:

- For cloud/product/platform facts, use current official web sources. This includes Google Cloud APIs, Cloud Run, MLflow deployment/operation notes, security/compliance, pricing, quotas, and provider availability.
- For implementation code that depends on library or framework behavior, use Context7 through MCP Docker before coding or surgery. The subagent must report the Context7 library IDs and topics used.

Minimum sources to check:

- Google Speech-to-Text asynchronous recognition: https://cloud.google.com/speech-to-text/docs/async-recognize
- Google Speech-to-Text supported languages: https://cloud.google.com/speech-to-text/docs/speech-to-text-supported-languages
- Google Cloud Translation language support: https://cloud.google.com/translate/docs/languages
- Google Text-to-Speech synthesize endpoint: https://docs.cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize
- Google Cloud Run FastAPI quickstart: https://docs.cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-fastapi-service
- Google Cloud Run overview: https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run
- MLflow Tracking: https://mlflow.org/docs/latest/ml/tracking
- FFmpeg documentation: https://ffmpeg.org/documentation.html
- FFmpeg filters documentation: https://ffmpeg.org/ffmpeg-filters.html
- Google Video Intelligence speech transcription: https://cloud.google.com/video-intelligence/docs/speech-transcription

Current source notes to preserve:

- Google Speech-to-Text asynchronous recognition is the right fit for longer audio/video transcription workflows.
- Google Speech-to-Text has language support covering English and Chinese variants.
- Google Cloud Translation supports Vietnamese as a target language.
- Google Text-to-Speech `text:synthesize` returns audio content for Vietnamese voice generation.
- FFmpeg is the media processing boundary for audio extraction, subtitle handling, muxing, and final rendering.
- Video Intelligence speech transcription is English-only for that feature, so it should not be the primary transcription service for Chinese/English coverage.

Research output should be a short report with:

- Sources checked.
- Context7 library IDs and topics used for any code work.
- Facts confirmed.
- Facts that changed or remain uncertain.
- Product/API/deployment implications.
- Recommended updates to docs or implementation.

Context7 workflow for code subagents:

1. Identify the libraries/frameworks affected by the task.
2. Use Context7 via MCP Docker to resolve the library ID.
3. Fetch focused docs for the relevant topic.
4. Implement only after reading the focused docs.
5. Record the library ID, topic, and implementation implication in the subagent report.

Examples:

- Backend/FastAPI upload work: report the FastAPI Context7 library ID and topic such as file uploads, CORS, testing, or security.
- Frontend/Vite or Playwright work: report the Vite, TypeScript, or Playwright Context7 library ID and topic used.
- MLflow code integration: report the MLflow Context7 library ID and tracking topic used.
- If Context7 is unavailable, record the exact blocker and fallback official docs before coding.

## 4. Skill Creation And Validation

Do not assign a backend, frontend, infra, QA, docs, security, or reviewer subagent until a project skill exists for that role.

For each skill:

1. Define the role and responsibilities.
2. Define the expected inputs.
3. Define allowed write scope and prohibited scope.
4. Define required official/web research.
5. Define required verification.
6. Define report path under `docs/subagents/`.
7. Validate the skill with a small dry-run task before using it for production work.

Example skill validation checklist:

| Check | Evidence |
| --- | --- |
| Skill names role and artifact type | |
| Skill requires source research | |
| Skill defines ownership/write scope | |
| Skill defines verification | |
| Skill requires durable report | |
| Dry-run completed without scope violations | |

## 5. PM Documentation Creation

Assign a product/documentation subagent using `voice-ai-product-docs`.

The subagent should create or update:

- `docs/project-brief.md`
- `docs/prd.md`
- `docs/ai-system-design.md`
- `docs/security-privacy.md`
- `docs/observability-mlflow.md`
- `docs/deployment-runbook.md`
- `docs/sprint-plan.md`
- `docs/acceptance-checklist.md`
- `docs/api-contract.md`
- `docs/pm-governance.md`
- `docs/subagents/product-architecture-report.md`

PM should verify the documentation package through:

- The subagent report.
- Cross-references between brief, PRD, API contract, sprint plan, governance, and acceptance checklist.
- Explicit source notes for cloud, MLflow, FFmpeg, and deployment facts.
- Acceptance criteria that QA can fill with evidence.

## 6. Backend Workstream

The backend subagent owns the FastAPI service, job orchestration boundary, provider interfaces, storage integration, and contract tests.

Expected outputs:

- Health and readiness endpoints.
- API key authentication.
- CORS allowlist.
- Video upload endpoint.
- Localization job creation endpoint.
- Job status endpoint.
- Artifact listing and download endpoints.
- Direct TTS endpoint.
- Provider interfaces for STT, translation, TTS, media processing, and storage.
- Local/demo mode that works without cloud credentials.
- Structured errors that match `docs/api-contract.md`.
- Tests for local/demo mode and API contracts.
- Context7 evidence for implementation libraries/frameworks, including library IDs and topics used.
- Backend report under `docs/subagents/`.

Heavy backend verification should be CPU-limited where feasible:

```bash
taskset -c 0-3 pytest
taskset -c 0-3 ffmpeg ...
taskset -c 0-3 docker build ...
```

Backend should implement the product flow in stages:

1. Accept and validate uploaded videos.
2. Store source video locally for development or in durable object storage for production.
3. Extract audio with FFmpeg.
4. Submit audio to Speech-to-Text for async transcription in cloud mode.
5. Translate timestamped transcript segments to Vietnamese.
6. Generate Vietnamese script, SRT, and VTT.
7. Synthesize Vietnamese voice audio with Text-to-Speech.
8. Render final MP4 with FFmpeg.
9. Store artifact manifest with checksums, sizes, durations, and URLs.
10. Record stage telemetry and artifact references in MLflow.

Product workflow commands may include:

```bash
curl http://localhost:8080/healthz
curl -H "Authorization: Bearer dev-key" http://localhost:8080/readyz
curl -H "Authorization: Bearer dev-key" http://localhost:8080/v1/voices
```

For upload and localization testing, use documented API examples from `docs/api-contract.md`. Do not claim command success until the command has been run in the target environment.

## 7. Frontend Workstream

The frontend subagent owns the user-facing web experience.

Expected outputs:

- Upload screen for Chinese/English video.
- Source language selector or auto-detect option.
- Vietnamese voice selector.
- Subtitle mode selector: sidecar, burn-in, or both.
- Job creation flow.
- Progress/status display.
- Artifact list with downloads.
- Audio preview.
- Final video preview/download.
- Error states for auth, upload limits, provider failures, failed jobs, and expired downloads.
- Frontend report under `docs/subagents/`.

The UI must not expose Google credentials or internal provider secrets. It should call the backend only through documented API contracts.

Heavy frontend verification should be CPU-limited where feasible:

```bash
taskset -c 0-3 npm run build
taskset -c 0-3 npm test
taskset -c 0-3 npx playwright test
```

## 8. Infra And Observability Workstream

The infra/observability subagent owns deployment, cloud services, logs, metrics, MLflow connectivity, artifact storage, and release operations.

Expected outputs:

- Local environment setup instructions.
- CI pipeline for lint/test/build.
- Cloud Run deployment path.
- Secret management strategy.
- Google Cloud Storage bucket plan for source videos and artifacts.
- MLflow tracking backend plan.
- Log fields and dashboard requirements.
- Alert policies.
- Rollback procedure.
- Infra report under `docs/subagents/`.

Heavy infra verification should be CPU-limited where feasible, especially Docker build/rebuild and FFmpeg generation. Use `taskset -c 0-3` when the host supports it, and record any exception in the infra report.

Recommended environment variables:

- `ENVIRONMENT`
- `PORT`
- `API_KEYS`
- `CORS_ALLOW_ORIGINS`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `GCP_PROJECT_ID`
- `TRANSCRIPTION_PROVIDER`
- `TRANSLATION_PROVIDER`
- `TTS_PROVIDER`
- `MLFLOW_TRACKING_URI`
- `UPLOAD_STORAGE_DIR`
- `AUDIO_STORAGE_DIR`
- `ARTIFACT_STORAGE_DIR`
- `AUDIO_BASE_URL`
- `ARTIFACT_BASE_URL`
- `MAX_INPUT_CHARS`
- `MAX_VIDEO_UPLOAD_MB`
- `MAX_VIDEO_DURATION_SECONDS`
- `LOG_LEVEL`

Local development can use local filesystem paths. Production must not treat Cloud Run's local filesystem as durable storage.

## 9. QA And Reviewer Workstream

The QA/reviewer subagent owns evidence collection and release readiness verification.

Expected outputs:

- API contract tests.
- Local/demo mode verification.
- Upload/job/artifact happy-path verification.
- Failure tests for unsupported language, oversized file, auth failure, provider unavailable, and render failure.
- Privacy log review.
- MLflow run evidence.
- Context7 evidence for any test automation library/framework work, including library IDs and topics used.
- Cloud Run staging smoke evidence.
- Acceptance checklist updates.
- QA report under `docs/subagents/`.

QA should fill the living evidence checklist at the end of this tutorial and `docs/acceptance-checklist.md`.

## 10. Local Development Path

Local development should prove the product shape without cloud credentials.

Minimum local/demo mode behavior:

- Accept a small fixture video.
- Return `video_id`.
- Create a localization job.
- Progress through deterministic stages.
- Generate placeholder Vietnamese transcript/script.
- Generate valid SRT and VTT files.
- Generate real provider TTS audio for any user-testing prototype.
- Generate local beep/tone fallback audio only when provider credentials are missing, and label it clearly as fallback/demo audio in UI, docs, and reports.
- Produce a valid MP4 artifact or documented placeholder video artifact.
- Create logs and MLflow/local tracking evidence.

Local workflow commands should be documented after implementation. Typical workflow shape:

```bash
export ENVIRONMENT=local
export TTS_PROVIDER=google
export TRANSCRIPTION_PROVIDER=local
export TRANSLATION_PROVIDER=local
export MLFLOW_TRACKING_URI=./mlruns
export API_KEYS=dev-key
```

If no provider credentials exist, set `TTS_PROVIDER=local` only for a clearly labeled fallback/demo run. Do not use local beep/tone output as evidence of real Voice AI quality.

Do not invent successful outputs. Each reported output must come from an actual run.

## 11. CI/CD Path

CI should run without live Google credentials.

Minimum CI gates:

- Formatting/lint.
- Unit tests.
- API contract tests.
- Local/demo pipeline test.
- Security checks for committed secrets.
- Container build.
- Documentation consistency check if available.

CD should deploy only after CI passes and should promote the same image digest from staging to production.

Where feasible, run repeated heavy CI-like commands on shared servers with CPU affinity, for example `taskset -c 0-3 pytest`, `taskset -c 0-3 npm run build`, and `taskset -c 0-3 docker build ...`. This reduces server contention and keeps parallel agent work usable.

## 12. Cloud Run And GCP Production Path

Production should use Cloud Run for the API and job execution boundary, with GCP services for managed storage and provider APIs.

Production requirements:

- Cloud Run service identity or Secret Manager for credentials.
- Cloud Storage for uploaded videos and generated artifacts.
- Speech-to-Text API enabled.
- Cloud Translation API enabled.
- Text-to-Speech API enabled.
- MLflow tracking endpoint configured.
- Logs, metrics, dashboards, and alerts configured.
- Cloud Run revisions used for rollback.

The deployment runbook is `docs/deployment-runbook.md`.

## 13. MLflow And Observability

Create one MLflow run per localization job and one run per direct TTS request.

Localization run tags:

- `job_id`
- `video_id`
- `request_id`
- `source_language`
- `target_language`
- `environment`
- `service_version`
- `fallback`

Localization metrics:

- upload bytes.
- source duration.
- stage latency for extraction, transcription, translation, TTS, rendering, and storage.
- transcript segment count.
- translated character count.
- output audio duration.
- output video duration.
- artifact bytes.
- success/failure.

Artifacts or artifact references:

- Source video reference.
- Vietnamese transcript/script reference.
- SRT/VTT references.
- Vietnamese audio reference.
- Final MP4 reference.
- Error report if failed.

Logs must include request id, video id, job id, stage, provider, status, latency, and error code. Logs must not include raw source transcript or Vietnamese script by default.

## 14. Acceptance Audit

Before release, PM should verify only through allowed evidence:

- Subagent reports.
- Product docs.
- Local or hosted UI.
- API responses.
- Logs.
- MLflow/observability UI.
- Acceptance checklist.
- Completion audit report.

PM should not inspect source code as the primary verification path.

PM should perform active review during execution, not only at the end:

- Test public URLs as soon as they are available.
- Scroll desktop and mobile UI and inspect screenshots for layout, runtime, and artifact-link failures.
- Run smoke commands for health, readiness, voices, synthesize, and artifact downloads when credentials are not required or are supplied through redacted environment variables.
- Feed failures back to the responsible subagent before final reports are written.

Release readiness requires:

- A successful local/demo job without cloud credentials.
- A successful staging job using Google providers.
- A user-testing prototype voice generated by a real TTS provider, not an unlabeled beep/tone fallback.
- A downloadable Vietnamese transcript/script.
- Downloadable SRT and VTT.
- Downloadable Vietnamese TTS audio.
- Downloadable final MP4.
- MLflow run evidence for the localization job.
- Logs without raw transcript/script content by default.
- Rollback procedure tested or explicitly blocked with a release decision.

## 15. Lifecycle Management

After launch, manage the product through explicit lifecycle tasks:

- Monitor provider costs and quotas.
- Review failed localization jobs weekly.
- Track subtitle timing quality.
- Track translation quality feedback.
- Track Vietnamese TTS quality feedback.
- Review retention and deletion policy.
- Rotate API keys and secrets.
- Refresh official-source assumptions when Google, FFmpeg, MLflow, or Cloud Run docs change.
- Keep `docs/api-contract.md` versioned when endpoints or schemas change.
- Keep `docs/acceptance-checklist.md` current with release evidence.

## 16. Lessons Learned / Avoid These Mistakes

Use this section as a release-readiness guardrail. These checks come from mistakes found during the first prototype and public-deploy pass.

Limit long-running repeated commands to CPU cores 0-3 where feasible. Use `taskset -c 0-3` for `pytest`, `npm run build`, `npm test`, Playwright, FFmpeg generation, and Docker build/rebuild commands. This reduces server contention while multiple agents and services run on the same host. If CPU affinity is unavailable, record the exception and keep the verification run narrow.

Do not treat local beep/tone audio as real Voice AI. User testing needs a real TTS provider so users can judge voice quality, pacing, and product value. A local beep/tone fallback is acceptable only when provider credentials do not exist, and every UI label, report, and demo note must say it is fallback/demo audio.

PM should actively review while agents run. Open public URLs, scroll desktop and mobile UI, run available smoke commands, inspect screenshots, and report failures early. Waiting silently for agent completion misses cheap feedback loops.

Do not call a web deploy ready after only `npm run build`, container startup, or HTTP 200. A public frontend can serve HTML and still be unusable. Always open the actual public URL and capture desktop and mobile screenshots from that URL. Link the screenshots from QA and report docs, for example under `docs/subagents/`.

If Playwright cannot launch because browser system libraries are missing and the environment has no `sudo`, use the temporary dependency workaround only to unblock visual QA:

```bash
mkdir -p /tmp/pw-debs /tmp/pw-libs
cd /tmp/pw-debs
apt-get download libgbm1 libasound2 libwayland-server0
for deb in ./*.deb; do dpkg-deb -x "$deb" /tmp/pw-libs; done
export LD_LIBRARY_PATH="/tmp/pw-libs/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
npx playwright test
```

This is a local workaround, not the preferred final state. In real CI or a maintained server, install the required browser dependencies through the proper system package path or a Playwright-ready image.

Fix ambiguous E2E selectors before trusting test results. If two controls share the same accessible name, tests may click the wrong element or fail for the wrong reason. Use unique accessible names, `exact: true`, or stable `data-testid` attributes for controls that have repeated labels.

The public frontend must not default API calls to `localhost` for external users. A browser on another machine resolves `localhost` to that user's machine, not the deployed backend. Derive the API base from explicit config or from `window.location.hostname` when the frontend and backend share a host, and record the chosen behavior in the frontend report.

Runtime compatibility errors must be fixed before deployment, even if they only appear in the public browser. A failure such as `crypto.randomUUID is not a function` needs a durable fallback or polyfill before release.

Backend smoke tests must hit the deployed or public service over real HTTP, not only FastAPI `TestClient` or unit tests. Verify:

- `GET /healthz` and authenticated readiness endpoints return expected status.
- Direct TTS or audio artifact downloads begin with `RIFF` when WAV is expected.
- Video localization jobs produce downloadable transcript, subtitle, audio, and video artifacts.
- Artifact URLs work from outside the container and are linked in QA evidence.

Do not hot-patch a running container as the final release state. Hot patches are acceptable only as temporary diagnosis or emergency mitigation. Before release, rebuild the Docker image durably, restart from that image, and rerun public HTTP smoke plus desktop/mobile visual QA.

Capture evidence files while the system is working. At minimum, QA/report docs should link:

- Desktop screenshot from the actual public frontend URL.
- Mobile screenshot from the actual public frontend URL.
- Public API smoke output or summarized command evidence.
- Audio artifact evidence showing WAV downloads start with `RIFF`.
- Video job artifact evidence showing final artifact downloads.
- Any logs, MLflow run ids, or observability screenshots used for the release decision.

PM should stop adding features until the prototype-first core flow is visibly usable. The core flow is: open public frontend, upload or synthesize, create a job, see progress, download audio/subtitles/video artifacts, and confirm evidence through public URLs. New features before that point hide release risk.

## Living Evidence Checklist

QA and reviewers can fill this table during delivery and release audits.

| Area | Evidence Needed | Status | Evidence Link Or Notes |
| --- | --- | --- | --- |
| Governance | Subagent prompts include skill, scope, verification, and report path. | Not started | |
| Research | Official/web sources checked before implementation/docs/UI/deployment. | Not started | |
| Skills | Required project skills created and dry-run validated. | Not started | |
| PM docs | Brief, PRD, system design, API contract, runbook, sprint plan, and checklist align. | Not started | |
| Local upload | Local/demo mode accepts a fixture Chinese or English video. | Not started | |
| Local job | Local/demo mode creates and completes a localization job. | Not started | |
| STT | Staging job transcribes English or Chinese source speech with timestamps. | Not started | |
| Translation | Staging job produces Vietnamese transcript/script. | Not started | |
| Subtitles | Staging job produces valid SRT and VTT. | Not started | |
| TTS | User-testing or staging job produces Vietnamese voice/dub audio from a real TTS provider; any local beep/tone fallback is clearly labeled. | Not started | |
| Render | Staging job produces downloadable localized MP4. | Not started | |
| API | Upload, job status, artifacts, downloads, voices, and synthesize contracts pass. | Not started | |
| Public visual QA | Desktop and mobile screenshots from the actual public frontend URL are linked. | Not started | |
| UI | Hosted or local UI can run the full product flow with non-ambiguous E2E selectors. | Not started | |
| Public API base | Frontend API base is public-safe and does not default external users to `localhost`. | Not started | |
| Runtime compatibility | Public browser runtime has no blocking errors such as missing `crypto.randomUUID`. | Not started | |
| Public HTTP smoke | Deployed backend smoke ran over real HTTP, including WAV `RIFF` and video artifact downloads. | Not started | |
| Heavy task CPU limit | Repeated heavy commands used `taskset -c 0-3` where feasible, or exceptions were recorded. | Not started | |
| PM active review | PM tested public URLs, scrolled desktop/mobile UI, ran smoke commands, and inspected screenshots while agents were running. | Not started | |
| Logs | Logs include ids/stage/status and omit raw transcript/script by default. | Not started | |
| MLflow | Localization job and TTS request create MLflow evidence. | Not started | |
| Security | Auth, CORS, storage access, retention, and secret handling verified. | Not started | |
| CI | CI passes without cloud credentials. | Not started | |
| Durable image | Any container hot patch was replaced by a rebuilt image and restart. | Not started | |
| Cloud Run | Staging deployment completes and smoke tests pass. | Not started | |
| Rollback | Rollback procedure tested or release exception documented. | Not started | |
| Release | PM completion audit references only allowed verification surfaces. | Not started | |

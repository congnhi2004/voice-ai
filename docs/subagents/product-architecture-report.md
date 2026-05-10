# Product Architecture Report

## Summary

Created a complete PM/product documentation package for a production Voice AI text-to-speech product. No application source code was created or modified.

## Files Created

- `docs/project-brief.md`
- `docs/prd.md`
- `docs/ai-system-design.md`
- `docs/security-privacy.md`
- `docs/observability-mlflow.md`
- `docs/deployment-runbook.md`
- `docs/sprint-plan.md`
- `docs/acceptance-checklist.md`
- `docs/api-contract.md`
- `docs/subagents/product-architecture-report.md`

## Key Product And Architecture Decisions

- FastAPI is the API boundary.
- Google Cloud Text-to-Speech is the production TTS provider.
- A deterministic local provider is required for local development and CI when Google credentials are missing.
- `POST /v1/synthesize` returns JSON, not raw audio, so clients receive job metadata, audio location, latency, provider metadata, and observability ids.
- Local generated audio can be served from `/audio/{filename}`.
- Production audio must use durable object storage because Cloud Run instances have disposable filesystems.
- MLflow Tracking records one run per synthesis request with params, metrics, tags, and audio artifact references.
- API keys are the MVP auth mechanism, with a path to tenant-scoped keys or stronger identity later.

## Official Source Links Used

- Google Cloud Text-to-Speech `text:synthesize`: https://docs.cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize
- Google create audio guide: https://cloud.google.com/text-to-speech/docs/create-audio
- Cloud Run FastAPI quickstart: https://docs.cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-fastapi-service
- Cloud Run overview: https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run
- MLflow Tracking docs: https://mlflow.org/docs/latest/ml/tracking

## Important Reference Notes

- Google `text:synthesize` is synchronous and returns base64 audio content.
- Google requests require synthesis input, desired voice, and audio config.
- Google create-audio guidance describes decoding base64 audio into playable files such as MP3.
- Cloud Run can deploy Python FastAPI services from source and runs services as HTTPS endpoints.
- Cloud Run local container filesystem is disposable and not durable.
- MLflow Tracking supports logging/querying params, metrics, runs, and artifacts.

## Handoff Instructions

Backend agents should implement `docs/api-contract.md` first, using `docs/ai-system-design.md` for provider/storage boundaries. Infrastructure agents should use `docs/deployment-runbook.md` and should not treat local audio storage as production durable storage. QA should use `docs/acceptance-checklist.md` as the release evidence ledger and fill evidence fields as implementation lands.

The highest implementation risks are Google credential handling, production audio persistence, privacy-safe logging, and making CI pass without live Google access.

## Addendum: PM Governance Update

Updated the docs package with PM governance rules requested by the user.

Files changed in this addendum:

- `docs/pm-governance.md`
- `docs/sprint-plan.md`
- `docs/subagents/product-architecture-report.md`

Governance decisions captured:

- PM cannot directly write product code or product docs; PM delegates to skilled subagents and reads their reports/docs.
- New subagents require a clear project skill for the role before assignment.
- Subagent prompts must name skill(s), ownership/write scope, verification, and report path.
- Agents must search current web/official docs before implementation, docs, UI design, deployment, or writing skills, preferring built-in web search and avoiding heavy Exa usage unless needed.
- PM verification is limited to docs/reports, local or hosted web UI, APIs, logs, MLflow/observability UIs, and completion audits.

Sources and assumptions:

- Source: user-provided governance rules in the PM update request.
- Source: `voice-ai-product-docs` skill instructions at `/home/jhao/.codex/skills/voice-ai-product-docs/SKILL.md`.
- Source: existing docs package, especially `docs/sprint-plan.md` and this report.
- Assumption: no external platform fact changed for this governance update; the durable rule itself requires future agents to check current web/official docs before implementation, docs, UI design, deployment, or skill writing.

Recommended next action:

- Define and approve project skills for backend, frontend, infra, QA, docs, security, and PM governance before assigning new subagents in those roles.

## Addendum: Tutorial From Zero To Production

Added a complete learning/tutorial document for taking Voice AI from an empty workspace to a production-ready Chinese/English-to-Vietnamese video localization product.

Files changed in this addendum:

- `docs/tutorial-from-zero-to-production.md`
- `docs/project-brief.md`
- `docs/sprint-plan.md`
- `docs/subagents/product-architecture-report.md`

Tutorial scope:

- Starting assumptions and PM governance constraints.
- Research-first workflow using current official/web sources.
- Skill creation and validation steps before subagent assignment.
- PM documentation creation flow.
- Backend, frontend, infra/observability, and QA/reviewer workstreams.
- Full video localization pipeline from upload through final MP4 rendering.
- Local development, CI/CD, Cloud Run/GCP deployment, MLflow, acceptance audit, release readiness, and lifecycle management.
- Living evidence checklist for QA and release reviewers.

Sources checked for this tutorial update:

- Google Speech-to-Text asynchronous recognition: https://cloud.google.com/speech-to-text/docs/async-recognize
- Google Cloud Translation language support: https://cloud.google.com/translate/docs/languages
- Google Text-to-Speech synthesize endpoint: https://docs.cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize
- FFmpeg documentation and filters documentation: https://ffmpeg.org/documentation.html and https://ffmpeg.org/ffmpeg-filters.html

Assumptions:

- This was a docs-only tutorial update; no application source code was modified.
- Tutorial commands describe expected product workflows and do not claim successful command output without a real run.

## Addendum: User-Provided Secret Handling

Updated governance and security documentation with explicit handling rules for user-provided API keys and cloud/API credentials.

Files changed in this addendum:

- `docs/pm-governance.md`
- `docs/security-privacy.md`
- `docs/subagents/product-architecture-report.md`

Rules captured:

- Treat user-provided `OPENAI_API_KEY` values and all cloud/API keys as secrets.
- Never commit, echo, log, paste into reports, or place secret values in `.env.example`.
- Pass secrets only through environment variables for narrow, explicit test commands when no safer path is available.
- Redact secret-like values as `[redacted]` in docs, logs, reports, screenshots, and evidence.
- Recommend rotating any key that appeared in chat or another non-secret surface after test use.

Sources checked:

- OpenAI Help Center guidance on API key security and environment variables: https://help.openai.com/en/articles/8304786-how-can-i-keep-my-openai-accounts-secure
- Google Secret Manager best practices: https://docs.cloud.google.com/secret-manager/docs/best-practices

Assumption:

- This was a docs-only security/process update. No secret value was included or repeated in the documentation.

## Addendum: Root User Quickstart

Created a short Vietnamese root-level guide so the user can understand and manually test the current product without reading the full documentation set.

Files changed in this addendum:

- `shine_read.md`
- `docs/subagents/product-architecture-report.md`

Guide content:

- Current product scope: Chinese/English video to Vietnamese script, subtitles, voice/dub, and final localized video, plus direct TTS base.
- Short architecture summary: frontend, FastAPI backend, local fallback/demo, Google Cloud target, MLflow/logging, and FFmpeg/video processing.
- Test link table with current known frontend preview and placeholders for backend docs, MLflow UI, and public URL where infra/PM must fill values.
- Manual test flow in seven steps.
- Known limitations from backend/frontend/QA reports, including local demo mode, missing production Google STT/Translation/TTS video path, FFmpeg availability, and blocked browser E2E screenshots.
- Pointers to deeper docs.

Sources checked:

- `docs/subagents/frontend-report.md`
- `docs/subagents/backend-report.md`
- `docs/subagents/qa-report.md`
- Existing product docs under `docs/`

Assumption:

- This was a docs-only user guide update. No application source code or secret values were modified or included.

## Addendum: Subagent Role Map

Updated PM governance with a short role map for subagents used in this run.

Files changed in this addendum:

- `docs/pm-governance.md`
- `docs/subagents/product-architecture-report.md`

Governance decision captured:

- Future PM updates should refer to stable human-readable roles instead of random generated nicknames or opaque agent IDs.
- Generated IDs/nicknames were not available in the durable reports for most roles, so the role map marks them as not recorded rather than inventing values.

Roles mapped:

- Product Docs Agent
- Skill Author Agent A
- Skill Author Agent B
- Backend Builder Agent
- Frontend Builder Agent
- Infra/Observability Agent
- QA Acceptance Agent

Sources checked:

- `docs/pm-governance.md`
- `docs/subagents/product-architecture-report.md`
- `docs/subagents/skill-author-a-report.md`
- `docs/subagents/skill-author-b-report.md`
- `docs/subagents/backend-report.md`
- `docs/subagents/frontend-report.md`
- `docs/subagents/qa-report.md`

Assumption:

- This was a docs-only governance update. No external platform fact was needed, and no application source code was modified.

## Addendum: Vietnamese Diacritics Cleanup

Fixed missing Vietnamese diacritics in user-facing Markdown prose while preserving technical identifiers, file paths, commands, endpoint paths, environment variables, links, and product names.

Files changed in this addendum:

- `shine_read.md`
- `docs/subagents/product-architecture-report.md`

Review performed:

- Reviewed the target files named by the user: `shine_read.md`, `docs/tutorial-from-zero-to-production.md`, and `docs/pm-governance.md`.
- Ran a grep-style scan for common unaccented Vietnamese phrases across Markdown files.
- Confirmed the accent-loss issue was concentrated in the root user guide. The tutorial and governance docs are English prose with technical language names, so no Vietnamese prose rewrite was needed there.

Assumption:

- This was a docs-only language cleanup. No application source code was modified.

## Addendum: Primary Frontend Test Link

Updated the Vietnamese root quickstart so the primary user test/progress link is the frontend URL.

Files changed in this addendum:

- `shine_read.md`
- `docs/subagents/product-architecture-report.md`

Change summary:

- Made `http://103.27.237.252:4174/` the main frontend link users should open.
- Moved backend API docs, local frontend fallback, MLflow UI, and other public URL placeholders into a smaller technical link section.
- Clarified that users usually only need the frontend link.
- Preserved Vietnamese diacritics and did not include any secret values.

Assumption:

- This was a docs-only link update. No application source code was modified.

## Addendum: Context7 Requirement For Code Subagents

Updated governance and tutorial documentation with the new engineering rule that code-writing subagents must use Context7 through MCP Docker before implementation or surgery.

Files changed in this addendum:

- `docs/pm-governance.md`
- `docs/tutorial-from-zero-to-production.md`
- `docs/subagents/product-architecture-report.md`

Rule captured:

- Any subagent doing code must use Context7 via MCP Docker for library/framework docs before implementation or surgery.
- Code-writing subagents must report Context7 library IDs and topics used.
- If Context7 is unavailable, the subagent must report the failure mode, fallback source, and residual risk before coding.
- Web search remains preferred for current cloud/product/platform facts such as Google Cloud APIs, deployment behavior, pricing, quotas, security, and other fast-changing provider facts.

Sources and local assumptions:

- Source: user-provided engineering governance rule in this update request.
- Source: prior local MCP Docker/Context7 memory that the reliable checks were `docker mcp tools ls`, `resolve-library-id`, and `get-library-docs`.
- Assumption: this was a docs-only governance/tutorial update. No application source code was modified.

## Addendum: Lessons Learned And Release Mistakes

Added practical release-readiness lessons so the next PM, QA, frontend, backend, or infra agent does not repeat mistakes found during the prototype/public deploy pass.

Files changed in this addendum:

- `docs/tutorial-from-zero-to-production.md`
- `docs/pm-governance.md`
- `docs/subagents/product-architecture-report.md`

Lessons captured:

- Build success and HTTP 200 are insufficient for web deploy readiness; public desktop and mobile visual QA screenshots are required.
- Playwright no-`sudo` browser-library workaround: `apt-get download` missing Ubuntu `.deb` packages, extract with `dpkg-deb -x` into `/tmp`, and run with `LD_LIBRARY_PATH`; prefer proper system install or browser-ready images in real CI/server environments.
- Ambiguous E2E selectors must be fixed before trusting tests; use unique accessible names, exact labels, or stable test ids.
- Public frontend API base must not default external users to `localhost`; use explicit config or host-derived behavior.
- Public runtime errors such as `crypto.randomUUID is not a function` need durable fallback fixes before release.
- Backend smoke must use real HTTP against the deployed/public service, including WAV `RIFF` checks and video artifact download checks.
- Running-container hot patches are temporary only; release requires rebuilt Docker image, restart, and rerun smoke/visual QA.
- QA/report docs should link screenshots, public API smoke evidence, artifact checks, logs, MLflow run ids, and release evidence.
- PM should pause feature additions until the prototype-first core flow is visibly usable through the public UI and downloadable artifacts.

Sources checked:

- User-provided lessons in this update request.
- Existing tutorial and governance documents.
- Existing evidence/report paths under `docs/subagents/`, including public frontend screenshot filenames already present in the repo.

Assumption:

- This was a docs-only lessons update. No application source code, secrets, or runtime configuration were modified.

## Addendum: CPU Limits, Real TTS Prototype, And Active PM Review

Updated product/process docs with new operating rules requested by the user.

Files changed in this addendum:

- `docs/tutorial-from-zero-to-production.md`
- `docs/pm-governance.md`
- `shine_read.md`
- `docs/subagents/product-architecture-report.md`

Rules captured:

- Long-running or heavy repeated tasks should use `taskset -c 0-3` where feasible, including `pytest`, `npm run build`, `npm test`, Playwright, FFmpeg generation, and Docker build/rebuild. This reduces server contention while multiple agents and services run.
- Prototype voice for user testing must use a real TTS provider. Local beep/tone audio is acceptable only as a clearly labeled fallback when provider credentials do not exist, and must never be presented as real Voice AI.
- PM must actively review while agents run by testing public URLs, scrolling desktop/mobile UI, running smoke commands, and inspecting screenshots instead of only waiting for subagent completion.

Sources checked:

- User-provided rules in this update request.
- Existing `docs/pm-governance.md`, `docs/tutorial-from-zero-to-production.md`, and `shine_read.md`.

Assumption:

- This was a docs-only governance/tutorial update. No application source code, secret values, or runtime configuration were modified.

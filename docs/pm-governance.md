# PM Governance

## Purpose

This document defines how PM work is governed for the Voice AI project. It is durable process guidance for PM, product, architecture, engineering, QA, infra, security, design, and documentation subagents.

## Scope

These rules apply to project planning, implementation delegation, documentation, UI design, deployment, skill creation, verification, and completion audits.

## Governance Rules

1. PM cannot directly write product code or product docs; PM delegates to skilled subagents and reads their reports/docs.
2. No new subagent should be spawned or assigned until a clear project skill exists for that role. Treat each subagent like an employee with a defined skill and criteria.
3. Every subagent prompt should name the skill(s), ownership/write scope, verification, and report path.
4. Search current web/official docs before implementation, docs, UI design, deployment, or writing skills. Prefer built-in web search; avoid heavy Exa usage unless needed.
5. PM verifies only through docs/reports, local or hosted web UI, APIs, logs, MLflow/observability UIs, and completion audits.
6. Any subagent doing code must use Context7 via MCP Docker for library/framework documentation before implementation or surgery, and must report the Context7 library IDs and topics used.
7. Long-running or heavy repeated tasks should be limited to CPU cores 0-3 with `taskset -c 0-3` where feasible. This includes `pytest`, `npm run build`, `npm test`, Playwright, FFmpeg generation, and Docker build/rebuild commands. The goal is to reduce server contention while agents are working.
8. Prototype voice used for user testing must come from a real TTS provider. A local beep/tone fallback is acceptable only when provider credentials do not exist, and it must be clearly labeled as fallback/demo audio. Never present beep audio as real Voice AI output.
9. PM must actively review while agents run. PM should test public URLs, scroll desktop and mobile UI, run smoke commands, inspect screenshots, and update evidence instead of only waiting for subagent completion.

## Operating Model

- PM owns product intent, acceptance standards, delegation quality, and final completion audits.
- Subagents own the work products assigned to their skill and write scope.
- Subagents must produce durable reports that summarize files changed, sources checked, decisions made, gaps, verification performed, and recommended next actions.
- PM should not inspect application source code to verify delivery. PM should rely on explicit evidence from allowed verification surfaces.

## Subagent Assignment Criteria

Before assigning a subagent, PM must confirm:

- The role has a named project skill.
- The skill defines the artifact or work type clearly enough for execution.
- The prompt names ownership and write boundaries.
- The prompt defines verification evidence.
- The prompt names the expected report path under `docs/subagents/` or another approved docs location.

## Subagent Role Map

Future PM updates should refer to stable human-readable roles, not random generated nicknames or opaque agent IDs. If a platform-generated agent ID or nickname is useful, record it in the assigned subagent's report, but do not make it the primary role name.

| Human-readable role | Generated ID/nickname recorded in durable docs | Skill or assignment | Primary report/evidence |
| --- | --- | --- | --- |
| Product Docs Agent | Not recorded | `voice-ai-product-docs` | `docs/subagents/product-architecture-report.md` |
| Skill Author Agent A | Not recorded | Skill creation for PM/product/reviewer skills | `docs/subagents/skill-author-a-report.md` |
| Skill Author Agent B | Not recorded | Skill creation for backend/frontend/infra/QA skills | `docs/subagents/skill-author-b-report.md` |
| Backend Builder Agent | Not recorded | `voice-ai-backend-builder` | `docs/subagents/backend-report.md` |
| Frontend Builder Agent | `Frontend Builder Agent` title recorded | `voice-ai-frontend-builder` | `docs/subagents/frontend-report.md` |
| Infra/Observability Agent | Not recorded | `voice-ai-infra-observability` | `docs/subagents/infra-report.md`; follow-up reports include `infra-production-completion-audit-20260510.md`, `infra-local-speech-runtime-report-20260510.md`, `infra-production-secret-guard-report-20260510.md`, `infra-video-env-runtime-report-20260510.md`, and `cloud-production-lifecycle-report-20260510.md` |
| QA Acceptance Agent | Not recorded | `voice-ai-qa-acceptance` | `docs/subagents/qa-report.md` |
| Tech Lead Reviewer | Not recorded | `voice-ai-techlead-reviewer` | `docs/subagents/techlead-release-review-20260510.md` and `docs/subagents/techlead-runtime-review-20260510.md` |

## Required Prompt Fields

Every subagent prompt should include:

- Skill(s): the project skill or skills the subagent must use.
- Role: the subagent's responsibility for the assignment.
- Ownership/write scope: files, directories, or surfaces the subagent may change.
- Prohibited scope: files or surfaces the subagent must not change.
- Verification: commands, UI checks, API checks, logs, MLflow evidence, reports, or audits required.
- Documentation sources: for code work, require Context7 via MCP Docker with library IDs/topics to report; for cloud/product/platform facts, require current official web sources.
- Report path: the durable handoff document the PM will read.

## Engineering Documentation Sources

Code-writing subagents must use Context7 through MCP Docker before changing implementation code, framework integration, tests, build tooling, or deployment scripts that depend on library/framework behavior.

Required behavior:

- Resolve each relevant library or framework with Context7 before implementation or surgery.
- Fetch focused Context7 docs for the task topic, such as FastAPI uploads, Vite env handling, Playwright testing, MLflow tracking, or provider SDK usage.
- Report the Context7 library ID and topic used in the subagent report.
- If Context7 is unavailable, record the failure mode, fallback source, and residual risk before coding.
- Do not use Context7 as the only source for cloud/product/platform current facts. Web search and official provider docs remain preferred for Google Cloud behavior, pricing, quotas, deployment guidance, API availability, security/compliance facts, and other fast-changing platform details.

Context7 local-tooling notes:

- On this machine, Context7 is expected through the MCP Docker surface.
- Reliable checks from prior local setup were `docker mcp tools ls`, `resolve-library-id`, and `get-library-docs`.
- When `resolve-library-id` returns explanatory text, choose the actual returned library ID explicitly; do not use placeholder examples such as `/org/project`.

## Verification Boundaries

PM may verify delivery through:

- Product and architecture docs.
- Subagent reports.
- Local or hosted web UI.
- Public or authenticated APIs.
- Logs.
- MLflow and observability UIs.
- Completion audits and acceptance checklists.

PM may not use direct product code or product doc editing as a substitute for delegation.

PM active review expectations:

- Open the public frontend URL while builders or QA are still running when a URL is available.
- Scroll the desktop and mobile UI, check obvious layout failures, and inspect screenshots or browser captures.
- Run narrow smoke commands against public or local service endpoints when credentials are not required, or with secret values passed only through redacted environment variables.
- Compare visible product behavior against the acceptance checklist and subagent reports.
- Record blockers early so subagents can fix them before the final handoff.

Heavy-task command guidance:

- Prefer `taskset -c 0-3 pytest`, `taskset -c 0-3 npm run build`, `taskset -c 0-3 npm test`, `taskset -c 0-3 npx playwright test`, `taskset -c 0-3 ffmpeg ...`, and `taskset -c 0-3 docker build ...` where the host supports `taskset`.
- If `taskset` is unavailable or the command does not tolerate CPU affinity, record the reason in the report and keep the run as narrow as practical.
- Do not use CPU limiting as an excuse to skip required verification.

## Release Readiness Lessons

PM and release reviewers must treat these as blocking checks for public prototype or production claims:

- A web deploy is not ready just because build passes or the public URL returns HTTP 200. QA must open the actual public URL, run desktop and mobile visual checks, capture screenshots, and link evidence in QA/report docs.
- A prototype voice demo is not ready for user testing unless the primary path uses a real TTS provider. Local beep/tone audio may exist only as a visibly labeled fallback when provider credentials are absent.
- If Playwright is blocked by missing browser libraries in a no-`sudo` environment, QA may temporarily download `.deb` dependencies such as `libgbm1`, `libasound2`, and `libwayland-server0` with `apt-get download`, extract them with `dpkg-deb -x` into `/tmp`, and run Playwright with `LD_LIBRARY_PATH` pointed at the extracted libraries. Real CI or maintained servers should install dependencies properly or use a browser-ready image.
- E2E selectors must be trustworthy before test results are trusted. Accessible names should be unique, or tests should use exact labels or stable test ids.
- Public frontend API configuration must be safe for external users. Do not default to `localhost` unless the browser is truly local; use explicit config or derive from `window.location.hostname` when appropriate.
- Public browser runtime errors such as `crypto.randomUUID is not a function` must be fixed with durable fallbacks before deployment is considered ready.
- Backend smoke must run as real HTTP against the deployed/public service. Unit tests and FastAPI `TestClient` are useful but insufficient for release evidence.
- Audio smoke must verify WAV downloads start with `RIFF` when WAV output is expected, and video smoke must verify job artifacts can be downloaded outside the container.
- Hot-patching a running container is never a final release state. The release state must be a rebuilt Docker image, restarted service, and rerun public smoke/visual QA.
- Evidence files matter. Screenshots, public API smoke summaries, artifact checks, logs, MLflow run ids, and release notes should be linked from QA/report docs.
- PM should stop adding features until the prototype-first core flow is visibly usable: public UI opens, core job or synthesis flow works, artifacts download, and evidence is linked.

## User-Provided Secrets

User-provided `OPENAI_API_KEY` values and all cloud/API keys are secrets. This includes Google Cloud keys, provider API keys, MLflow credentials, deploy tokens, CI/CD tokens, signed URL secrets, and temporary test keys.

Rules:

- Never commit a secret value.
- Never echo a secret value in terminal output, chat, docs, logs, reports, screenshots, or acceptance evidence.
- Never paste a secret value into subagent prompts, subagent reports, product docs, or completion summaries.
- Never place a real secret value in `.env.example`, sample config, curl examples, CI examples, or tutorial commands.
- Pass secrets only through environment variables for narrow, explicit test commands when no safer secret manager path is available.
- Redact any secret-like value as `[redacted]` in docs, logs, reports, and evidence.
- Recommend rotating any key that appeared in chat, terminal output, logs, reports, screenshots, or docs after test use.
- Prefer managed secret storage for persistent environments, such as Google Secret Manager, CI secret stores, or equivalent platform controls.
- Use least privilege and environment-specific keys. Do not reuse personal user keys as shared project, staging, or production credentials.

Subagent prompts that require secret-dependent verification must specify the secret variable name only, never the value. Example: use `OPENAI_API_KEY=[redacted]`, not an actual key.

## Evidence

This governance document is current when:

- New subagent prompts cite a valid skill and report path.
- Delivery reports state verification evidence and ownership boundaries.
- Code-writing reports list Context7 library IDs/topics used, or document why Context7 was unavailable.
- Reports and evidence redact user-provided API keys and cloud/API keys as `[redacted]`.
- `docs/acceptance-checklist.md` or relevant reports contain auditable completion evidence.
- PM completion summaries reference docs, reports, UI/API/log/MLflow evidence, or audits rather than direct code inspection.
- Public deploy claims include desktop/mobile screenshots from the actual public URL, real HTTP backend smoke, artifact download evidence, and rebuilt-image evidence after any hot patch.

## Open Questions

- Security does not yet have a dedicated project skill/report owner. Until one exists, security/privacy work is covered by product docs, backend, infra, QA, and tech lead review prompts with explicit write scope.
- Should PM governance violations block release, or create follow-up tasks when the delivered product behavior is otherwise acceptable?

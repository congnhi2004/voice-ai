# PM Artifact Completion Audit - 2026-05-10

Role: PM Artifact Completeness Auditor

Skill used: `voice-ai-product-docs`

Write scope respected: only this report was created. Existing product docs, reports, evidence files, and the untracked `docs/subagents/evidence/qa-audit-20260510/` directory were not edited.

## Verification Performed

- File inventory: `rg --files`, `wc -l`, `find docs/subagents -maxdepth 1`, and direct file existence checks.
- Recency: `git log --name-status -n 8 -- docs ... shine_read.md` shows the PM docs were created in `6e2fe3e` and key runtime docs were refreshed through `9cd8d36` and `039e0d6` on 2026-05-10.
- Public smoke: `GET http://103.27.237.252:4174/` returned HTTP 200; `GET http://103.27.237.252:8080/healthz` returned `{"status":"ok","service":"voice-ai","version":"0.1.0"}`; `GET /readyz` returned provider `openai`, storage `local`, MLflow ready, video provider `openai`, and FFmpeg available.
- Public TTS spot check: `POST /v1/synthesize` with `voice.name=marin` returned provider `openai`, `fallback=false`, model `gpt-4o-mini-tts`, WAV URL, and `mlflow_run_id=fb182e16b71848fd9ead08e79f30a1a2`.
- Evidence path check: latest evidence files exist under `docs/subagents/evidence/...`; several older checklist links still point to stale root-level `docs/subagents/final-gate-*` paths.
- Role skill check: all expected local skills exist under `/home/jhao/.codex/skills/`: `voice-ai-backend-builder`, `voice-ai-frontend-builder`, `voice-ai-infra-observability`, `voice-ai-pm-orchestrator`, `voice-ai-product-docs`, `voice-ai-qa-acceptance`, and `voice-ai-techlead-reviewer`.

## Current Official Sources Checked

External platform/API facts were judged because the docs claim Google Cloud, OpenAI, Cloud Run, FFmpeg, and MLflow behavior.

- Google Cloud Speech-to-Text supported languages: https://cloud.google.com/speech-to-text/docs/speech-to-text-supported-languages
- Google Cloud Translation language support: https://cloud.google.com/translate/docs/languages
- Google Cloud Text-to-Speech `text:synthesize`: https://docs.cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize
- Google Cloud Video Intelligence speech transcription: https://cloud.google.com/video-intelligence/docs/feature-speech-transcription
- OpenAI Text to speech guide: https://platform.openai.com/docs/guides/text-to-speech
- OpenAI Speech to text guide: https://platform.openai.com/docs/guides/speech-to-text

Result: the major external claims used by the docs are still directionally current: Speech-to-Text supports English/Chinese language coverage, Cloud Translation includes Vietnamese, Google TTS has synchronous `text:synthesize`, Video Intelligence speech transcription remains English (US) only for that feature, OpenAI exposes `gpt-4o-mini-tts`/`gpt-4o-mini-transcribe`, and OpenAI TTS voices include `marin` and `cedar`. No docs were edited to reflect this audit.

## Requested Artifact Checklist

| Requested artifact | Path/evidence | Status | Audit notes |
| --- | --- | --- | --- |
| Project brief | `docs/project-brief.md` lines 1-72 | Pass | Exists, current enough for handoff, links the tutorial, states outcomes, scope, non-goals, official references, and current source notes. Caveat: it still frames Google providers as the first sellable target while current public prototype uses OpenAI for real TTS/video. |
| PRD | `docs/prd.md` lines 1-105 | Pass with gaps | Exists and covers problem, goals, personas, functional/non-functional requirements, release criteria, risks, and source notes. Gap: video API paths in PRD use `/v1/videos` plus `/v1/localization-jobs`, while current reports/frontend use `/v1/video-localization/jobs`. |
| AI system design | `docs/ai-system-design.md` lines 1-130 | Pass with gaps | Exists with architecture, flows, provider contracts, fallback, storage, failure modes, and production decisions. Same API-route gap as PRD; it describes the intended split upload/job design, not the current multipart public endpoint. |
| Sprint plan per subagent/workstream | `docs/sprint-plan.md` lines 1-160 | Pass with gaps | Exists and is organized by Backend, Frontend, Infra, QA, and Docs for each sprint. It is usable as a workstream plan, but not a current per-named-subagent status board. |
| Security/privacy | `docs/security-privacy.md` lines 1-111 | Pass | Exists and covers auth, secrets, user-provided API key handling, privacy controls, retention, CORS, abuse prevention, and security acceptance. |
| Observability/MLflow | `docs/observability-mlflow.md` lines 1-116 | Pass with production blockers | Exists and is usable as a design target. Current public spot check shows TTS MLflow run id now present, but acceptance docs still contain older MLflow 403 evidence and no dashboard/alert proof for production readiness. |
| Deployment runbook | `docs/deployment-runbook.md` lines 1-151 | Pass with production blockers | Exists and includes local run, Cloud Run deployment, concrete repo artifacts, staging checks, rollback, and operational risks. Referenced `.github/workflows/*`, `deploy/*` templates, lifecycle files, secret map, and release checklist all exist. Production Cloud Run/GCS/rollback evidence remains blocked per completion audit. |
| API contract | `docs/api-contract.md` lines 1-442 | Fail for current public video contract | Exists and is substantial for TTS and intended video design, but current public/reported video route is `/v1/video-localization/jobs`, not documented `/v1/videos` plus `/v1/localization-jobs`. The file also has duplicate rendered lines around `MAX_VIDEO_UPLOAD_MB` and one duplicate `checksum_sha256` line. |
| Acceptance checklist | `docs/acceptance-checklist.md` lines 1-32 | Fail for evidence hygiene, pass as risk ledger | Exists and has concrete statuses. Gaps: several referenced paths are stale root-level `docs/subagents/final-gate-*`; the actual files exist under `docs/subagents/evidence/...`. Some older rows say local fallback/MLflow failures while newer completion audit and live spot check show OpenAI and MLflow run ids. |
| Tutorial from zero to production with mistakes learned | `docs/tutorial-from-zero-to-production.md` lines 1-541 | Pass | Exists, long-form, handoff-friendly, includes process from empty workspace to production path and a specific "Lessons Learned / Avoid These Mistakes" section at lines 456-507. The living checklist at lines 509-541 remains template-style `Not started`, so it should not be treated as current release evidence. |
| `shine_read.md` short project guide | `shine_read.md` lines 1-73 | Pass with stale placeholders | Exists in Vietnamese with diacritics and gives product purpose, architecture, test link, manual test steps, limits, and next docs. Gaps: MLflow/Public URL rows still show `[PM/Infra cần điền]`; known limitations include older local/demo/FFmpeg/Playwright notes that are partially superseded by later reports. |
| Subagent docs organization | `docs/subagents/README.md` lines 1-44 plus `docs/subagents/evidence/*` | Pass | README is Vietnamese with diacritics, links active reports, and defines evidence folders. Evidence inventory confirms images, audio, video, and API files are organized under `evidence/`. |
| Vietnamese diacritics | `shine_read.md`, `docs/subagents/README.md`, Vietnamese sections in audits/tutorial | Pass | User-facing Vietnamese docs inspected use Vietnamese diacritics. Caveat: some generated local-demo transcript evidence strings are unaccented, but those are product artifact outputs, not documentation prose. |
| Links for frontend testing | `shine_read.md` lines 22-45; `docs/subagents/README.md` lines 30-36; public smoke check | Pass with caveats | Main public frontend `http://103.27.237.252:4174/` returned HTTP 200 during audit; frontend browser evidence exists at `docs/subagents/evidence/api/final-gate-frontend-browser-check-20260510.json`. Caveat: local fallback link in `shine_read.md` says `localhost:4173`, while current reports frequently use public/local `4174`. |
| Role skills for subagents | `/home/jhao/.codex/skills/*/SKILL.md`; `docs/pm-governance.md` lines 30-64; skill author reports | Pass with governance cleanup needed | All expected local skills exist and skill author reports record validation. Gap: `docs/pm-governance.md` still has an open question asking which skills are approved, and its role map says Infra has no dedicated durable report even though `docs/subagents/infra-report.md` exists. |

## Gaps

1. API contract drift is the highest documentation issue. PRD, system design, and API contract describe `/v1/videos` plus `/v1/localization-jobs`, while current frontend/backend/reports repeatedly use `POST /v1/video-localization/jobs` and artifact downloads under `/v1/video-localization/jobs/{job_id}/artifacts/{filename}`.
2. Acceptance evidence paths need cleanup. Actual final-gate artifacts live under `docs/subagents/evidence/images`, `docs/subagents/evidence/api`, `docs/subagents/evidence/audio`, and `docs/subagents/evidence/video`; older checklist rows still link root-level `docs/subagents/final-gate-*` paths that do not exist.
3. Current-state claims conflict across audit layers. `docs/subagents/completion-audit-20260510.md` says public OpenAI/MLflow is working, live TTS spot check supports that, but `docs/acceptance-checklist.md` and final-gate evidence files still include older local fallback and MLflow 403 failures.
4. `shine_read.md` is useful as a quick guide, but its technical links section has placeholders and its known limitations are partly stale after the later OpenAI/FFmpeg/runtime work.
5. Governance role map is mostly useful but internally stale: it has an unresolved skill-approval question and does not recognize the existing infra durable report.
6. Commercial production handoff remains blocked by lack of live Cloud Run/GCP deployment evidence, durable GCS storage proof, production auth/billing proof, alert/dashboard links, rollback evidence, and clean published release evidence.

## Readiness Recommendation

Recommendation: **Pass for tutorial/project handoff of the current public prototype, fail for production/commercial handoff until docs are reconciled.**

The documentation package is broad, mostly current, and usable for onboarding another PM, engineer, QA agent, or reviewer into the product. The strongest handoff path is:

1. `shine_read.md`
2. `docs/tutorial-from-zero-to-production.md`
3. `docs/project-brief.md`
4. `docs/prd.md`
5. `docs/api-contract.md` with the route-drift caveat above
6. `docs/subagents/completion-audit-20260510.md`
7. `docs/subagents/README.md`

Before claiming "production-ready documentation", update the API contract and related PRD/system-design route references, repair stale evidence links in the acceptance checklist, reconcile old local-fallback evidence with the latest OpenAI runtime evidence, complete `shine_read.md` placeholders, and refresh governance role-map status.

# Sprint Plan

## Delivery Model

Parallel workstreams can proceed from the contracts in this docs package. Agents must avoid overwriting each other and should record evidence in `docs/acceptance-checklist.md`.

PM delegation, subagent assignment, web-research expectations, and verification boundaries are governed by `docs/pm-governance.md`.

The end-to-end implementation and release learning path is documented in `docs/tutorial-from-zero-to-production.md`.

## Sprint 0: Foundation

Backend:

- Scaffold FastAPI app structure.
- Implement config loading and environment validation.
- Implement health/readiness endpoints.
- Implement provider interface and local fallback provider.

Frontend:

- Define minimal TTS screen flow.
- Stub API client against documented contract.

Infra:

- Define Cloud Run service, Artifact Registry, and secret strategy.
- Decide production audio storage bucket and URL policy.

QA:

- Create contract test plan.
- Create local fallback synthesis tests.

Docs:

- Keep PRD, API contract, and acceptance checklist current as implementation decisions change.

## Sprint 1: Core TTS

Backend:

- Implement `GET /v1/voices`.
- Implement `POST /v1/synthesize`.
- Implement local static audio serving.
- Implement Google provider mapping to Text-to-Speech request/response.
- Add structured errors and request ids.

Frontend:

- Build text input, voice selector, encoding selector, submit, and playback.
- Show validation/provider errors.

Infra:

- Add CI for lint, tests, and container build.
- Add staging deploy pipeline.

QA:

- Validate local provider without Google credentials.
- Validate API response schema.
- Validate audio file retrieval.

Docs:

- Record implementation deviations from API contract.
- Add curl examples if final routes differ.

## Sprint 2: Production Hardening

Backend:

- Add API key auth and CORS allowlist.
- Add MLflow run logging.
- Add audio checksum and metadata.
- Add idempotency-key handling if capacity allows.

Frontend:

- Add loading states and generation history for current session.
- Add audio download behavior according to access policy.

Infra:

- Configure Cloud Run service identity and secrets.
- Add staging/prod environment variables.
- Add Cloud Storage bucket for production audio.
- Add rollback runbook validation.

QA:

- Run staging smoke test using Google provider.
- Verify MLflow run creation.
- Verify logs exclude raw text.

Docs:

- Complete acceptance evidence fields for release candidate.

## Sprint 3: Launch Readiness

Backend:

- Add rate limits and request size enforcement.
- Add provider timeout/retry policy.
- Add cost/usage counters.

Frontend:

- Polish UX for error recovery and audio playback.
- Confirm accessibility basics.

Infra:

- Add dashboards and alerts.
- Add production deployment approval gate.

QA:

- Run security and privacy checklist.
- Run load smoke for target concurrency.
- Verify rollback.

Docs:

- Freeze release notes and handoff notes.

## Backlog By Agent

Backend:

- Batch synthesis.
- Async long-form job API.
- Tenant-scoped usage accounting.
- SSML validation helper.

Frontend:

- Saved generations.
- Voice preview catalog.
- Tenant/admin settings.

Infra:

- Terraform or IaC modules.
- CDN for audio.
- Multi-region serving.

QA:

- Golden audio regression suite.
- Provider fault injection.
- Contract tests published as CI artifact.

Docs:

- Customer integration guide.
- Incident response playbooks.
- API changelog.

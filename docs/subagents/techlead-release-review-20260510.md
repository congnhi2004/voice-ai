# Tech Lead Release Review - 2026-05-10

Role: Tech Lead Release Reviewer  
Skill: `voice-ai-techlead-reviewer`  
Repo: `/home/jhao/code/voice-ai`  
Write scope honored: this report only. No product code, tests, deploy config, runtime env, or existing docs were edited.

## Final Release Recommendation

**Block commercial production release.**

The current public prototype is usable for controlled TTS and short video-localization testing: the live public runtime reports OpenAI active, `/readyz` is healthy, `/v1/voices` includes `marin` and `cedar`, and recent gate evidence shows OpenAI TTS/video artifacts with MLflow run ids. It is not production-release ready because live GCP deployment, durable storage, production billing, release publication, and production-grade auth/abuse controls are still unproven or broken.

## Severity-Ordered Findings

### P0 - Commercial release has no proven production deployment, durable storage, or release publication path

Evidence:

- Current git state is `main...origin/main [ahead 8]`; latest local commit is `9cd8d36 Redesign public studio UI and auth billing runtime`.
- `GIT_TERMINAL_PROMPT=0 git push --dry-run origin HEAD` failed: `fatal: could not read Username for 'https://github.com': terminal prompts disabled`.
- Current public `/readyz` returns `provider.name=openai`, but `storage.mode=local`; `/v1/product/capabilities` reports `environment=local`, `billing.available=false`, and `billing.production_billing=false`.
- `./scripts/local-services.sh status` shows the public runtime is tmux/Docker based on `voice-ai:durable-20260510`, not Cloud Run. It confirms `OPENAI_API_KEY: set` without exposing the value, `GOOGLE_APPLICATION_CREDENTIALS: unset`, and containers `voice-ai-backend` / `voice-ai-mlflow` are up locally.
- `docs/subagents/release-runtime-gate-20260510.md:81-91` explicitly says the gate does not prove live Cloud Run, Artifact Registry, GCS persistence, Secret Manager wiring, Cloud Tasks/job processing, production identity, production billing, alerting dashboards, public MLflow access, or GitHub release publication.

Affected path or product surface:

- Runtime release process, Cloud Run/GCP production deployment, GitHub release state, storage durability.

Impact:

- A commercial release would run without proof of deployability, rollback, durable media persistence, or pushed CI/release provenance. Local filesystem artifacts can be lost on container restart and cannot satisfy production retention/access requirements.

Recommended fix:

- Push the release branch through secure GitHub auth, run CI, deploy to staging Cloud Run, capture service URL, revision, image digest, Secret Manager mappings, runtime service account, GCS object proof, smoke-test output, rollback proof, and then promote the same digest to production.

Owner suggestion:

- Infra/release owner with backend support for GCS proof.

### P1 - Stripe billing lifecycle cannot work end to end

Evidence:

- Runtime capabilities currently return `billing.available=false`, `mode=not-configured`, and `production_billing=false`.
- Backend routes are `/v1/billing/checkout-session` and `/v1/billing/customer-portal` in `app/main.py:246-265`.
- Frontend client calls `/v1/billing/checkout` and `/v1/billing/portal` in `frontend/src/api.ts:409-425`, so Checkout and portal redirects will 404 even after Stripe secrets are configured.
- Webhook handling verifies Stripe signatures and records duplicate event ids, but `checkout.session.completed` unconditionally provisions `status="active"` without checking payment status or retrieving/expanding line items (`app/auth_billing.py:427-450`).
- Official Stripe docs checked say Checkout fulfillment must be webhook-driven, idempotent, retrieve the Checkout Session with line items, check `payment_status`, and record fulfillment state; subscription access should be driven by subscription/invoice webhook events such as `invoice.paid`, `invoice.payment_failed`, and `customer.subscription.updated`.

Affected path or product surface:

- `frontend/src/api.ts`, `app/main.py`, `app/auth_billing.py`, paid plan purchase, billing portal, entitlement provisioning.

Impact:

- Paid users cannot complete Checkout from the frontend. If endpoint names are fixed without tightening webhook provisioning, the app can over-provision subscription access from incomplete or unpaid sessions.

Recommended fix:

- Align frontend routes with backend routes or add compatible backend aliases. Configure live Stripe secrets/price ids/URLs. Rework fulfillment around Stripe-recommended webhook events and payment/subscription status checks, with idempotent persisted fulfillment state and negative tests for unpaid, incomplete, deleted, and payment-failed subscriptions.

Owner suggestion:

- Backend billing owner plus frontend owner.

### P1 - Auth/session posture is not production-grade and runtime capabilities overstate identity readiness

Evidence:

- Current capabilities report `auth.production_identity=true`, but the same response reports `environment=local` and `auth.storage=sqlite`.
- `app/frontend_support.py:34-40` marks production identity as `settings.auth_configured`; in non-production, `Settings.jwt_secret` silently falls back to `local-dev-only-change-auth-jwt-secret-before-production` (`app/config.py:73-83`).
- `frontend/src/main.ts:216-218` initializes `sessionToken` from `localStorage`; bearer tokens are then sent from the browser client. This is acceptable for prototype testing but higher risk for production web sessions.
- There is no observed rate limit, account lockout, password reset, email verification, MFA, tenant isolation, audit log, managed user store, or production migration path.

Affected path or product surface:

- Auth endpoints, account state, token storage, `/v1/product/capabilities`, public frontend sessions.

Impact:

- External commercial users would rely on local SQLite and browser-stored bearer tokens. The public UI may claim production identity when the runtime is still local/demo-shaped, making release readiness hard to assess and increasing account-abuse risk.

Recommended fix:

- Gate `production_identity` on explicit production/staging config, a non-default JWT secret, and a durable managed user store. Add rate limits/lockouts and abuse telemetry for register/login/synthesize/video endpoints. Move production web sessions to a hardened pattern such as short-lived access tokens plus secure refresh/session handling, and document the accepted threat model.

Owner suggestion:

- Backend/auth owner with frontend session handling review.

### P1 - Provider limits and frontend/backend validation are inconsistent with current OpenAI Audio limits

Evidence:

- Official OpenAI Audio API reference checked says `audio/speech` input has a maximum length of 4096 characters and built-in voices include `alloy`, `ash`, `ballad`, `coral`, `echo`, `fable`, `onyx`, `nova`, `sage`, `shimmer`, `verse`, `marin`, and `cedar`.
- The backend default `max_input_chars` is 5000 (`app/config.py:35-39` plus load default), and `/v1/synthesize` only checks `settings.max_input_chars` before calling the provider (`app/main.py:318-328`).
- Official OpenAI speech-to-text docs checked say file uploads are limited to 25 MB. Backend enforces 25 MB for uploaded video bytes (`app/video_localization.py:26`, `app/video_localization.py:200-208`), but frontend permits 250 MB before submit (`frontend/src/main.ts:209`) and deploy config advertises `MAX_UPLOAD_BYTES=524288000`, which current code does not consume.

Affected path or product surface:

- `/v1/synthesize`, `/v1/video-localization/jobs`, frontend video upload UX, deploy env.

Impact:

- Users can submit text/video sizes that the UI or env suggests are valid but the provider/backend cannot process. OpenAI TTS inputs between 4097 and 5000 characters can fail as provider errors instead of deterministic contract errors. Video uploads over 25 MB pass frontend validation but fail backend.

Recommended fix:

- Set provider-aware limits in backend and expose them through capabilities. For OpenAI TTS, reject above 4096 chars before the API call or chunk synthesis intentionally. Make frontend upload limits reflect backend/provider limits, or implement a real large-video path that extracts/chunks audio before OpenAI upload and updates docs/tests accordingly.

Owner suggestion:

- Backend API contract owner plus frontend owner.

### P1 - Video localization is still synchronous request work, not the documented production worker/runtime model

Evidence:

- `/v1/video-localization/jobs` reads the full upload, then calls `localize_video(...)` inline and returns the completed status (`app/main.py:431-470`).
- `localize_video` writes source media, transcript, subtitles, voiceover, and rendered video under the job directory before returning (`app/video_localization.py:520-560` and later artifact writes).
- Production docs say the target shape is GCS source upload, Cloud Tasks HTTP task to `/internal/tasks/video-localization`, bounded stage processing, Cloud Storage outputs, and MLflow parent/stage runs (`deploy/README.md:146-159`).
- The workflow/deploy config mentions `JOB_DISPATCH_MODE=cloud_tasks` and Cloud Run Jobs, but the inspected app has no production task handler evidence.

Affected path or product surface:

- `/v1/video-localization/jobs`, long-running videos, retries, cancellation, worker isolation, Cloud Run timeout behavior.

Impact:

- Short public prototype videos work, but production workloads can tie up request threads, lose work on restart, duplicate work on client retry, and fail without recoverable stage state.

Recommended fix:

- Implement the documented async job model: durable job records, GCS source/artifact storage, Cloud Tasks or Cloud Run Job dispatch, idempotent stage execution, retry/cancel semantics, and status polling that does not depend on request lifetime.

Owner suggestion:

- Backend video/infra owners.

### P1 - MLflow and media artifact handling still need a production privacy decision

Evidence:

- MLflow readiness only sets the experiment and returns ready (`app/observability.py:22-32`); it does not verify that a run can log the artifact class required by acceptance.
- `MLFLOW_LOG_AUDIO_ARTIFACTS` defaults true (`app/config.py:38`), and `track_synthesis` logs the generated audio artifact when the file exists (`app/observability.py:100-111`).
- Current public MLflow endpoint by IP is documented as HTTP 403 `Invalid Host header` (`docs/subagents/release-runtime-gate-20260510.md:31`, `docs/subagents/release-runtime-gate-20260510.md:89`), while backend-to-MLflow tracking works internally.
- Official MLflow docs checked say artifact stores hold large artifacts and default to local `./mlruns`, while remote stores such as Google Cloud Storage require explicit artifact-store configuration and access management.

Affected path or product surface:

- MLflow tracking server, generated audio/video privacy, observability readiness, public/internal observability access.

Impact:

- Production may log user-generated speech artifacts to MLflow without a reviewed retention/access policy. Readiness can pass even if artifact logging fails. Public observability is neither safely exposed nor clearly internal-only in runtime evidence.

Recommended fix:

- Decide and document whether MLflow is internal-only. For production, disable raw audio artifact logging unless explicitly approved, or store artifacts in governed GCS with retention and access controls. Extend readiness/smoke checks to prove run creation plus expected artifact metadata logging.

Owner suggestion:

- Infra/observability owner with privacy review.

### P2 - Structured logs exist, but production abuse controls and alerting are incomplete

Evidence:

- `logs/backend.log` contains structured request and synthesis/video completion events with request id, route, status, latency, provider, and job id.
- No code evidence was found for per-user/IP/provider quota, request throttling, paid-plan entitlement enforcement on synthesis/video endpoints, abuse dashboards, or Cloud Monitoring alert policies.
- `/v1/synthesize` and `/v1/video-localization/jobs` depend only on API key/session dependency depending on runtime config, not subscription entitlement checks.

Affected path or product surface:

- Public API, provider spend controls, commercial quotas, incident response.

Impact:

- A released service can be abused to consume OpenAI quota or CPU/FFmpeg resources. Paying and free users are not enforced by production entitlements.

Recommended fix:

- Add rate limits, per-plan usage accounting, quota enforcement, request-size limits exposed through capabilities, provider error alerts, and Cloud Logging/Monitoring dashboards before commercial launch.

Owner suggestion:

- Backend platform owner.

## Tests And Reports Checked

Commands run in this review:

- `git status --short --branch` -> `main...origin/main [ahead 8]`, plus untracked `docs/subagents/evidence/qa-audit-20260510/`.
- `git log --oneline -1 --decorate` -> `9cd8d36 (HEAD -> main) Redesign public studio UI and auth billing runtime`.
- `GIT_TERMINAL_PROMPT=0 git push --dry-run origin HEAD` -> failed due missing HTTPS credential prompt.
- `taskset -c 0-3 ./scripts/local-services.sh status` -> public local runtime up; OpenAI key set/unprinted; Google credentials unset.
- `curl http://103.27.237.252:8080/readyz` -> ready, OpenAI provider, local storage, MLflow ready, video provider OpenAI.
- `curl http://103.27.237.252:8080/v1/product/capabilities` -> OpenAI active, video demo false, auth production_identity true with sqlite, billing unavailable.
- `curl http://103.27.237.252:8080/v1/voices?language_code=vi-VN` -> OpenAI voice list includes `marin` and `cedar`.
- First backend test attempt failed because `app` was not on `PYTHONPATH`.
- `PYTHONPATH=. taskset -c 0-3 .venv/bin/pytest tests/backend/test_api.py -q` -> `30 passed, 3 skipped, 2 warnings`.
- `taskset -c 0-3 npm run lint` -> passed.
- `taskset -c 0-3 npm test` -> `4 passed`.
- `taskset -c 0-3 npm run build` -> passed, Vite built `dist`.

Reports/docs checked:

- `docs/subagents/release-runtime-gate-20260510.md`
- `docs/subagents/completion-audit-20260510.md`
- `docs/subagents/techlead-runtime-review-20260510.md`
- `docs/subagents/qa-public-runtime-20260510.md`
- `docs/deployment-runbook.md`
- `deploy/README.md`
- `deploy/secret-manager-map.md`
- `deploy/release-smoke-checklist.md`
- `.github/workflows/deploy-cloud-run.yml`

## Official Sources Checked

- OpenAI Text to Speech guide: `https://platform.openai.com/docs/guides/text-to-speech`
- OpenAI Audio API reference: `https://platform.openai.com/docs/api-reference/audio`
- OpenAI Speech to Text guide: `https://platform.openai.com/docs/guides/speech-to-text`
- Google Cloud Run service identity: `https://cloud.google.com/run/docs/securing/service-identity`
- Google Cloud Run configure service identity: `https://cloud.google.com/run/docs/configuring/services/service-identity`
- Google Cloud Run configure secrets: `https://cloud.google.com/run/docs/configuring/services/secrets`
- Google Cloud Run environment variables: `https://cloud.google.com/run/docs/configuring/services/environment-variables`
- Stripe Checkout fulfillment: `https://docs.stripe.com/checkout/fulfillment`
- Stripe subscriptions webhooks: `https://docs.stripe.com/billing/subscriptions/webhooks`
- Stripe webhook signature verification: `https://docs.stripe.com/webhooks/signatures`
- Stripe customer portal: `https://docs.stripe.com/customer-management`
- MLflow Tracking and artifact stores: `https://www.mlflow.org/docs/latest/ml/tracking`, `https://mlflow.org/docs/2.22.0/tracking/artifacts-stores`

## Context7

Not used. This review did not require exact framework/library API-change guidance. The recommendations are release-readiness, endpoint contract, provider-limit, deployment, billing-lifecycle, and privacy/control findings based on code inspection plus official service docs.

## Residual Risks

- I did not run a fresh paid Stripe Checkout flow because Stripe is not configured in the current runtime.
- I did not deploy to GCP because credentials and project configuration are not present in this workspace.
- I did not run browser E2E in this pass; I relied on current frontend lint/unit/build plus the existing public runtime and E2E reports.
- Public runtime can change independently of this report because it is managed by tmux/local Docker sessions.
- OpenAI behavior can change; the report uses official docs checked on 2026-05-10.

## Release Decision

- Controlled public prototype testing: **Proceed with accepted risks** for short OpenAI TTS and short OpenAI video-localization demos only.
- Commercial production release: **Block release** until P0/P1 findings are fixed or explicitly accepted by the PM with compensating controls.

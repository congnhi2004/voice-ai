# Infra Cloud Production Hardening - 2026-05-10

Role: Infra Cloud Run and Observability Engineer
Scope: `deploy/**`, `scripts/cloud-run-*.sh`, `.github/workflows/**`, deployment runbook docs, and this report. Backend/frontend implementation files were not edited by this agent.

## Selected Production Async Path

Selected path: **Cloud Tasks HTTP target to the Cloud Run service**.

Rationale:

- The current backend exposes HTTP service endpoints and GCS/signed URL storage behavior.
- The current backend does not include a separate Cloud Run Job entrypoint or worker command that can be deployed independently without backend changes.
- Cloud Run Job deployment artifacts were removed from the active deploy path to eliminate ambiguity. Future Cloud Run Jobs would require a backend-owned job entrypoint, idempotency contract, and separate smoke evidence.

Current caveat:

- The current public backend still processes `POST /v1/video-localization/jobs` synchronously. The infra path now declares and provisions Cloud Tasks, queue IAM, and handler env wiring for `/internal/tasks/video-localization`, but commercial approval still requires backend implementation and live evidence for that internal handler.

## Files Changed

- `.github/workflows/deploy-cloud-run.yml`
  - Removed Cloud Run Job dispatch input and job create/update step.
  - Builds and pushes the image tag, resolves the Artifact Registry digest, deploys the digest URI, and prints the digest as release evidence.
  - Runs `scripts/cloud-run-observe.sh` after deploy.
- `deploy/cloud-run-deploy-operator.sh`
  - Dry-run-first deploy path now renders Artifact Registry, Docker build/push, Cloud Run service deploy, Secret Manager bindings, Cloud Tasks queue readback, and service URL/revision readback.
  - Forces `JOB_DISPATCH_MODE=cloud_tasks`.
- `scripts/cloud-run-deploy.sh`
  - Aligned one-shot service deploy with OpenAI production envs, GCS storage, Secret Manager mappings, Cloud Tasks envs, and Cloud Tasks service account invoker binding.
- `scripts/cloud-run-iam-bootstrap.sh`
  - Added `DRY_RUN=1` command rendering.
  - Renders/enables APIs, service accounts, Artifact Registry, private GCS buckets, lifecycle policies, Secret Manager resources, runtime secret access, bucket IAM, signed URL signing support, Cloud Tasks queue policy, enqueuer role, and Cloud Tasks OIDC impersonation binding.
- `scripts/cloud-run-observe.sh`
  - Added dry-run and live smoke/observe coverage for service URL, revisions, traffic, image digest, redacted env/secret inventory, `/healthz`, `/readyz`, bucket lifecycle, object inventory, signed URL GET status, Cloud Tasks status, Cloud Logging, Cloud Monitoring checklist, and MLflow privacy stance.
- `deploy/cloud-run-service.yaml.template`
  - Aligned service template with `STORAGE_PROVIDER=gcs` and Cloud Tasks envs.
- `deploy/cloud-run-video-job.yaml.template`
  - Deleted to remove the inactive Cloud Run Jobs production path.
- `deploy/README.md`
  - Documents Cloud Tasks as the selected production async path and the current backend caveat.
- `deploy/release-smoke-checklist.md`
  - Replaced job smoke with Cloud Tasks queue/IAM checks and observe script evidence.
- `deploy/secret-manager-map.md`
  - Clarified Cloud Tasks queue and service account as production async resources.
- `docs/deployment-runbook.md`
  - Removed stale Cloud Run Job workflow/template references.
- `docs/subagents/infra-cloud-production-hardening-20260510.md`
  - This report.

## Sources Checked

PM-provided official/current sources were used for Cloud Run Jobs, Cloud Tasks auth/HTTP targets, Cloud Run secrets, GCS signed URLs/lifecycle, and MLflow tracking architecture.

Additional current sources checked:

- Google GitHub Actions auth README: https://github.com/google-github-actions/auth
- Google GitHub Actions deploy-cloudrun README: https://github.com/google-github-actions/deploy-cloudrun

Context7 was not applicable because this task changed shell scripts, GitHub Actions YAML, and deployment docs, not library/framework APIs.

## Verification

Commands run:

```bash
taskset -c 0-3 docker compose config --quiet
bash -n scripts/cloud-run-deploy.sh scripts/cloud-run-iam-bootstrap.sh scripts/cloud-run-observe.sh deploy/cloud-run-deploy-operator.sh
python3 - <<'PY'
import json
from pathlib import Path
for path in ['deploy/gcs-audio-lifecycle.json','deploy/gcs-video-artifact-lifecycle.json']:
    json.loads(Path(path).read_text())
    print(f'{path}: ok')
PY
python3 - <<'PY'
import yaml
for path in ['.github/workflows/ci.yml','.github/workflows/deploy-cloud-run.yml','deploy/cloud-run-service.yaml.template']:
    with open(path, 'r', encoding='utf-8') as f:
        yaml.safe_load(f)
    print(f'{path}: ok')
PY
```

Results:

- Docker Compose config: passed.
- Shell syntax: passed.
- Lifecycle JSON parse: passed for both lifecycle files.
- YAML parse: passed for CI workflow, deploy workflow, and service template.

Dry-run commands run with placeholder values:

```bash
DRY_RUN=1 GCP_PROJECT_ID=voice-ai-placeholder REGION=us-central1 ARTIFACT_REPOSITORY=voice-ai DEPLOY_SERVICE_ACCOUNT=voice-ai-deploy@voice-ai-placeholder.iam.gserviceaccount.com RUNTIME_SERVICE_ACCOUNT=voice-ai-run@voice-ai-placeholder.iam.gserviceaccount.com TASKS_SERVICE_ACCOUNT=voice-ai-tasks@voice-ai-placeholder.iam.gserviceaccount.com GCS_AUDIO_BUCKET=voice-ai-placeholder-audio GCS_ARTIFACT_BUCKET=voice-ai-placeholder-artifacts API_KEYS_SECRET_NAME=voice-ai-api-keys OPENAI_API_KEY_SECRET_NAME=voice-ai-openai-api-key CLOUD_TASKS_QUEUE=voice-ai-video bash scripts/cloud-run-iam-bootstrap.sh
DRY_RUN=1 GCP_PROJECT_ID=voice-ai-placeholder REGION=us-central1 ENVIRONMENT=staging SERVICE_NAME=voice-ai ARTIFACT_REPOSITORY=voice-ai CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT=voice-ai-run@voice-ai-placeholder.iam.gserviceaccount.com CLOUD_TASKS_SERVICE_ACCOUNT=voice-ai-tasks@voice-ai-placeholder.iam.gserviceaccount.com GCS_AUDIO_BUCKET=voice-ai-placeholder-audio GCS_ARTIFACT_BUCKET=voice-ai-placeholder-artifacts API_KEYS_SECRET_NAME=voice-ai-api-keys OPENAI_API_KEY_SECRET_NAME=voice-ai-openai-api-key MLFLOW_TRACKING_URI=https://mlflow.example.invalid CLOUD_TASKS_QUEUE=voice-ai-video bash deploy/cloud-run-deploy-operator.sh
DRY_RUN=1 GCP_PROJECT_ID=voice-ai-placeholder REGION=us-central1 SERVICE_NAME=voice-ai CLOUD_TASKS_QUEUE=voice-ai-video GCS_AUDIO_BUCKET=voice-ai-placeholder-audio GCS_ARTIFACT_BUCKET=voice-ai-placeholder-artifacts SIGNED_URL_TO_TEST='https://storage.googleapis.com/redacted?X-Goog-Signature=redacted' bash scripts/cloud-run-observe.sh
```

Dry-run results:

- IAM bootstrap rendered API enablement, service account creation, Artifact Registry repository, bucket create/update/lifecycle, Secret Manager create/bind, bucket IAM, runtime signed URL signing role, Cloud Tasks queue update, enqueuer role, and Cloud Tasks OIDC impersonation binding.
- Deploy operator rendered Artifact Registry auth/create, Docker build/push, Cloud Run service deploy with `JOB_DISPATCH_MODE=cloud_tasks`, `--set-secrets`, Cloud Tasks service account `roles/run.invoker`, Cloud Tasks queue readback, and service URL/revision readback.
- Observe script rendered service metadata, revision/traffic/image digest readback, redacted env/secret inventory, `/healthz`, `/readyz`, GCS lifecycle/object checks, signed URL GET smoke without printing URL, Cloud Tasks status, Cloud Logging query, Cloud Monitoring checklist, and MLflow privacy stance.

No live GCP credentials or secret values were used or printed.

## Remaining Live-Credential Steps

Run these with staging credentials first:

1. `DRY_RUN=0 scripts/cloud-run-iam-bootstrap.sh` with real project, region, bucket names, service accounts, Secret Manager secret names, and `PROJECT_NUMBER`.
2. Add secret versions separately without echoing values:

```bash
printf %s "$API_KEYS_VALUE" | gcloud secrets versions add "$API_KEYS_SECRET_NAME" --data-file=-
printf %s "$OPENAI_API_KEY_VALUE" | gcloud secrets versions add "$OPENAI_API_KEY_SECRET_NAME" --data-file=-
```

3. Dispatch `.github/workflows/deploy-cloud-run.yml` for staging using GitHub OIDC.
4. Confirm the workflow deployed the digest URI printed by the image step, not just a mutable tag.
5. Run `scripts/cloud-run-observe.sh` with live env values and `RELEASE_SMOKE_API_KEY` if authenticated endpoint smoke is required.
6. Generate or capture one app-produced GCS signed URL, set `SIGNED_URL_TO_TEST`, and rerun observe to capture only the HTTP code.
7. After the backend internal task handler exists, enqueue one Cloud Tasks HTTP task to `/internal/tasks/video-localization` and capture queue/task/log evidence.

## Evidence PM Must Capture Before Commercial Approval

- Cloud Run service URL, latest ready revision, traffic split, runtime service account, and deployed image digest.
- Artifact Registry image digest from GitHub Actions and matching Cloud Run revision image digest.
- Secret Manager bindings for `API_KEYS` and `OPENAI_API_KEY` without printing values.
- Private GCS bucket proof: uniform bucket-level access, public access prevention, lifecycle policy, sample audio object, sample source/intermediate/rendered video objects.
- Signed URL proof: one generated object URL returns HTTP 200 before expiry and does not appear in logs or MLflow.
- Cloud Tasks proof: queue config, OIDC service account, `roles/run.invoker` binding, one task dispatch/execution status, retry/failure behavior, and handler logs.
- `/healthz` and `/readyz` from the Cloud Run URL.
- Cloud Logging query showing structured request/job fields and no raw transcripts, source media, full signed URLs, or secrets.
- Cloud Monitoring dashboard or query evidence for request count, latency, error logs, queue task attempts, queue depth/age, and alert policy ownership.
- MLflow evidence: internal-only tracking URI, run id metadata, no raw media/transcript leakage unless explicitly approved.
- Rollback evidence: previous revision or previous digest redeploy/update-traffic command and successful smoke after rollback.

## Production Approval Stance

Infra deploy and observe paths are now unambiguous and dry-run-verifiable without credentials. Commercial production approval remains blocked until live Cloud Run/GCS/Secret Manager/Cloud Tasks/GitHub Actions evidence is captured and the backend-owned internal Cloud Tasks handler exists.

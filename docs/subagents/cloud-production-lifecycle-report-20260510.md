# Cloud Production Lifecycle Report - 2026-05-10

Role: Cloud Production Lifecycle Agent
Skill: `voice-ai-infra-observability`
Scope: `.github/workflows/**`, `deploy/**`, `docs/deployment-runbook.md`, and this report. No backend/frontend app code, runtime scripts, or secret files were edited.

## Files Changed

- `.github/workflows/ci.yml`
  - Adds frontend `npm ci`, lint, tests, and build to the existing backend test, compose config, Docker build, and video smoke CI path.
- `.github/workflows/deploy-cloud-run.yml`
  - Keeps deployment manual through `workflow_dispatch`.
  - Adds a verify job that runs backend tests, frontend checks/build, compose config, and a local Docker build before cloud auth.
  - Builds and pushes to Artifact Registry through GitHub OIDC, then deploys Cloud Run with OpenAI `marin`, Secret Manager secret mappings, GCS env placeholders, and Cloud Run job creation/update for video processing.
- `deploy/cloud-run-deploy-operator.sh`
  - Dry-run-first operator script for image build/push, service deploy, and video job update. It refuses to run if `GOOGLE_APPLICATION_CREDENTIALS` is set.
- `deploy/cloud-run-service.yaml.template`
  - Cloud Run service YAML template with runtime service identity, resource limits, GCS config, Secret Manager references, and OpenAI `marin` defaults.
- `deploy/cloud-run-video-job.yaml.template`
  - Cloud Run job YAML template for future off-request video processing with the same image and secrets.
- `deploy/gcs-audio-lifecycle.json`
  - Audio retention template: NEARLINE after 7 days, delete generated audio after 30 days, abort incomplete multipart uploads after 1 day.
- `deploy/gcs-video-artifact-lifecycle.json`
  - Video lifecycle template: delete intermediate after 7 days, source after 14 days, rendered artifacts NEARLINE after 30 days and delete after 90 days.
- `deploy/secret-manager-map.md`
  - Required GitHub vars/secrets, Secret Manager mappings, and IAM roles.
- `deploy/release-smoke-checklist.md`
  - Health/readiness/voices/synthesis/storage/job/log/rollback smoke commands.
- `deploy/README.md`
  - Expanded operator commands, lifecycle application, signed URL and retention notes.
- `docs/deployment-runbook.md`
  - Adds production Cloud Run/GCS/Secret Manager/CI-CD runbook detail and rollback/smoke pointers.
- `docs/subagents/cloud-production-lifecycle-report-20260510.md`
  - This handoff.

## Official Sources Checked

- Cloud Run deploy command and service deployment: https://cloud.google.com/sdk/gcloud/reference/run/deploy and https://cloud.google.com/run/docs/deploying
- Cloud Run service env/secrets guidance: https://cloud.google.com/run/docs/configuring/services/environment-variables and https://cloud.google.com/run/docs/configuring/services/secrets
- Cloud Run job secrets guidance: https://cloud.google.com/run/docs/configuring/jobs/secrets
- Cloud Storage signed URLs: https://cloud.google.com/storage/docs/access-control/signed-urls
- Cloud Storage lifecycle management: https://cloud.google.com/storage/docs/lifecycle
- Artifact Registry Docker auth: https://cloud.google.com/artifact-registry/docs/docker/authentication
- GitHub Actions workflow triggers and `workflow_dispatch`: https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow
- GitHub OIDC for Google Cloud: https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-google-cloud-platform
- Google GitHub Actions Cloud Run deploy action: https://github.com/google-github-actions/deploy-cloudrun

Context7: not used. The implementation did not rely on Docker or GitHub Actions library API docs; it used official cloud and GitHub documentation plus local syntax validation.

## Commands Run

```bash
docker compose config --quiet
bash -n deploy/cloud-run-deploy-operator.sh
jq empty deploy/gcs-audio-lifecycle.json
jq empty deploy/gcs-video-artifact-lifecycle.json
python3 - <<'PY'
from pathlib import Path
import json
for path in Path('.github/workflows').glob('*.yml'):
    assert path.read_text(encoding='utf-8').strip()
for path in Path('deploy').glob('*.json'):
    json.loads(path.read_text(encoding='utf-8'))
PY
python3 - <<'PY'
from pathlib import Path
import yaml
for path in list(Path('.github/workflows').glob('*.yml')) + list(Path('deploy').glob('*.yaml.template')):
    yaml.safe_load(path.read_text(encoding='utf-8'))
    print(f'parsed {path}')
PY
PYTHONPATH=. .venv/bin/pytest -q
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
GCP_PROJECT_ID=voice-ai-prod REGION=us-central1 ENVIRONMENT=staging SERVICE_NAME=voice-ai ARTIFACT_REPOSITORY=voice-ai CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT=voice-ai-run@voice-ai-prod.iam.gserviceaccount.com GCS_AUDIO_BUCKET=voice-ai-prod-audio GCS_ARTIFACT_BUCKET=voice-ai-prod-artifacts API_KEYS_SECRET_NAME=voice-ai-api-keys OPENAI_API_KEY_SECRET_NAME=voice-ai-openai-api-key MLFLOW_TRACKING_URI=https://mlflow.example.com DRY_RUN=1 deploy/cloud-run-deploy-operator.sh
docker build -t voice-ai:cloud-production-lifecycle .
```

Results:

- Backend tests: `24 passed, 3 skipped`. The global `pytest` command was unavailable in this shell, and `.venv/bin/pytest` needed `PYTHONPATH=.` because the repo is not installed as a package in the venv.
- Frontend lint/test/build passed; Vitest reported `4 passed`.
- Docker build completed for `voice-ai:cloud-production-lifecycle`.
- `gcloud`, `shellcheck`, `yamllint`, and `yq` were not installed, so no live cloud validation or shellcheck/yamllint run was possible. The deploy script dry run rendered commands without executing cloud calls.

## Required GitHub Secrets And Variables

GitHub repository or environment secrets:

- `GCP_WORKLOAD_IDENTITY_PROVIDER`: Workload Identity Provider resource name.
- `GCP_DEPLOY_SERVICE_ACCOUNT`: deployment service account email.
- `API_KEYS_SECRET_NAME`: Secret Manager secret name for runtime API keys.
- `OPENAI_API_KEY_SECRET_NAME`: Secret Manager secret name for the OpenAI key.

GitHub repository or environment variables:

- `GCP_PROJECT_ID`
- `ARTIFACT_REGISTRY_REPOSITORY`
- `CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT`
- `GCS_AUDIO_BUCKET`
- `GCS_ARTIFACT_BUCKET`
- `CLOUD_TASKS_QUEUE`
- `CLOUD_TASKS_SERVICE_ACCOUNT`
- `MLFLOW_TRACKING_URI`
- `OPENAI_TTS_MODEL`
- `OPENAI_TTS_VOICE`
- `OPENAI_TTS_RESPONSE_FORMAT`

## Required IAM

Deployment identity:

- `roles/run.admin` on the project.
- `roles/artifactregistry.writer` on the Artifact Registry repo.
- `roles/iam.serviceAccountUser` on the Cloud Run runtime service account.

Runtime service account:

- `roles/secretmanager.secretAccessor` on `voice-ai-api-keys` and `voice-ai-openai-api-key`.
- `roles/storage.objectAdmin` or narrower object permissions on the configured audio and artifact buckets.
- No `GOOGLE_APPLICATION_CREDENTIALS` env var in Cloud Run; use runtime service identity.

Optional Cloud Tasks identity:

- `roles/run.invoker` on private task handlers.
- Cloud Tasks service agent permission to impersonate the task service account for OIDC dispatch.

## How This Moves Toward Production

- CI now proves backend tests, frontend checks/build, compose config, and container build before deploy.
- Deployment is concrete but credential-gated: GitHub OIDC, Artifact Registry, Cloud Run service, Cloud Run job, Secret Manager secret mappings, and GCS envs are represented.
- Operators have dry-run deploy commands, lifecycle policies, smoke checks, rollback commands, and IAM/secret inventory without committing live credentials.
- GCS lifecycle policies and signed URL notes create an explicit retention/access model for generated audio and video artifacts.

## Remaining Live-Deploy Blockers

- No live GCP credentials were available in this session, so there is no real Cloud Run revision, Artifact Registry image digest, GCS object, Secret Manager secret, or GitHub Actions run evidence.
- Current backend storage code still appears local-filesystem based; the new GCS envs/templates are production lifecycle artifacts, not proof that app code writes audio/video to GCS today.
- Video localization remains local/demo in current app code; the Cloud Run job artifact provides the deploy target, but the worker/job entrypoint still needs production implementation evidence before commercial release.
- Auth and billing remain MVP/demo. `API_KEYS` is documented as a stopgap, not final commercial auth.
- MLflow endpoint, alert policies, and Cloud Logging dashboards still need live environment configuration and evidence.

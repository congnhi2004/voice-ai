# Deployment Runbook

## Environments

- Local: FastAPI with local or Google provider, filesystem audio storage.
- CI: local fallback provider, no Google credentials required.
- Staging: Cloud Run, Google provider, MLflow enabled, limited API keys.
- Production: Cloud Run, Google provider, durable audio storage, API keys or stronger auth, alerts enabled.

## Required Configuration

Environment variables:

- `ENVIRONMENT`: `local`, `ci`, `staging`, or `production`.
- `PORT`: Cloud Run-provided port, default `8080`.
- `TTS_PROVIDER`: `google` or `local`.
- `GOOGLE_APPLICATION_CREDENTIALS`: local development credential path when not using service identity.
- `GCP_PROJECT_ID`: Google Cloud project id.
- `MLFLOW_TRACKING_URI`: MLflow tracking backend URI.
- `STORAGE_PROVIDER`: `local` for development or `gcs` to use Cloud Storage for both generated audio and video artifacts.
- `AUDIO_STORAGE_MODE`: optional per-surface override, normally matches `STORAGE_PROVIDER`.
- `AUDIO_STORAGE_DIR`: local audio directory, default `./data/audio`.
- `AUDIO_BASE_URL`: base URL for returned audio links.
- `VIDEO_STORAGE_MODE`: optional per-surface override, normally matches `STORAGE_PROVIDER`.
- `GCS_AUDIO_BUCKET`: private bucket for generated TTS audio when GCS storage is enabled.
- `GCS_ARTIFACT_BUCKET`: private bucket for source video, intermediate files, subtitles, voiceover audio, and rendered video when GCS storage is enabled.
- `GCS_AUDIO_PREFIX`, `GCS_SOURCE_VIDEO_PREFIX`, `GCS_INTERMEDIATE_PREFIX`, `GCS_RENDERED_VIDEO_PREFIX`: object prefixes for generated artifacts.
- `SIGNED_URL_TTL_SECONDS`: signed URL lifetime for download links, default `3600`.
- `API_KEYS`: comma-separated MVP API keys or secret-expanded value.
- `CORS_ALLOW_ORIGINS`: comma-separated allowed origins.
- `MAX_INPUT_CHARS`: default `5000`.
- `LOG_LEVEL`: default `INFO`.

Production should use Cloud Run service identity and Secret Manager rather than mounting service account JSON files.
For GCS storage, keep buckets private and grant the Cloud Run runtime service account object access only to the required buckets. Local tests mock the GCS client and should not require live credentials.

## Local Run

Assumed commands once implementation exists:

```bash
export TTS_PROVIDER=local
export AUDIO_STORAGE_DIR=./data/audio
export MLFLOW_TRACKING_URI=./mlruns
export API_KEYS=dev-key
uvicorn app.main:app --reload --port 8080
```

Smoke test:

```bash
curl http://localhost:8080/healthz
curl -H "Authorization: Bearer dev-key" http://localhost:8080/v1/voices
curl -X POST http://localhost:8080/v1/synthesize \
  -H "Authorization: Bearer dev-key" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello from Voice AI","voice":{"language_code":"en-US"},"audio":{"encoding":"MP3"}}'
```

## Cloud Run Deployment

Google's FastAPI quickstart shows a Python FastAPI app can be deployed from source with:

```bash
gcloud run deploy --source .
```

Recommended production deployment should be CI/CD-driven:

1. Run lint, type checks, unit tests, and API contract tests.
2. Build container image.
3. Push image to Artifact Registry.
4. Deploy to Cloud Run staging.
5. Run staging smoke tests.
6. Promote the same image digest to production.

Cloud Run is a managed platform for running code or containers on Google infrastructure. It provides HTTPS service endpoints and handles infrastructure/scaling operations. Cloud Run instances are disposable, so generated audio must use durable storage in production.

Concrete artifacts for this repo:

- `.github/workflows/ci.yml`: backend tests, frontend lint/test/build, compose config, Docker build, and video smoke hooks.
- `.github/workflows/deploy-cloud-run.yml`: manual Cloud Run deploy through GitHub OIDC, Artifact Registry, Secret Manager mappings, image-digest deploy, and post-deploy observe/smoke checks.
- `deploy/cloud-run-deploy-operator.sh`: dry-run-first operator deploy script.
- `deploy/cloud-run-service.yaml.template`: Cloud Run service review template. Production async video dispatch is Cloud Tasks HTTP target to the service, not Cloud Run Jobs.
- `deploy/gcs-audio-lifecycle.json` and `deploy/gcs-video-artifact-lifecycle.json`: lifecycle retention templates.
- `deploy/secret-manager-map.md`: required GitHub secrets, GitHub variables, Secret Manager secrets, and IAM.
- `deploy/release-smoke-checklist.md`: release smoke, storage, job, logs, and rollback commands.

Production Cloud Run must use Secret Manager for `OPENAI_API_KEY` and `API_KEYS`; do not put secret values in GitHub variables, workflow YAML, plain env vars, or committed files. Do not set `GOOGLE_APPLICATION_CREDENTIALS` on Cloud Run services or jobs; use the Cloud Run runtime service account.

Minimum manual dry run:

```bash
export GCP_PROJECT_ID=my-project
export REGION=us-central1
export ENVIRONMENT=staging
export SERVICE_NAME=voice-ai
export CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT=voice-ai-run@my-project.iam.gserviceaccount.com
export STORAGE_PROVIDER=gcs
export GCS_AUDIO_BUCKET=my-voice-ai-audio
export GCS_ARTIFACT_BUCKET=my-voice-ai-artifacts
export API_KEYS_SECRET_NAME=voice-ai-api-keys
export OPENAI_API_KEY_SECRET_NAME=voice-ai-openai-api-key
export MLFLOW_TRACKING_URI=https://mlflow.example.com
deploy/cloud-run-deploy-operator.sh
```

Execute only after credentials and IAM are configured:

```bash
DRY_RUN=0 deploy/cloud-run-deploy-operator.sh
```

Apply bucket lifecycle policies:

```bash
gcloud storage buckets update "gs://${GCS_AUDIO_BUCKET}" \
  --lifecycle-file=deploy/gcs-audio-lifecycle.json
gcloud storage buckets update "gs://${GCS_ARTIFACT_BUCKET}" \
  --lifecycle-file=deploy/gcs-video-artifact-lifecycle.json
```

Signed URL policy:

- Buckets remain private.
- App/API authorizes the user first, then returns a time-limited signed URL for a specific object.
- Default TTL is `SIGNED_URL_TTL_SECONDS=3600`.
- Full signed URLs should not be written to application logs or MLflow parameters.

## Staging Verification

- `/healthz` returns `200`.
- `/readyz` returns `200` with Google provider ready.
- `/v1/voices` returns at least one Google voice.
- `/v1/synthesize` returns playable audio URL.
- MLflow has a run with matching `job_id`.
- Logs include request id and job id.

## Rollback

- Prefer Cloud Run revision rollback to the last known good revision.
- Keep production deployments pinned to image digests.
- Roll back config separately when a secret or environment change caused the incident.
- Capture failed revision, logs, MLflow run ids, and provider error codes in the incident record.

## Operational Risks

- Missing Google credentials: staging/prod readiness must fail before serving synthesis traffic.
- Provider quota exceeded: rate-limit clients and alert on quota errors.
- Disposable filesystem: local file paths are acceptable only outside production.
- MLflow outage: synthesis may continue, but alert and record logging failures.

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
- `AUDIO_STORAGE_DIR`: local audio directory, default `./data/audio`.
- `AUDIO_BASE_URL`: base URL for returned audio links.
- `API_KEYS`: comma-separated MVP API keys or secret-expanded value.
- `CORS_ALLOW_ORIGINS`: comma-separated allowed origins.
- `MAX_INPUT_CHARS`: default `5000`.
- `LOG_LEVEL`: default `INFO`.

Production should use Cloud Run service identity and Secret Manager rather than mounting service account JSON files.

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


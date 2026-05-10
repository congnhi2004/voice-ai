# Release Smoke Checklist

Run this after a manual workflow dispatch or operator deploy. Replace placeholders before use.

## Service

```bash
export PROJECT_ID=voice-ai-prod
export REGION=us-central1
export SERVICE_NAME=voice-ai
export API_KEY_REF=redacted-local-test-key

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format='value(status.url)')"

curl -fsS "${SERVICE_URL}/healthz"
curl -fsS "${SERVICE_URL}/readyz"
curl -fsS -H "Authorization: Bearer ${API_KEY_REF}" "${SERVICE_URL}/v1/voices?language_code=vi-VN"
curl -fsS -X POST "${SERVICE_URL}/v1/synthesize" \
  -H "Authorization: Bearer ${API_KEY_REF}" \
  -H "Content-Type: application/json" \
  -d '{"text":"Xin chao, day la smoke test Cloud Run OpenAI marin.","voice":{"language_code":"vi-VN","name":"marin"},"audio":{"encoding":"LINEAR16"},"metadata":{"client_reference_id":"cloud-run-smoke"}}'
```

Expected:

- `/healthz` returns HTTP 200.
- `/readyz` reports provider `openai`, storage ready, and MLflow status known.
- `/v1/voices` includes `marin`.
- Synthesis returns provider `openai`, `fallback=false`, a downloadable audio URL, and no secret values.

## Storage

```bash
gcloud storage ls "gs://${GCS_AUDIO_BUCKET}/voice-ai/audio/" --project="${PROJECT_ID}" --limit=5
gcloud storage ls "gs://${GCS_ARTIFACT_BUCKET}/voice-ai/video/" --project="${PROJECT_ID}" --recursive --limit=10
```

Expected:

- Audio objects are created only after a successful GCS-backed release. Current app code may still write local filesystem artifacts; that is a live-deploy blocker if no object appears.
- Video source/rendered/intermediate prefixes exist before commercial video release.

## Job

```bash
gcloud run jobs describe voice-ai-video-localization \
  --project="${PROJECT_ID}" \
  --region="${REGION}"
```

Expected:

- Job exists and uses the same image tag or digest as the service.
- Job has no `GOOGLE_APPLICATION_CREDENTIALS` env var.
- Secrets are mounted through Secret Manager references.

## Logs And Rollback

```bash
gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format='value(status.latestReadyRevisionName,status.traffic)'

gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --limit=50 \
  --format='table(timestamp,severity,textPayload)'

gcloud run services update-traffic "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --to-revisions LAST_KNOWN_GOOD_REVISION=100
```

Rollback should use the previous known-good revision or redeploy the previous image digest. Record the failed revision, image digest, API response, log query, and MLflow run id in the incident note.

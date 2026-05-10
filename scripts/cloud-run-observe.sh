#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${REGION:=us-central1}"
: "${SERVICE_NAME:=voice-ai}"
: "${CLOUD_TASKS_QUEUE:=voice-ai-video}"
: "${GCS_AUDIO_BUCKET:?Set GCS_AUDIO_BUCKET}"
: "${GCS_ARTIFACT_BUCKET:?Set GCS_ARTIFACT_BUCKET}"
: "${LOG_LIMIT:=50}"
: "${DRY_RUN:=0}"

run_cmd() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
  if [[ "${DRY_RUN}" == "0" ]]; then
    "$@"
  fi
}

run_capture() {
  if [[ "${DRY_RUN}" == "0" ]]; then
    "$@"
  else
    printf 'DRY_RUN_VALUE'
  fi
}

run_optional_cmd() {
  printf '+'
  printf ' %q' "$@"
  printf ' || true\n'
  if [[ "${DRY_RUN}" == "0" ]]; then
    "$@" || true
  fi
}

echo "Cloud Run service metadata:"
run_cmd gcloud run services describe "${SERVICE_NAME}" \
  --project="${GCP_PROJECT_ID}" \
  --region="${REGION}" \
  --format='table(metadata.name,status.url,status.latestReadyRevisionName,status.traffic[].percent,status.traffic[].revisionName)'

echo
echo "Cloud Run revision and traffic:"
run_cmd gcloud run revisions list \
  --project="${GCP_PROJECT_ID}" \
  --region="${REGION}" \
  --service="${SERVICE_NAME}" \
  --limit=10 \
  --format='table(metadata.name,status.conditions[0].status,status.conditions[0].type,status.imageDigest,metadata.creationTimestamp)'

echo
echo "Runtime env/secrets inventory (values redacted by field selection):"
run_cmd gcloud run services describe "${SERVICE_NAME}" \
  --project="${GCP_PROJECT_ID}" \
  --region="${REGION}" \
  --format='json(spec.template.spec.serviceAccountName,spec.template.spec.containers[0].image,spec.template.spec.containers[0].env[].name,spec.template.spec.containers[0].env[].valueFrom.secretKeyRef.name)'

SERVICE_URL="${SERVICE_URL:-$(run_capture gcloud run services describe "${SERVICE_NAME}" --project="${GCP_PROJECT_ID}" --region="${REGION}" --format='value(status.url)')}"

echo
echo "Health checks:"
run_cmd curl -fsS "${SERVICE_URL}/healthz"
run_cmd curl -fsS "${SERVICE_URL}/readyz"

if [[ -n "${RELEASE_SMOKE_API_KEY:-}" ]]; then
  echo
  echo "Authenticated voice smoke:"
  echo "+ curl -fsS -H 'Authorization: Bearer [REDACTED]' '${SERVICE_URL}/v1/voices?language_code=vi-VN'"
  if [[ "${DRY_RUN}" == "0" ]]; then
    curl -fsS -H "Authorization: Bearer ${RELEASE_SMOKE_API_KEY}" "${SERVICE_URL}/v1/voices?language_code=vi-VN"
  fi
else
  echo
  echo "Authenticated voice smoke skipped: RELEASE_SMOKE_API_KEY is unset."
fi

echo
echo "GCS lifecycle and object inventory:"
run_cmd gcloud storage buckets describe "gs://${GCS_AUDIO_BUCKET}" \
  --project="${GCP_PROJECT_ID}" \
  --format='json(name,iamConfiguration.uniformBucketLevelAccess,iamConfiguration.publicAccessPrevention,lifecycle)'
run_cmd gcloud storage buckets describe "gs://${GCS_ARTIFACT_BUCKET}" \
  --project="${GCP_PROJECT_ID}" \
  --format='json(name,iamConfiguration.uniformBucketLevelAccess,iamConfiguration.publicAccessPrevention,lifecycle)'
run_optional_cmd gcloud storage ls "gs://${GCS_AUDIO_BUCKET}/${GCS_AUDIO_PREFIX:-voice-ai/audio}/" \
  --project="${GCP_PROJECT_ID}" \
  --limit=5
run_optional_cmd gcloud storage ls "gs://${GCS_ARTIFACT_BUCKET}/${GCS_RENDERED_VIDEO_PREFIX:-voice-ai/video/rendered}/" \
  --project="${GCP_PROJECT_ID}" \
  --limit=5

echo
echo "Signed URL GET smoke:"
if [[ -n "${SIGNED_URL_TO_TEST:-}" ]]; then
  echo "+ curl -fsSI [SIGNED_URL_REDACTED]"
  if [[ "${DRY_RUN}" == "0" ]]; then
    curl -fsSI -o /dev/null -w 'signed_url_http_code=%{http_code}\n' "${SIGNED_URL_TO_TEST}"
  fi
elif [[ -n "${SIGNED_URL_GCS_URI:-}" ]]; then
  echo "+ gcloud storage sign-url ${SIGNED_URL_GCS_URI} --duration=10m --impersonate-service-account=[RUNTIME_SERVICE_ACCOUNT] # do not print the generated URL in shared logs"
  echo "Set SIGNED_URL_TO_TEST to the generated URL and re-run this script to capture only the HTTP code."
else
  echo "Skipped: set SIGNED_URL_TO_TEST to test an app-generated signed URL without printing it."
fi

echo
echo "Cloud Tasks queue status:"
run_cmd gcloud tasks queues describe "${CLOUD_TASKS_QUEUE}" \
  --project="${GCP_PROJECT_ID}" \
  --location="${REGION}" \
  --format='yaml(name,state,rateLimits,retryConfig,stats)'

echo
echo "Cloud Logging query:"
run_cmd gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}" \
  --project="${GCP_PROJECT_ID}" \
  --limit="${LOG_LIMIT}" \
  --format='table(timestamp,severity,resource.labels.revision_name,textPayload,jsonPayload.message,jsonPayload.request_id,jsonPayload.job_id,jsonPayload.error_code)'

echo
cat <<EOF
Cloud Monitoring checks to capture before production approval:
- run.googleapis.com/request_count grouped by response_code_class for service_name=${SERVICE_NAME}
- run.googleapis.com/request_latencies filtered to service_name=${SERVICE_NAME}
- logging.googleapis.com/log_entry_count filtered by severity>=ERROR and service_name=${SERVICE_NAME}
- cloudtasks.googleapis.com/queue/task_attempt_count filtered to queue_id=${CLOUD_TASKS_QUEUE}
- cloudtasks.googleapis.com/queue/depth and oldest task age if the queue has pending work

MLflow stance:
- MLFLOW_TRACKING_URI must point to an internal endpoint or private network path.
- Smoke evidence should record run ids and metadata only; do not log raw transcripts, source media, full signed URLs, or API keys.
EOF

#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${REGION:=us-central1}"
: "${SERVICE_NAME:=voice-ai}"
: "${LOG_LIMIT:=50}"

echo "Service:"
gcloud run services describe "${SERVICE_NAME}" \
  --project="${GCP_PROJECT_ID}" \
  --region="${REGION}" \
  --format='table(metadata.name,status.url,status.latestReadyRevisionName,status.traffic[].percent,status.traffic[].revisionName)'

echo
echo "Recent revisions:"
gcloud run revisions list \
  --project="${GCP_PROJECT_ID}" \
  --region="${REGION}" \
  --service="${SERVICE_NAME}" \
  --limit=10

echo
echo "Recent logs:"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}" \
  --project="${GCP_PROJECT_ID}" \
  --limit="${LOG_LIMIT}" \
  --format='table(timestamp,severity,resource.labels.revision_name,textPayload,jsonPayload.message)'

echo
cat <<EOF
Metric filters for Cloud Monitoring:
- run.googleapis.com/request_count grouped by response_code_class
- run.googleapis.com/request_latencies filtered to service_name=${SERVICE_NAME}
- logging.googleapis.com/log_entry_count filtered by severity>=ERROR
- cloudtasks.googleapis.com/queue/task_attempt_count filtered to queue_id=${CLOUD_TASKS_QUEUE:-voice-ai-video}

Suggested smoke checks:
SERVICE_URL=\$(gcloud run services describe ${SERVICE_NAME} --project ${GCP_PROJECT_ID} --region ${REGION} --format='value(status.url)')
curl -fsS "\${SERVICE_URL}/healthz"
curl -fsS "\${SERVICE_URL}/readyz"

Expected structured video-stage log fields:
- job_id, request_id, video_job_id, stage, stage_status, duration_ms, input_uri, output_uri, error_code
EOF

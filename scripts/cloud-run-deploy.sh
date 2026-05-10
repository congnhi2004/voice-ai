#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${REGION:=us-central1}"
: "${SERVICE_NAME:=voice-ai}"
: "${ARTIFACT_REPOSITORY:=voice-ai}"
: "${IMAGE_TAG:=$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
: "${CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT:?Set CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT}"
: "${GCS_AUDIO_BUCKET:?Set GCS_AUDIO_BUCKET}"
: "${GCS_ARTIFACT_BUCKET:?Set GCS_ARTIFACT_BUCKET}"
: "${MLFLOW_TRACKING_URI:?Set MLFLOW_TRACKING_URI}"
: "${CLOUD_TASKS_QUEUE:=voice-ai-video}"

IMAGE_URI="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REPOSITORY}/${SERVICE_NAME}:${IMAGE_TAG}"

echo "Using image ${IMAGE_URI}"
gcloud config set project "${GCP_PROJECT_ID}" >/dev/null
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

if ! gcloud artifacts repositories describe "${ARTIFACT_REPOSITORY}" --location "${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${ARTIFACT_REPOSITORY}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Voice AI containers"
fi

docker build -t "${IMAGE_URI}" .
docker push "${IMAGE_URI}"

gcloud run deploy "${SERVICE_NAME}" \
  --project="${GCP_PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --service-account="${CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT}" \
  --memory="${CLOUD_RUN_MEMORY:-4Gi}" \
  --cpu="${CLOUD_RUN_CPU:-2}" \
  --min-instances=0 \
  --max-instances=10 \
  --concurrency="${CLOUD_RUN_CONCURRENCY:-1}" \
  --timeout="${REQUEST_TIMEOUT_SECONDS:-3600}" \
  --set-env-vars="ENVIRONMENT=${ENVIRONMENT:-staging},SERVICE_VERSION=${IMAGE_TAG},TTS_PROVIDER=google,GCP_PROJECT_ID=${GCP_PROJECT_ID},GOOGLE_CLOUD_REGION=${REGION},AUDIO_STORAGE_MODE=gcs,GCS_AUDIO_BUCKET=${GCS_AUDIO_BUCKET},GCS_AUDIO_PREFIX=${GCS_AUDIO_PREFIX:-voice-ai/audio},VIDEO_LOCALIZATION_ENABLED=true,VIDEO_STORAGE_MODE=gcs,GCS_ARTIFACT_BUCKET=${GCS_ARTIFACT_BUCKET},GCS_SOURCE_VIDEO_PREFIX=${GCS_SOURCE_VIDEO_PREFIX:-voice-ai/video/source},GCS_RENDERED_VIDEO_PREFIX=${GCS_RENDERED_VIDEO_PREFIX:-voice-ai/video/rendered},GCS_INTERMEDIATE_PREFIX=${GCS_INTERMEDIATE_PREFIX:-voice-ai/video/intermediate},JOB_DISPATCH_MODE=${JOB_DISPATCH_MODE:-cloud_tasks},CLOUD_TASKS_QUEUE=${CLOUD_TASKS_QUEUE},CLOUD_TASKS_LOCATION=${REGION},CLOUD_TASKS_HANDLER_PATH=${CLOUD_TASKS_HANDLER_PATH:-/internal/tasks/video-localization},CLOUD_TASKS_SERVICE_ACCOUNT=${CLOUD_TASKS_SERVICE_ACCOUNT:-${CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT}},MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI},MLFLOW_EXPERIMENT_NAME=${MLFLOW_EXPERIMENT_NAME:-voice-ai-tts-synthesis},MLFLOW_VIDEO_EXPERIMENT_NAME=${MLFLOW_VIDEO_EXPERIMENT_NAME:-voice-ai-video-localization},VIDEO_OBSERVABILITY_STAGES=${VIDEO_OBSERVABILITY_STAGES:-upload,stt,translation,tts,alignment,render,delivery},LOG_LEVEL=${LOG_LEVEL:-INFO},STRUCTURED_LOGS=true,MAX_INPUT_CHARS=${MAX_INPUT_CHARS:-5000},MAX_UPLOAD_BYTES=${MAX_UPLOAD_BYTES:-524288000},REQUEST_TIMEOUT_SECONDS=${REQUEST_TIMEOUT_SECONDS:-3600},VIDEO_STAGE_TIMEOUT_SECONDS=${VIDEO_STAGE_TIMEOUT_SECONDS:-3300},FFMPEG_THREADS=${FFMPEG_THREADS:-2}" \
  ${ALLOW_UNAUTHENTICATED:+--allow-unauthenticated}

gcloud run services describe "${SERVICE_NAME}" \
  --project="${GCP_PROJECT_ID}" \
  --region="${REGION}" \
  --format='value(status.url)'

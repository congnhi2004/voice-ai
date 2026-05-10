#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${REGION:=us-central1}"
: "${ENVIRONMENT:=staging}"
: "${SERVICE_NAME:=voice-ai}"
: "${ARTIFACT_REPOSITORY:=voice-ai}"
: "${IMAGE_TAG:=$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
: "${CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT:?Set CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT}"
: "${CLOUD_TASKS_SERVICE_ACCOUNT:?Set CLOUD_TASKS_SERVICE_ACCOUNT}"
: "${GCS_AUDIO_BUCKET:?Set GCS_AUDIO_BUCKET}"
: "${GCS_ARTIFACT_BUCKET:?Set GCS_ARTIFACT_BUCKET}"
: "${API_KEYS_SECRET_NAME:?Set API_KEYS_SECRET_NAME}"
: "${OPENAI_API_KEY_SECRET_NAME:?Set OPENAI_API_KEY_SECRET_NAME}"
: "${MLFLOW_TRACKING_URI:?Set MLFLOW_TRACKING_URI}"
: "${CLOUD_TASKS_QUEUE:=voice-ai-video}"
: "${CLOUD_TASKS_HANDLER_PATH:=/internal/tasks/video-localization}"
: "${DRY_RUN:=1}"

IMAGE_URI="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REPOSITORY}/${SERVICE_NAME}:${IMAGE_TAG}"

run_cmd() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
  if [[ "${DRY_RUN}" == "0" ]]; then
    "$@"
  fi
}

if [[ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" && "${DRY_RUN}" == "0" ]]; then
  echo "Refusing deploy: unset GOOGLE_APPLICATION_CREDENTIALS for Cloud Run service deploys; use service identity or GitHub OIDC." >&2
  exit 1
elif [[ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
  echo "# Warning: GOOGLE_APPLICATION_CREDENTIALS is set; live Cloud Run deploys should use service identity or GitHub OIDC." >&2
fi

run_cmd gcloud config set project "${GCP_PROJECT_ID}"
run_cmd gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
if [[ "${DRY_RUN}" == "0" ]]; then
  if ! gcloud artifacts repositories describe "${ARTIFACT_REPOSITORY}" --location "${REGION}" >/dev/null 2>&1; then
    run_cmd gcloud artifacts repositories create "${ARTIFACT_REPOSITORY}" \
      --repository-format=docker \
      --location="${REGION}" \
      --description="Voice AI containers"
  fi
else
  run_cmd gcloud artifacts repositories describe "${ARTIFACT_REPOSITORY}" --location "${REGION}"
  run_cmd gcloud artifacts repositories create "${ARTIFACT_REPOSITORY}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Voice AI containers"
fi
run_cmd docker build -t "${IMAGE_URI}" .
run_cmd docker push "${IMAGE_URI}"

run_cmd gcloud run deploy "${SERVICE_NAME}" \
  --project="${GCP_PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --service-account="${CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT}" \
  --memory="${CLOUD_RUN_MEMORY:-4Gi}" \
  --cpu="${CLOUD_RUN_CPU:-2}" \
  --min-instances="${CLOUD_RUN_MIN_INSTANCES:-0}" \
  --max-instances="${CLOUD_RUN_MAX_INSTANCES:-10}" \
  --concurrency="${CLOUD_RUN_CONCURRENCY:-1}" \
  --timeout="${REQUEST_TIMEOUT_SECONDS:-3600}" \
  --set-env-vars="ENVIRONMENT=${ENVIRONMENT},SERVICE_VERSION=${IMAGE_TAG},TTS_PROVIDER=openai,OPENAI_TTS_MODEL=${OPENAI_TTS_MODEL:-gpt-4o-mini-tts},OPENAI_TTS_VOICE=${OPENAI_TTS_VOICE:-marin},OPENAI_TTS_RESPONSE_FORMAT=${OPENAI_TTS_RESPONSE_FORMAT:-wav},GCP_PROJECT_ID=${GCP_PROJECT_ID},GOOGLE_CLOUD_REGION=${REGION},STORAGE_PROVIDER=gcs,AUDIO_STORAGE_MODE=gcs,GCS_AUDIO_BUCKET=${GCS_AUDIO_BUCKET},GCS_AUDIO_PREFIX=${GCS_AUDIO_PREFIX:-voice-ai/audio},SIGNED_URL_TTL_SECONDS=${SIGNED_URL_TTL_SECONDS:-3600},VIDEO_LOCALIZATION_ENABLED=true,VIDEO_STORAGE_MODE=gcs,GCS_ARTIFACT_BUCKET=${GCS_ARTIFACT_BUCKET},GCS_SOURCE_VIDEO_PREFIX=${GCS_SOURCE_VIDEO_PREFIX:-voice-ai/video/source},GCS_RENDERED_VIDEO_PREFIX=${GCS_RENDERED_VIDEO_PREFIX:-voice-ai/video/rendered},GCS_INTERMEDIATE_PREFIX=${GCS_INTERMEDIATE_PREFIX:-voice-ai/video/intermediate},JOB_DISPATCH_MODE=cloud_tasks,CLOUD_TASKS_QUEUE=${CLOUD_TASKS_QUEUE},CLOUD_TASKS_LOCATION=${REGION},CLOUD_TASKS_HANDLER_PATH=${CLOUD_TASKS_HANDLER_PATH},CLOUD_TASKS_SERVICE_ACCOUNT=${CLOUD_TASKS_SERVICE_ACCOUNT},MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI},MLFLOW_EXPERIMENT_NAME=${MLFLOW_EXPERIMENT_NAME:-voice-ai-tts-synthesis},MLFLOW_VIDEO_EXPERIMENT_NAME=${MLFLOW_VIDEO_EXPERIMENT_NAME:-voice-ai-video-localization},VIDEO_OBSERVABILITY_STAGES=${VIDEO_OBSERVABILITY_STAGES:-upload,stt,translation,tts,alignment,render,delivery},LOG_LEVEL=${LOG_LEVEL:-INFO},STRUCTURED_LOGS=true,MAX_INPUT_CHARS=${MAX_INPUT_CHARS:-5000},MAX_UPLOAD_BYTES=${MAX_UPLOAD_BYTES:-524288000},REQUEST_TIMEOUT_SECONDS=${REQUEST_TIMEOUT_SECONDS:-3600},VIDEO_STAGE_TIMEOUT_SECONDS=${VIDEO_STAGE_TIMEOUT_SECONDS:-3300},FFMPEG_THREADS=${FFMPEG_THREADS:-2}" \
  --set-secrets="API_KEYS=${API_KEYS_SECRET_NAME}:latest,OPENAI_API_KEY=${OPENAI_API_KEY_SECRET_NAME}:latest" \
  ${ALLOW_UNAUTHENTICATED:+--allow-unauthenticated}

run_cmd gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
  --project="${GCP_PROJECT_ID}" \
  --region="${REGION}" \
  --member="serviceAccount:${CLOUD_TASKS_SERVICE_ACCOUNT}" \
  --role="roles/run.invoker"

run_cmd gcloud tasks queues describe "${CLOUD_TASKS_QUEUE}" \
  --project="${GCP_PROJECT_ID}" \
  --location="${REGION}" \
  --format="table(name,state,rateLimits.maxDispatchesPerSecond,rateLimits.maxConcurrentDispatches,retryConfig.maxAttempts)"

run_cmd gcloud run services describe "${SERVICE_NAME}" \
  --project="${GCP_PROJECT_ID}" \
  --region="${REGION}" \
  --format="value(status.url,status.latestReadyRevisionName)"

echo "Dry run complete for ${IMAGE_URI}. Re-run with DRY_RUN=0 after credentials/IAM are configured."

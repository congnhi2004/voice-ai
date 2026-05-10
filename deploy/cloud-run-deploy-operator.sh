#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${REGION:=us-central1}"
: "${ENVIRONMENT:=staging}"
: "${SERVICE_NAME:=voice-ai}"
: "${VIDEO_JOB_NAME:=voice-ai-video-localization}"
: "${ARTIFACT_REPOSITORY:=voice-ai}"
: "${IMAGE_TAG:=$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
: "${CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT:?Set CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT}"
: "${GCS_AUDIO_BUCKET:?Set GCS_AUDIO_BUCKET}"
: "${GCS_ARTIFACT_BUCKET:?Set GCS_ARTIFACT_BUCKET}"
: "${API_KEYS_SECRET_NAME:?Set API_KEYS_SECRET_NAME}"
: "${OPENAI_API_KEY_SECRET_NAME:?Set OPENAI_API_KEY_SECRET_NAME}"
: "${MLFLOW_TRACKING_URI:?Set MLFLOW_TRACKING_URI}"
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

if [[ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
  echo "Refusing deploy: unset GOOGLE_APPLICATION_CREDENTIALS for Cloud Run service/job deploys; use service identity or GitHub OIDC." >&2
  exit 1
fi

run_cmd gcloud config set project "${GCP_PROJECT_ID}"
run_cmd gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
run_cmd gcloud artifacts repositories describe "${ARTIFACT_REPOSITORY}" --location "${REGION}"
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
  --set-env-vars="ENVIRONMENT=${ENVIRONMENT},SERVICE_VERSION=${IMAGE_TAG},TTS_PROVIDER=openai,OPENAI_TTS_MODEL=${OPENAI_TTS_MODEL:-gpt-4o-mini-tts},OPENAI_TTS_VOICE=${OPENAI_TTS_VOICE:-marin},OPENAI_TTS_RESPONSE_FORMAT=${OPENAI_TTS_RESPONSE_FORMAT:-wav},GCP_PROJECT_ID=${GCP_PROJECT_ID},GOOGLE_CLOUD_REGION=${REGION},AUDIO_STORAGE_MODE=gcs,GCS_AUDIO_BUCKET=${GCS_AUDIO_BUCKET},GCS_AUDIO_PREFIX=${GCS_AUDIO_PREFIX:-voice-ai/audio},SIGNED_URL_TTL_SECONDS=${SIGNED_URL_TTL_SECONDS:-3600},VIDEO_LOCALIZATION_ENABLED=true,VIDEO_STORAGE_MODE=gcs,GCS_ARTIFACT_BUCKET=${GCS_ARTIFACT_BUCKET},GCS_SOURCE_VIDEO_PREFIX=${GCS_SOURCE_VIDEO_PREFIX:-voice-ai/video/source},GCS_RENDERED_VIDEO_PREFIX=${GCS_RENDERED_VIDEO_PREFIX:-voice-ai/video/rendered},GCS_INTERMEDIATE_PREFIX=${GCS_INTERMEDIATE_PREFIX:-voice-ai/video/intermediate},JOB_DISPATCH_MODE=${JOB_DISPATCH_MODE:-cloud_run_job},MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI},MLFLOW_EXPERIMENT_NAME=${MLFLOW_EXPERIMENT_NAME:-voice-ai-tts-synthesis},MLFLOW_VIDEO_EXPERIMENT_NAME=${MLFLOW_VIDEO_EXPERIMENT_NAME:-voice-ai-video-localization},LOG_LEVEL=${LOG_LEVEL:-INFO},STRUCTURED_LOGS=true,MAX_INPUT_CHARS=${MAX_INPUT_CHARS:-5000},MAX_UPLOAD_BYTES=${MAX_UPLOAD_BYTES:-524288000},REQUEST_TIMEOUT_SECONDS=${REQUEST_TIMEOUT_SECONDS:-3600},VIDEO_STAGE_TIMEOUT_SECONDS=${VIDEO_STAGE_TIMEOUT_SECONDS:-3300},FFMPEG_THREADS=${FFMPEG_THREADS:-2}" \
  --set-secrets="API_KEYS=${API_KEYS_SECRET_NAME}:latest,OPENAI_API_KEY=${OPENAI_API_KEY_SECRET_NAME}:latest" \
  ${ALLOW_UNAUTHENTICATED:+--allow-unauthenticated}

job_action=update
if [[ "${DRY_RUN}" == "0" ]]; then
  if ! gcloud run jobs describe "${VIDEO_JOB_NAME}" --project="${GCP_PROJECT_ID}" --region="${REGION}" >/dev/null 2>&1; then
    job_action=create
  fi
else
  echo "# Dry run assumes '${VIDEO_JOB_NAME}' may already exist. Use create instead of update for first deployment."
fi

run_cmd gcloud run jobs "${job_action}" "${VIDEO_JOB_NAME}" \
  --project="${GCP_PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --service-account="${CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT}" \
  --memory="${CLOUD_RUN_JOB_MEMORY:-4Gi}" \
  --cpu="${CLOUD_RUN_JOB_CPU:-2}" \
  --tasks=1 \
  --parallelism=1 \
  --task-timeout="${VIDEO_STAGE_TIMEOUT_SECONDS:-3600}" \
  --set-env-vars="ENVIRONMENT=${ENVIRONMENT},SERVICE_VERSION=${IMAGE_TAG},TTS_PROVIDER=openai,OPENAI_TTS_MODEL=${OPENAI_TTS_MODEL:-gpt-4o-mini-tts},OPENAI_TTS_VOICE=${OPENAI_TTS_VOICE:-marin},OPENAI_TTS_RESPONSE_FORMAT=${OPENAI_TTS_RESPONSE_FORMAT:-wav},GCP_PROJECT_ID=${GCP_PROJECT_ID},GOOGLE_CLOUD_REGION=${REGION},AUDIO_STORAGE_MODE=gcs,GCS_AUDIO_BUCKET=${GCS_AUDIO_BUCKET},VIDEO_LOCALIZATION_ENABLED=true,VIDEO_STORAGE_MODE=gcs,GCS_ARTIFACT_BUCKET=${GCS_ARTIFACT_BUCKET},JOB_DISPATCH_MODE=cloud_run_job,MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI},LOG_LEVEL=${LOG_LEVEL:-INFO},STRUCTURED_LOGS=true,FFMPEG_THREADS=${FFMPEG_THREADS:-2}" \
  --set-secrets="API_KEYS=${API_KEYS_SECRET_NAME}:latest,OPENAI_API_KEY=${OPENAI_API_KEY_SECRET_NAME}:latest"

echo "Dry run complete for ${IMAGE_URI}. Re-run with DRY_RUN=0 after credentials/IAM are configured."

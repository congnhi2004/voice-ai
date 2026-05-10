#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${REGION:=us-central1}"
: "${ARTIFACT_REPOSITORY:=voice-ai}"
: "${DEPLOY_SERVICE_ACCOUNT:=voice-ai-deploy@${GCP_PROJECT_ID}.iam.gserviceaccount.com}"
: "${RUNTIME_SERVICE_ACCOUNT:=voice-ai-run@${GCP_PROJECT_ID}.iam.gserviceaccount.com}"
: "${TASKS_SERVICE_ACCOUNT:=voice-ai-tasks@${GCP_PROJECT_ID}.iam.gserviceaccount.com}"
: "${GCS_AUDIO_BUCKET:?Set GCS_AUDIO_BUCKET}"
: "${GCS_ARTIFACT_BUCKET:?Set GCS_ARTIFACT_BUCKET}"
: "${CLOUD_TASKS_QUEUE:=voice-ai-video}"

PROJECT_NUMBER="$(gcloud projects describe "${GCP_PROJECT_ID}" --format='value(projectNumber)')"

gcloud config set project "${GCP_PROJECT_ID}" >/dev/null

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  secretmanager.googleapis.com \
  texttospeech.googleapis.com \
  cloudtasks.googleapis.com \
  storage.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com

for sa in "${DEPLOY_SERVICE_ACCOUNT}" "${RUNTIME_SERVICE_ACCOUNT}" "${TASKS_SERVICE_ACCOUNT}"; do
  if ! gcloud iam service-accounts describe "${sa}" >/dev/null 2>&1; then
    name="${sa%@*}"
    gcloud iam service-accounts create "${name}" --display-name="${name}"
  fi
done

if ! gcloud artifacts repositories describe "${ARTIFACT_REPOSITORY}" --location "${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${ARTIFACT_REPOSITORY}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Voice AI containers"
fi

gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
  --member="serviceAccount:${DEPLOY_SERVICE_ACCOUNT}" \
  --role="roles/run.admin"
gcloud artifacts repositories add-iam-policy-binding "${ARTIFACT_REPOSITORY}" \
  --location="${REGION}" \
  --member="serviceAccount:${DEPLOY_SERVICE_ACCOUNT}" \
  --role="roles/artifactregistry.writer"
gcloud iam service-accounts add-iam-policy-binding "${RUNTIME_SERVICE_ACCOUNT}" \
  --member="serviceAccount:${DEPLOY_SERVICE_ACCOUNT}" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SERVICE_ACCOUNT}" \
  --role="roles/cloudtexttospeech.user"
gcloud storage buckets add-iam-policy-binding "gs://${GCS_AUDIO_BUCKET}" \
  --member="serviceAccount:${RUNTIME_SERVICE_ACCOUNT}" \
  --role="roles/storage.objectAdmin"
gcloud storage buckets add-iam-policy-binding "gs://${GCS_ARTIFACT_BUCKET}" \
  --member="serviceAccount:${RUNTIME_SERVICE_ACCOUNT}" \
  --role="roles/storage.objectAdmin"

if ! gcloud tasks queues describe "${CLOUD_TASKS_QUEUE}" --location="${REGION}" >/dev/null 2>&1; then
  gcloud tasks queues create "${CLOUD_TASKS_QUEUE}" \
    --location="${REGION}" \
    --max-dispatches-per-second=2 \
    --max-concurrent-dispatches=1 \
    --max-attempts=3 \
    --min-backoff=30s \
    --max-backoff=600s
fi

gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SERVICE_ACCOUNT}" \
  --role="roles/cloudtasks.enqueuer"
gcloud iam service-accounts add-iam-policy-binding "${TASKS_SERVICE_ACCOUNT}" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-cloudtasks.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

cat <<EOF
Project number: ${PROJECT_NUMBER}
Deploy service account: ${DEPLOY_SERVICE_ACCOUNT}
Runtime service account: ${RUNTIME_SERVICE_ACCOUNT}

Configure GitHub Workload Identity Federation separately, then set repository variables/secrets:
- vars.GCP_PROJECT_ID=${GCP_PROJECT_ID}
- vars.ARTIFACT_REGISTRY_REPOSITORY=${ARTIFACT_REPOSITORY}
- vars.CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT=${RUNTIME_SERVICE_ACCOUNT}
- vars.GCS_AUDIO_BUCKET=${GCS_AUDIO_BUCKET}
- vars.GCS_ARTIFACT_BUCKET=${GCS_ARTIFACT_BUCKET}
- vars.CLOUD_TASKS_QUEUE=${CLOUD_TASKS_QUEUE}
- vars.CLOUD_TASKS_SERVICE_ACCOUNT=${TASKS_SERVICE_ACCOUNT}
- vars.MLFLOW_TRACKING_URI=<production-or-staging-mlflow-uri>
- secrets.GCP_WORKLOAD_IDENTITY_PROVIDER=<provider-resource-name>
- secrets.GCP_DEPLOY_SERVICE_ACCOUNT=${DEPLOY_SERVICE_ACCOUNT}
- secrets.API_KEYS_SECRET_NAME=<secret-manager-secret-name>
EOF

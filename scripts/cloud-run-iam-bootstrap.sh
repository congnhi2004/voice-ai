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
: "${API_KEYS_SECRET_NAME:=voice-ai-api-keys}"
: "${OPENAI_API_KEY_SECRET_NAME:=voice-ai-openai-api-key}"
: "${DRY_RUN:=1}"
: "${GRANT_RUNTIME_SIGNBLOB:=1}"

run_cmd() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
  if [[ "${DRY_RUN}" == "0" ]]; then
    "$@"
  fi
}

if [[ "${DRY_RUN}" == "0" ]]; then
  PROJECT_NUMBER="$(gcloud projects describe "${GCP_PROJECT_ID}" --format='value(projectNumber)')"
else
  PROJECT_NUMBER="${PROJECT_NUMBER:-000000000000}"
  echo "# Dry run uses PROJECT_NUMBER=${PROJECT_NUMBER}; set PROJECT_NUMBER to render exact Cloud Tasks service-agent bindings."
fi

run_cmd gcloud config set project "${GCP_PROJECT_ID}"

run_cmd gcloud services enable \
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
  if [[ "${DRY_RUN}" == "0" ]] && ! gcloud iam service-accounts describe "${sa}" >/dev/null 2>&1; then
    name="${sa%@*}"
    run_cmd gcloud iam service-accounts create "${name}" --display-name="${name}"
  elif [[ "${DRY_RUN}" != "0" ]]; then
    run_cmd gcloud iam service-accounts describe "${sa}"
    run_cmd gcloud iam service-accounts create "${sa%@*}" --display-name="${sa%@*}"
  fi
done

if [[ "${DRY_RUN}" == "0" ]] && ! gcloud artifacts repositories describe "${ARTIFACT_REPOSITORY}" --location "${REGION}" >/dev/null 2>&1; then
  run_cmd gcloud artifacts repositories create "${ARTIFACT_REPOSITORY}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Voice AI containers"
elif [[ "${DRY_RUN}" != "0" ]]; then
  run_cmd gcloud artifacts repositories describe "${ARTIFACT_REPOSITORY}" --location "${REGION}"
  run_cmd gcloud artifacts repositories create "${ARTIFACT_REPOSITORY}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Voice AI containers"
else
  run_cmd gcloud artifacts repositories describe "${ARTIFACT_REPOSITORY}" --location "${REGION}"
fi

for bucket in "${GCS_AUDIO_BUCKET}" "${GCS_ARTIFACT_BUCKET}"; do
  if [[ "${DRY_RUN}" == "0" ]] && ! gcloud storage buckets describe "gs://${bucket}" >/dev/null 2>&1; then
    run_cmd gcloud storage buckets create "gs://${bucket}" \
      --project="${GCP_PROJECT_ID}" \
      --location="${REGION}" \
      --uniform-bucket-level-access
  elif [[ "${DRY_RUN}" != "0" ]]; then
    run_cmd gcloud storage buckets describe "gs://${bucket}" --project="${GCP_PROJECT_ID}"
    run_cmd gcloud storage buckets create "gs://${bucket}" \
      --project="${GCP_PROJECT_ID}" \
      --location="${REGION}" \
      --uniform-bucket-level-access
  fi
  run_cmd gcloud storage buckets update "gs://${bucket}" \
    --project="${GCP_PROJECT_ID}" \
    --public-access-prevention=enforced
done

run_cmd gcloud storage buckets update "gs://${GCS_AUDIO_BUCKET}" \
  --project="${GCP_PROJECT_ID}" \
  --lifecycle-file=deploy/gcs-audio-lifecycle.json
run_cmd gcloud storage buckets update "gs://${GCS_ARTIFACT_BUCKET}" \
  --project="${GCP_PROJECT_ID}" \
  --lifecycle-file=deploy/gcs-video-artifact-lifecycle.json

for secret in "${API_KEYS_SECRET_NAME}" "${OPENAI_API_KEY_SECRET_NAME}"; do
  if [[ "${DRY_RUN}" == "0" ]] && ! gcloud secrets describe "${secret}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
    run_cmd gcloud secrets create "${secret}" \
      --project="${GCP_PROJECT_ID}" \
      --replication-policy="automatic"
    echo "# Add the first version separately without echoing the value: printf %s \"...\" | gcloud secrets versions add ${secret} --data-file=-"
  elif [[ "${DRY_RUN}" != "0" ]]; then
    run_cmd gcloud secrets describe "${secret}" --project="${GCP_PROJECT_ID}"
    run_cmd gcloud secrets create "${secret}" \
      --project="${GCP_PROJECT_ID}" \
      --replication-policy="automatic"
    echo "# Secret value command intentionally omitted from dry-run output."
  fi
done

run_cmd gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
  --member="serviceAccount:${DEPLOY_SERVICE_ACCOUNT}" \
  --role="roles/run.admin"
run_cmd gcloud artifacts repositories add-iam-policy-binding "${ARTIFACT_REPOSITORY}" \
  --location="${REGION}" \
  --member="serviceAccount:${DEPLOY_SERVICE_ACCOUNT}" \
  --role="roles/artifactregistry.writer"
run_cmd gcloud iam service-accounts add-iam-policy-binding "${RUNTIME_SERVICE_ACCOUNT}" \
  --member="serviceAccount:${DEPLOY_SERVICE_ACCOUNT}" \
  --role="roles/iam.serviceAccountUser"

run_cmd gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SERVICE_ACCOUNT}" \
  --role="roles/cloudtexttospeech.user"
run_cmd gcloud storage buckets add-iam-policy-binding "gs://${GCS_AUDIO_BUCKET}" \
  --member="serviceAccount:${RUNTIME_SERVICE_ACCOUNT}" \
  --role="roles/storage.objectAdmin"
run_cmd gcloud storage buckets add-iam-policy-binding "gs://${GCS_ARTIFACT_BUCKET}" \
  --member="serviceAccount:${RUNTIME_SERVICE_ACCOUNT}" \
  --role="roles/storage.objectAdmin"

for secret in "${API_KEYS_SECRET_NAME}" "${OPENAI_API_KEY_SECRET_NAME}"; do
  run_cmd gcloud secrets add-iam-policy-binding "${secret}" \
    --project="${GCP_PROJECT_ID}" \
    --member="serviceAccount:${RUNTIME_SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
done

if [[ "${GRANT_RUNTIME_SIGNBLOB}" == "1" ]]; then
  run_cmd gcloud iam service-accounts add-iam-policy-binding "${RUNTIME_SERVICE_ACCOUNT}" \
    --member="serviceAccount:${RUNTIME_SERVICE_ACCOUNT}" \
    --role="roles/iam.serviceAccountTokenCreator"
fi

if [[ "${DRY_RUN}" == "0" ]] && ! gcloud tasks queues describe "${CLOUD_TASKS_QUEUE}" --location="${REGION}" >/dev/null 2>&1; then
  run_cmd gcloud tasks queues create "${CLOUD_TASKS_QUEUE}" \
    --location="${REGION}" \
    --max-dispatches-per-second=2 \
    --max-concurrent-dispatches=1 \
    --max-attempts=3 \
    --min-backoff=30s \
    --max-backoff=600s
else
  run_cmd gcloud tasks queues describe "${CLOUD_TASKS_QUEUE}" --location="${REGION}"
  run_cmd gcloud tasks queues update "${CLOUD_TASKS_QUEUE}" \
    --location="${REGION}" \
    --max-dispatches-per-second=2 \
    --max-concurrent-dispatches=1 \
    --max-attempts=3 \
    --min-backoff=30s \
    --max-backoff=600s
fi

run_cmd gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SERVICE_ACCOUNT}" \
  --role="roles/cloudtasks.enqueuer"
run_cmd gcloud iam service-accounts add-iam-policy-binding "${TASKS_SERVICE_ACCOUNT}" \
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
- secrets.OPENAI_API_KEY_SECRET_NAME=<secret-manager-secret-name>
EOF

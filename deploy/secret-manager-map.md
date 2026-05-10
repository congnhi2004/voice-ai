# Secret Manager Map

No secret value belongs in this repository or in GitHub Actions logs.

## Runtime Secrets

| Environment variable | Secret Manager secret | GitHub secret that stores the secret name | Purpose |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | `voice-ai-openai-api-key` | `OPENAI_API_KEY_SECRET_NAME` | OpenAI TTS provider for `marin`. |
| `API_KEYS` | `voice-ai-api-keys` | `API_KEYS_SECRET_NAME` | MVP bearer/API key list until production auth replaces it. |

Cloud Run service and job deploys should map these with `--set-secrets`, not plain environment values. Pin numbered versions for high-control releases; use `latest` only when operators accept automatic rotation on new instance startup.

## Non-Secret Deployment Variables

| GitHub variable | Example | Purpose |
| --- | --- | --- |
| `GCP_PROJECT_ID` | `voice-ai-prod` | Deployment project. |
| `ARTIFACT_REGISTRY_REPOSITORY` | `voice-ai` | Docker repository in Artifact Registry. |
| `CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT` | `voice-ai-run@PROJECT_ID.iam.gserviceaccount.com` | Runtime identity for service and job. |
| `GCS_AUDIO_BUCKET` | `voice-ai-prod-audio` | Private generated audio bucket. |
| `GCS_ARTIFACT_BUCKET` | `voice-ai-prod-artifacts` | Private video source/intermediate/rendered artifact bucket. |
| `CLOUD_TASKS_QUEUE` | `voice-ai-video` | Optional queue if the app dispatches video work through Cloud Tasks. |
| `CLOUD_TASKS_SERVICE_ACCOUNT` | `voice-ai-tasks@PROJECT_ID.iam.gserviceaccount.com` | Optional OIDC identity for task handlers. |
| `MLFLOW_TRACKING_URI` | `https://mlflow.example.com` | Production MLflow endpoint. |
| `OPENAI_TTS_MODEL` | `gpt-4o-mini-tts` | OpenAI TTS model. |
| `OPENAI_TTS_VOICE` | `marin` | Commercial voice default proven in public demo. |
| `OPENAI_TTS_RESPONSE_FORMAT` | `wav` | Audio format. |

## IAM Summary

Deployment identity used by GitHub OIDC:

- `roles/run.admin` on the project.
- `roles/artifactregistry.writer` on the Artifact Registry repository.
- `roles/iam.serviceAccountUser` on the Cloud Run runtime service account.

Runtime service account:

- `roles/secretmanager.secretAccessor` on the two runtime secrets.
- `roles/storage.objectAdmin` or narrower custom object permissions on the audio and artifact buckets.
- Provider-specific roles only where used by active code. OpenAI TTS does not need Google Text-to-Speech IAM.

Optional Cloud Tasks identity:

- `roles/run.invoker` on the private Cloud Run task handler.
- Cloud Tasks service agent can impersonate the task service account for OIDC dispatch.

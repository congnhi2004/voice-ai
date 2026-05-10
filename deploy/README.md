# Cloud Run Deployment Notes

This scaffold targets a containerized FastAPI service on Cloud Run with local MLflow available through Docker Compose.

Official references checked on 2026-05-10:

- Cloud Run FastAPI quickstart: https://cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-fastapi-service
- Cloud Run logging: https://cloud.google.com/run/docs/logging
- Cloud Run monitoring overview: https://docs.cloud.google.com/run/docs/monitoring-overview
- Google GitHub Actions auth: https://github.com/google-github-actions/auth
- Google GitHub Actions deploy-cloudrun: https://github.com/google-github-actions/deploy-cloudrun
- MLflow Tracking: https://www.mlflow.org/docs/latest/ml/tracking
- Cloud Run request timeout: https://cloud.google.com/run/docs/configuring/request-timeout
- Cloud Tasks HTTP target tasks: https://cloud.google.com/tasks/docs/creating-http-target-tasks

## Assumptions

- Backend exposes a FastAPI application at `app.main:app`, overrideable with `APP_MODULE`.
- Production uses Cloud Run runtime service identity, not mounted JSON service account keys.
- Production audio is stored in Cloud Storage; local filesystem audio is only for local/dev.
- Video localization uses FFmpeg in the container and durable Cloud Storage for source videos, intermediate artifacts, and rendered outputs.
- Long-running video work should be submitted to Cloud Tasks and handled by a Cloud Run endpoint or split into Cloud Run Jobs when processing exceeds service/task deadlines.
- MLflow production endpoint is supplied through `MLFLOW_TRACKING_URI`; local compose runs MLflow at `http://localhost:5000`.
- If a static frontend exists, build artifacts are expected under `frontend/dist` and can be served by the backend or copied into the image context. The Dockerfile does not build frontend assets.

## Required Google Cloud APIs

Enable these APIs in the deployment project:

```bash
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
```

## Minimum IAM

Deployment service account used by GitHub Actions:

- `roles/run.admin`
- `roles/artifactregistry.writer`
- `roles/iam.serviceAccountUser` on the Cloud Run runtime service account
- `roles/secretmanager.secretAccessor` only if deploy-time secret reads are needed

Cloud Run runtime service account:

- `roles/cloudtexttospeech.user` or equivalent custom permission for Text-to-Speech
- `roles/storage.objectAdmin` on the audio and artifact buckets, narrowed to the target buckets
- `roles/secretmanager.secretAccessor` for runtime secrets such as `API_KEYS`

Cloud Tasks service account:

- `roles/run.invoker` on the Cloud Run service if task handlers are private
- permission for the Cloud Tasks service agent to mint OIDC tokens for the task service account

## Local

```bash
cp .env.example .env
docker compose up --build
```

Services:

- App: http://localhost:8080
- MLflow UI/server: http://localhost:5000

Mounted local state:

- `./data/audio` to `/app/data/audio`
- `./data/video` to `/app/data/video`
- `./data/artifacts` to `/app/data/artifacts`
- `./mlruns` and `./artifacts/mlflow` for MLflow backend/artifacts
- `./logs` for app logs if the implementation writes files locally

Optional local worker profile, once `app.worker` exists:

```bash
docker compose --profile worker up --build
```

## Manual Deploy

Use `scripts/cloud-run-deploy.sh` after exporting required variables:

```bash
export GCP_PROJECT_ID=my-project
export REGION=us-central1
export SERVICE_NAME=voice-ai
export ARTIFACT_REPOSITORY=voice-ai
export CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT=voice-ai-run@my-project.iam.gserviceaccount.com
export GCS_AUDIO_BUCKET=my-voice-ai-audio
export GCS_ARTIFACT_BUCKET=my-voice-ai-artifacts
export CLOUD_TASKS_QUEUE=voice-ai-video
export MLFLOW_TRACKING_URI=https://mlflow.example.com
./scripts/cloud-run-deploy.sh
```

## Video Localization Operations

Recommended production shape:

1. API receives metadata and writes source media to `gs://${GCS_ARTIFACT_BUCKET}/${GCS_SOURCE_VIDEO_PREFIX}`.
2. API enqueues a Cloud Tasks HTTP task to `/internal/tasks/video-localization`.
3. Worker handler runs bounded stages: `upload`, `stt`, `translation`, `tts`, `alignment`, `render`, `delivery`.
4. FFmpeg performs extract/remux/render work inside the container.
5. Intermediate files and final videos are written to Cloud Storage prefixes, not Cloud Run local disk.
6. MLflow records one parent video-localization run with stage child runs or stage-tagged metrics.

Constraints:

- Cloud Run service timeout can be raised to 3600 seconds; Cloud Tasks HTTP targets have their own dispatch deadline limits, so large jobs should checkpoint and re-enqueue or move to Cloud Run Jobs.
- The deploy workflow sets `--concurrency=1`, `--cpu=2`, `--memory=4Gi`, and `--timeout=3600` for FFmpeg-heavy processing. Tune after real media benchmarks.
- Do not store uploaded or rendered media in the container filesystem except as temporary scratch space.

## Observation

```bash
./scripts/cloud-run-observe.sh
```

This prints service metadata, recent revisions, recent logs, and metric query hints. Cloud Run automatically sends request, container, and system logs to Cloud Logging.

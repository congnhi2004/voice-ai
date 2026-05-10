# Backend Async Storage Production Report - 2026-05-10

## Files Changed

- `app/config.py`: added video job dispatch, Cloud Tasks, internal task token, and GCS job metadata prefix settings.
- `app/main.py`: changed video job creation to persist a queued job first, added dispatcher handoff, added internal task processing endpoint, expanded readiness/capability fields, and added dispatch/storage error mapping.
- `app/models.py`: added durable video job request metadata and storage/dispatch metadata fields on video job status.
- `app/storage.py`: added GCS object download helpers for worker-side source/job metadata recovery.
- `app/video_localization.py`: added durable request/status store support, GCS metadata mirroring, Cloud Tasks/local dispatcher abstractions, queued job creation, and idempotent job processing by id.
- `requirements.txt`: added `google-cloud-tasks`.
- `tests/backend/test_api.py`: added tests for queued Cloud Tasks mode, status polling, internal task idempotency, readiness mode reporting, GCS mocked download behavior, dispatch error mapping, and storage error mapping.
- `docs/subagents/backend-async-storage-production-report-20260510.md`: this report.

## API Endpoints And Contracts Affected

- `POST /v1/video-localization/jobs`
  - Local default remains `VIDEO_JOB_DISPATCH_MODE=local_inline`, so local/demo requests still return a completed `succeeded` job when processing succeeds.
  - Production mode `VIDEO_JOB_DISPATCH_MODE=cloud_tasks` returns a durable `queued` job and dispatch metadata instead of doing render/transcription work in the request thread.
  - Response status now includes `storage` and `dispatch` metadata fields.
- `GET /v1/video-localization/jobs/{job_id}`
  - Polls `queued`, `running`, `succeeded`, or `failed` state from persisted metadata.
  - Existing artifact signed URL refresh behavior is preserved.
- `POST /internal/video-localization/tasks/{job_id}`
  - Internal worker/task handler that processes an existing job id.
  - Idempotent for completed jobs: repeated delivery returns the existing `succeeded` status without regenerating artifacts.
  - Supports optional `X-Internal-Task-Token` via `INTERNAL_TASK_TOKEN`.
- `GET /readyz`
  - Adds video storage metadata mode, artifact bucket, dispatch mode, dispatch readiness, and worker endpoint fields.

## Env Vars Added

- `VIDEO_JOB_DISPATCH_MODE`: `local_inline` default, or `cloud_tasks` for production async dispatch.
- `INTERNAL_TASK_TOKEN`: optional shared token for the internal task endpoint.
- `CLOUD_TASKS_PROJECT_ID`: defaults to `GCP_PROJECT_ID` when unset.
- `CLOUD_TASKS_LOCATION`: default `us-central1`.
- `CLOUD_TASKS_QUEUE`: required for `cloud_tasks`.
- `CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL`: required for Cloud Tasks OIDC token dispatch.
- `CLOUD_TASKS_AUDIENCE`: optional OIDC audience override.
- `CLOUD_TASKS_HANDLER_URL`: base internal task handler URL, for example `https://service/internal/video-localization/tasks`.
- `CLOUD_TASKS_DISPATCH_DEADLINE_SECONDS`: default `1800`.
- `GCS_JOB_METADATA_PREFIX`: default `voice-ai/video/jobs`.

## Context7 Docs Used

- `/fastapi/fastapi`, topic `BackgroundTasks dependencies response models TestClient`.
- `/googleapis/python-storage`, topic `upload blobs signed URL client testing`.
- `/websites/cloud_google_tasks`, topic `HTTP target tasks with OIDC token create task python`.

## Production Blockers Closed

- Video job creation no longer requires the request thread to perform full localization in production mode.
- Job state now has a durable queued/running/succeeded/failed lifecycle and a pollable status contract.
- A worker/task handler can process a job by id from stored request/source metadata.
- Handler is idempotent for repeated task delivery after success.
- GCS-backed mode can persist source media, artifacts, and mirrored job metadata under configured prefixes.
- Readiness and capability responses now show whether storage and dispatch are local or production-oriented.
- MLflow/logging remains metadata-only; no raw transcript/subtitle text was added to structured logs.

## Tests Run

```bash
taskset -c 0-3 env PYTHONPATH=. .venv/bin/pytest tests/backend -q
```

Result: `40 passed, 3 skipped, 3 warnings`.

```bash
env PYTHONPATH=. .venv/bin/python - <<'PY'
from pathlib import Path
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
settings = Settings(tts_provider='local', audio_storage_dir=Path('/tmp/voice-ai-openapi-smoke/audio'), video_jobs_dir=Path('/tmp/voice-ai-openapi-smoke/video-jobs'), auth_storage_path=Path('/tmp/voice-ai-openapi-smoke/auth.sqlite3'), audio_base_url='http://testserver')
client = TestClient(create_app(settings))
schema = client.get('/openapi.json')
assert schema.status_code == 200
paths = schema.json()['paths']
required = ['/v1/video-localization/jobs', '/v1/video-localization/jobs/{job_id}', '/internal/video-localization/tasks/{job_id}', '/readyz']
assert not [path for path in required if path not in paths]
PY
```

Result: OpenAPI smoke passed for new/changed endpoints.

## Remaining Blockers Requiring Real GCP Credentials

- Create the Cloud Tasks queue and verify `cloudtasks.tasks.create` for the runtime identity.
- Grant the Cloud Tasks OIDC service account permission to invoke the internal Cloud Run endpoint, or configure and rotate `INTERNAL_TASK_TOKEN`.
- Run a live `VIDEO_JOB_DISPATCH_MODE=cloud_tasks` smoke test against the deployed service.
- Create and permission the GCS artifact bucket, then verify source/status/artifact writes and signed URL generation with production ADC.
- Apply/verify lifecycle policies for source, intermediate, metadata, and rendered video objects.

# Infra Production Completion Audit - 2026-05-10

Role: Infra Production Readiness Auditor  
Skills used: `voice-ai-infra-observability`, `voice-ai-product-docs`  
Scope: report-only audit for infrastructure, deployment, observability, and lifecycle completeness.  
Write scope honored: only `docs/subagents/infra-production-completion-audit-20260510.md` was written.

## Final Recommendation

**Do not mark this product commercially production-ready yet.**

The current public prototype is live and testable from the public IP: frontend `http://103.27.237.252:4174/`, backend `http://103.27.237.252:8080/`, local MLflow `http://127.0.0.1:5000/`, and backend container image `voice-ai:durable-20260510`. Docker runtime, FFmpeg, local tmux services, MLflow logging, deploy templates, CI workflow, Secret Manager mapping docs, GCS lifecycle templates, and dry-run Cloud Run commands are present.

Commercial production release remains **blocked** because the live runtime is local/tmux-based, storage readiness is local, billing is not configured, live GCP credentials are unavailable here, there is no verified Cloud Run revision / Artifact Registry digest / GCS object / Secret Manager binding / GitHub Actions run, and GitHub publication is blocked from this tool session.

## Official Sources Checked

Checked with built-in web search on 2026-05-10:

| Source | Production relevance |
| --- | --- |
| https://cloud.google.com/run/docs/configuring/services/secrets | Cloud Run services should consume sensitive values through Secret Manager. |
| https://cloud.google.com/run/docs/configuring/jobs/secrets | Cloud Run jobs can use Secret Manager references and require runtime service account access. |
| https://cloud.google.com/run/docs/configuring/jobs/environment-variables | Job env vars are plain config; secrets should not be stored as env values. |
| https://cloud.google.com/run/docs/create-jobs | Cloud Run Jobs are an appropriate shape for task-to-completion work. |
| https://cloud.google.com/run/docs/configuring/task-timeout | Long-running job retries/timeouts need explicit configuration. |
| https://cloud.google.com/storage/docs/lifecycle | GCS lifecycle policies can TTL/delete or tier objects, but actions are asynchronous. |
| https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/ | MLflow tracking server separates backend store and artifact store and can proxy artifacts. |
| https://www.mlflow.org/docs/latest/ml/tracking | MLflow stores run metadata separately from artifacts; production artifact storage must be explicit. |

## Pass / Fail / Blocked Matrix

| Area | Status | Evidence |
| --- | --- | --- |
| Public frontend | PASS for prototype | `curl -fsSI http://103.27.237.252:4174/` returned HTTP 200. `scripts/local-services.sh status` reports frontend preview on port `4174`. |
| Public backend health | PASS for prototype | `curl http://103.27.237.252:8080/healthz` returned `{"status":"ok","service":"voice-ai","version":"0.1.0"}`. |
| Public backend readiness | PARTIAL | `/readyz` reports `provider.name=openai`, provider ready, MLflow ready, FFmpeg available, but `storage.mode=local`. |
| Docker image/runtime | PASS local | `voice-ai:durable-20260510` exists, created `2026-05-10T17:16:31+07:00`, runs as `appuser`, size about 484 MB, Docker healthcheck calls `/healthz`. |
| FFmpeg availability | PASS local | `docker run --rm --entrypoint ffmpeg voice-ai:durable-20260510 -version` returned FFmpeg `7.1.3-0+deb13u1`. Running backend also has FFmpeg. |
| Local tmux services | PASS local | `voice-ai-backend`, `voice-ai-frontend`, and `voice-ai-mlflow` tmux sessions are active on socket `voice-ai`. |
| Local containers | PASS local | `docker ps` shows `voice-ai-backend` on `0.0.0.0:8080` healthy and `voice-ai-mlflow` on `0.0.0.0:5000`. |
| MLflow local UI/server | PASS local | `curl http://127.0.0.1:5000/health` returned `OK`; `curl -I http://127.0.0.1:5000/` returned HTTP 200; backend imports `mlflow 3.12.0`. |
| MLflow logging | PASS local | `logs/mlflow.log` shows run create/log-batch/update calls; `logs/backend.log` includes structured request completion lines and MLflow-backed synth events. |
| Public MLflow endpoint | FAIL if public observability is required | `curl http://103.27.237.252:5000/api/3.0/mlflow/server-info` returned HTTP 403 `Invalid Host header - possible DNS rebinding attack detected`. Acceptable only if MLflow is intentionally internal-only. |
| Docker Compose config | PASS | `docker compose config --quiet` completed successfully. Compose includes app, MLflow, and optional worker profile. |
| Cloud Run manifests | PASS as planned artifacts | `deploy/cloud-run-service.yaml.template` and `deploy/cloud-run-video-job.yaml.template` define service/job shape, resources, secrets, GCS envs, and MLflow URI placeholders. No live deployment evidence. |
| Cloud Run deploy dry run | PASS as dry-run only | `deploy/cloud-run-deploy-operator.sh` rendered `gcloud run deploy` and `gcloud run jobs update` commands with `--set-secrets`. `gcloud` is not installed, so live validation is blocked. |
| Long-running video work model | PARTIAL | Repo has a Cloud Run Job template and workflow job creation. There is mismatch: deploy workflow service uses `JOB_DISPATCH_MODE=cloud_tasks`, operator/templates default to `cloud_run_job`. Needs one production control path. |
| GCS lifecycle/storage docs | PASS as planned artifacts | `deploy/gcs-audio-lifecycle.json` and `deploy/gcs-video-artifact-lifecycle.json` parse as JSON. Audio TTL: NEARLINE after 7 days, delete after 30. Video: intermediate delete 7 days, source delete 14, rendered NEARLINE 30/delete 90. No live bucket/policy proof. |
| Runtime storage | FAIL for production | `/readyz` reports `storage.mode=local`; product artifacts are served from local runtime, not proven durable GCS signed URLs. |
| Secrets docs | PASS docs | `deploy/secret-manager-map.md` maps `OPENAI_API_KEY` and `API_KEYS` to Secret Manager names. `.env.runtime` has OpenAI runtime values set locally, but Stripe/GCS values are absent from runtime state. |
| Secret handling in local status | PASS | `scripts/local-services.sh status` prints credential fields only as set/unset; it did not print secret values. |
| Billing/product readiness | FAIL | `/v1/product/capabilities` reports billing `available=false`, `mode=not-configured`, `production_billing=false`. |
| CI workflow | PASS as config | `.github/workflows/ci.yml` runs backend tests, frontend lint/test/build, compose validation, Docker build, and video smoke hook. No pushed GitHub run evidence. |
| Deploy workflow | PASS as config, BLOCKED live | `.github/workflows/deploy-cloud-run.yml` has manual workflow dispatch, Google OIDC auth, Artifact Registry push, Cloud Run deploy, and optional video job update. It requires GitHub/GCP secrets not available here. |
| Git/GitHub release state | BLOCKED | `git status --short --branch`: `main...origin/main [ahead 8]`; no tags point at HEAD; `gh` is not installed; `GIT_TERMINAL_PROMPT=0 git push --dry-run origin HEAD` failed because HTTPS username cannot be read. |

## Live vs Planned Distinction

### Actually Live Now

- Public Vite preview frontend at `http://103.27.237.252:4174/`.
- Public backend at `http://103.27.237.252:8080/`.
- Local Docker backend container `voice-ai-backend` from image `voice-ai:durable-20260510`.
- Local Docker MLflow container `ghcr.io/mlflow/mlflow:v3.12.0`.
- Local MLflow health and logging at `127.0.0.1:5000`.
- tmux-managed local service lifecycle via `scripts/local-services.sh`.
- OpenAI runtime env is set in the running local backend, with values redacted by status output.

### Documented / Dry-Run / Planned

- Cloud Run service and Cloud Run job deployment.
- Artifact Registry image push.
- Secret Manager runtime bindings.
- GCS audio/video buckets, signed URL behavior, and lifecycle policies.
- Cloud Tasks queue path for service-based async video work.
- Cloud Logging/Monitoring dashboards and alert policies.
- GitHub Actions production deployment.
- Commercial billing and release publication.

## Commands and Evidence

```bash
docker compose config --quiet
# result: docker compose config: ok

bash scripts/local-services.sh status
# result: tmux sessions active; backend image voice-ai:durable-20260510;
# backend healthy; MLflow and frontend active; OpenAI/runtime fields set/unset only.

docker image inspect voice-ai:durable-20260510 --format '...'
# result: image id sha256:0a907b7..., created 2026-05-10T17:16:31+07:00,
# user appuser, healthcheck curl /healthz.

docker run --rm --entrypoint ffmpeg voice-ai:durable-20260510 -version
# result: ffmpeg version 7.1.3-0+deb13u1.

docker exec voice-ai-backend sh -c 'id; ffmpeg -version | sed -n "1,2p"; python -c "import mlflow; print(mlflow.__version__)"'
# result: uid=1000(appuser), FFmpeg present, mlflow 3.12.0.

curl -fsSI http://103.27.237.252:4174/
# result: HTTP/1.1 200 OK.

curl -fsS http://103.27.237.252:8080/healthz
# result: {"status":"ok","service":"voice-ai","version":"0.1.0"}.

curl -fsS http://103.27.237.252:8080/readyz
# result: provider openai ready; storage local ready; MLflow ready; video openai/auto ready; FFmpeg available.

curl -fsS http://127.0.0.1:5000/health
# result: OK.

curl -sS -o /tmp/voice-ai-mlflow-public.txt -w 'HTTP %{http_code}\n' http://103.27.237.252:5000/api/3.0/mlflow/server-info
# result: HTTP 403, Invalid Host header.

curl -fsS http://103.27.237.252:8080/v1/product/capabilities | python3 -m json.tool
# result: auth production_identity=true, billing available=false, production_billing=false.

bash -n scripts/local-services.sh deploy/cloud-run-deploy-operator.sh scripts/cloud-run-deploy.sh scripts/cloud-run-observe.sh
# result: shell syntax ok.

python3 - <<'PY'
from pathlib import Path
import json
for path in ['deploy/gcs-audio-lifecycle.json','deploy/gcs-video-artifact-lifecycle.json']:
    json.loads(Path(path).read_text())
    print(f'{path}: json ok')
PY
# result: both lifecycle files parsed.

GCP_PROJECT_ID=voice-ai-prod REGION=us-central1 ENVIRONMENT=staging SERVICE_NAME=voice-ai \
ARTIFACT_REPOSITORY=voice-ai CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT=voice-ai-run@voice-ai-prod.iam.gserviceaccount.com \
GCS_AUDIO_BUCKET=voice-ai-prod-audio GCS_ARTIFACT_BUCKET=voice-ai-prod-artifacts \
API_KEYS_SECRET_NAME=voice-ai-api-keys OPENAI_API_KEY_SECRET_NAME=voice-ai-openai-api-key \
MLFLOW_TRACKING_URI=https://mlflow.example.com DRY_RUN=1 deploy/cloud-run-deploy-operator.sh
# result: rendered gcloud config/auth/artifact/docker push/cloud run deploy/cloud run job update commands only.

gcloud auth list --filter=status:ACTIVE --format='value(account)'
# result: gcloud: command not found.

git status --short --branch
# result: ## main...origin/main [ahead 8], plus pre-existing untracked docs/subagents/evidence/qa-audit-20260510/.

GIT_TERMINAL_PROMPT=0 git push --dry-run origin HEAD
# result: fatal: could not read Username for 'https://github.com': terminal prompts disabled.
```

## Production Blockers

1. **No live GCP proof**: `gcloud` is not installed and GCP deployment credentials are not available in this environment. There is no verified Cloud Run service URL, revision, traffic split, Artifact Registry digest, Cloud Run Job execution, Secret Manager binding, GCS object, or rollback evidence.
2. **Runtime is local, not Cloud Run**: the live public service is tmux + Docker on the host, with Vite preview frontend and backend bound to public ports.
3. **Storage is still local at runtime**: `/readyz` reports `storage.mode=local`. GCS config, signed URLs, buckets, and lifecycle policies are planned artifacts without live bucket evidence.
4. **Billing is absent**: public capabilities report production billing false.
5. **Observability is local/internal only**: backend-to-MLflow logging works locally, but public MLflow by IP returns 403. The production stance must be internal-only with documented operator access, or a secured public/proxied observability endpoint.
6. **Async video strategy is not settled**: repo contains Cloud Run Job templates and a Cloud Tasks-oriented workflow path. Pick one production dispatch model, then prove retries, timeout, idempotency, and artifact persistence.
7. **GitHub release path is blocked**: local `main` is ahead of `origin/main` by 8 commits; `gh` is unavailable; push dry-run fails due missing non-interactive GitHub credentials; no release tag exists at HEAD.
8. **Secrets are not production-complete**: OpenAI local runtime is set, but Stripe/GCS live secrets are absent; Secret Manager mappings are documented but not live-verified.

## Required Next Evidence Before Production Approval

- Run a real Cloud Run staging deploy with the exact image digest and capture service URL, latest ready revision, traffic, env/secrets redaction, and `/healthz` + `/readyz` smoke results.
- Execute the Cloud Run video job or chosen Cloud Tasks path with one short video and capture job/task status, logs, retry policy, timeout behavior, MLflow run id, and GCS artifact URIs.
- Create private GCS audio/artifact buckets, apply lifecycle JSON, verify signed URL download, and show lifecycle policy on the bucket.
- Verify Secret Manager references for `OPENAI_API_KEY`, `API_KEYS`, and any Stripe/GCS production secrets without printing secret values.
- Configure production MLflow backend/artifact storage or explicitly document MLflow as internal-only; prove operator access and log/metric retention.
- Complete billing or gate commercial functionality until billing is available.
- Push the 8 local commits, run GitHub CI/deploy workflow, and attach run URLs/status before release tagging.

## Decision

**Prototype public readiness:** PASS.  
**Infra/commercial production readiness:** FAIL / BLOCKED.  

The product is suitable for controlled public prototype testing on the current host. It is not yet suitable for a production launch claim until the Cloud Run, GCS, Secret Manager, observability, billing, CI/CD, and GitHub release blockers above are closed with live evidence.

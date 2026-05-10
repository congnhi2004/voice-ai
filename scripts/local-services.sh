#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

select_runtime_env_file() {
  if [[ -n "${RUNTIME_ENV_FILE:-}" ]]; then
    printf "%s" "${RUNTIME_ENV_FILE}"
    return 0
  fi
  if [[ -f "${ROOT_DIR}/.env.runtime" ]]; then
    printf "%s" "${ROOT_DIR}/.env.runtime"
    return 0
  fi
  printf "%s" "${ROOT_DIR}/.env.local"
}

RUNTIME_ENV_FILE="$(select_runtime_env_file)"
RUNTIME_ENV_LOADED=0

load_runtime_env_file() {
  if [[ ! -f "${RUNTIME_ENV_FILE}" ]]; then
    return 0
  fi
  set -a
  # shellcheck source=/dev/null
  source "${RUNTIME_ENV_FILE}"
  set +a
  RUNTIME_ENV_LOADED=1
}

load_runtime_env_file

TMUX_SOCKET="${TMUX_SOCKET:-voice-ai}"
SERVER_IP="${SERVER_IP:-$(hostname -I | awk '{print $1}')}"
API_PORT="${API_PORT:-8080}"
FRONTEND_PORT="${FRONTEND_PORT:-4174}"
MLFLOW_PORT="${MLFLOW_PORT:-5000}"
IMAGE="${IMAGE:-voice-ai:durable-20260510}"
MLFLOW_IMAGE="${MLFLOW_IMAGE:-ghcr.io/mlflow/mlflow:v3.12.0}"
NETWORK="${NETWORK:-voice-ai-local}"
FRONTEND_MODE="${FRONTEND_MODE:-preview}"
FORCE_FRONTEND_BUILD="${FORCE_FRONTEND_BUILD:-0}"
PUBLIC_DEMO_PROFILE="${PUBLIC_DEMO_PROFILE:-}"
REQUIRE_REAL_TTS="${REQUIRE_REAL_TTS:-0}"
TASKSET_CPUSET="${TASKSET_CPUSET:-0-3}"
MLFLOW_ALLOWED_HOSTS="${MLFLOW_ALLOWED_HOSTS:-voice-ai-mlflow,voice-ai-mlflow:5000,localhost,localhost:*,127.0.0.1,127.0.0.1:*,host.docker.internal,host.docker.internal:5000}"
BACKEND_ENV_NAMES=(
  TTS_PROVIDER
  API_KEYS
  OPENAI_API_KEY
  OPENAI_TTS_MODEL
  OPENAI_TTS_VOICE
  OPENAI_TTS_RESPONSE_FORMAT
  GCP_PROJECT_ID
  GOOGLE_APPLICATION_CREDENTIALS
  GOOGLE_CLOUD_REGION
  PUBLIC_DEMO_PROFILE
  REQUIRE_REAL_TTS
)

if command -v taskset >/dev/null 2>&1; then
  TASKSET_CMD="taskset -c ${TASKSET_CPUSET}"
else
  TASKSET_CMD=""
fi

frontend_needs_build() {
  [[ "${FORCE_FRONTEND_BUILD}" == "1" ]] && return 0
  [[ ! -f "${ROOT_DIR}/frontend/dist/index.html" ]] && return 0
  find "${ROOT_DIR}/frontend" \
    \( -path "${ROOT_DIR}/frontend/node_modules" -o -path "${ROOT_DIR}/frontend/dist" \) -prune \
    -o -type f \
    \( -path "${ROOT_DIR}/frontend/src/*" -o -name index.html -o -name package.json -o -name package-lock.json -o -name tsconfig.json -o -name vite.config.ts \) \
    -newer "${ROOT_DIR}/frontend/dist/index.html" -print -quit | grep -q .
}

prepare_frontend() {
  case "${FRONTEND_MODE}" in
    preview)
      if frontend_needs_build; then
        echo "Building frontend/dist for preview on 0.0.0.0:${FRONTEND_PORT}"
        (cd "${ROOT_DIR}/frontend" && ${TASKSET_CMD} npm run build)
      else
        echo "Using current frontend/dist for preview on 0.0.0.0:${FRONTEND_PORT}"
      fi
      ;;
    dev)
      echo "Starting Vite dev server on 0.0.0.0:${FRONTEND_PORT}"
      ;;
    *)
      echo "FRONTEND_MODE must be preview or dev" >&2
      exit 2
      ;;
  esac
}

prepare_backend_env() {
  export TTS_PROVIDER="${TTS_PROVIDER:-local}"
  export API_KEYS="${API_KEYS:-}"
  export PUBLIC_DEMO_PROFILE
  export REQUIRE_REAL_TTS

  local name
  for name in "${BACKEND_ENV_NAMES[@]}"; do
    if [[ -v "${name}" ]]; then
      export "${name}"
    fi
  done
}

real_tts_required() {
  [[ "${PUBLIC_DEMO_PROFILE}" == "production" || "${REQUIRE_REAL_TTS}" == "1" ]]
}

validate_backend_env() {
  if ! real_tts_required; then
    return 0
  fi

  case "${TTS_PROVIDER}" in
    openai)
      if [[ -z "${OPENAI_API_KEY:-}" ]]; then
        echo "Refusing to start production public profile: TTS_PROVIDER=openai requires OPENAI_API_KEY to be set." >&2
        return 1
      fi
      ;;
    google)
      if [[ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
        echo "Refusing to start production public profile: TTS_PROVIDER=google requires GOOGLE_APPLICATION_CREDENTIALS to be set." >&2
        return 1
      fi
      ;;
    auto)
      if [[ -z "${OPENAI_API_KEY:-}" && -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
        echo "Refusing to start production public profile: TTS_PROVIDER=auto would fall back to local without real TTS credentials." >&2
        return 1
      fi
      ;;
    local|"")
      echo "Refusing to start production public profile: TTS_PROVIDER=${TTS_PROVIDER:-unset} would use local fallback audio." >&2
      return 1
      ;;
    *)
      echo "Refusing to start production public profile: unsupported TTS_PROVIDER=${TTS_PROVIDER}." >&2
      return 1
      ;;
  esac
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local tries="${3:-30}"

  for _ in $(seq 1 "${tries}"); do
    if curl -fsS --max-time 2 "${url}" >/dev/null 2>&1; then
      echo "${name} is reachable at ${url}"
      return 0
    fi
    sleep 1
  done

  echo "${name} did not become reachable at ${url}" >&2
  return 1
}

start() {
  mkdir -p "${ROOT_DIR}/logs" "${ROOT_DIR}/data/audio" "${ROOT_DIR}/data/video-jobs" "${ROOT_DIR}/data/artifacts" "${ROOT_DIR}/mlruns" "${ROOT_DIR}/artifacts/mlflow"
  prepare_backend_env
  validate_backend_env
  prepare_frontend
  docker network inspect "${NETWORK}" >/dev/null 2>&1 || docker network create "${NETWORK}" >/dev/null
  docker rm -f voice-ai-mlflow voice-ai-backend >/dev/null 2>&1 || true
  tmux -L "${TMUX_SOCKET}" kill-session -t voice-ai-mlflow >/dev/null 2>&1 || true
  tmux -L "${TMUX_SOCKET}" kill-session -t voice-ai-backend >/dev/null 2>&1 || true
  tmux -L "${TMUX_SOCKET}" kill-session -t voice-ai-frontend >/dev/null 2>&1 || true

  tmux -L "${TMUX_SOCKET}" new-session -d -s voice-ai-mlflow -c "${ROOT_DIR}" \
    "${TASKSET_CMD} docker run --rm --name voice-ai-mlflow --network ${NETWORK} -p 0.0.0.0:${MLFLOW_PORT}:5000 -v ${ROOT_DIR}/mlruns:/mlflow -v ${ROOT_DIR}/artifacts/mlflow:/mlflow/artifacts ${MLFLOW_IMAGE} mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:////mlflow/mlflow.db --default-artifact-root /mlflow/artifacts --serve-artifacts --allowed-hosts ${MLFLOW_ALLOWED_HOSTS@Q} 2>&1 | tee -a logs/mlflow.log"

  local backend_tmux_env=()
  local env_name
  for env_name in "${BACKEND_ENV_NAMES[@]}"; do
    backend_tmux_env+=("-e" "${env_name}")
  done

  tmux -L "${TMUX_SOCKET}" new-session -d -s voice-ai-backend -c "${ROOT_DIR}" "${backend_tmux_env[@]}" \
    "${TASKSET_CMD} docker run --rm --name voice-ai-backend --network ${NETWORK} -p 0.0.0.0:${API_PORT}:8080 -e ENVIRONMENT=local -e PORT=8080 -e TTS_PROVIDER -e API_KEYS -e OPENAI_API_KEY -e OPENAI_TTS_MODEL -e OPENAI_TTS_VOICE -e OPENAI_TTS_RESPONSE_FORMAT -e GCP_PROJECT_ID -e GOOGLE_APPLICATION_CREDENTIALS -e GOOGLE_CLOUD_REGION -e PUBLIC_DEMO_PROFILE -e REQUIRE_REAL_TTS -e CORS_ALLOW_ORIGINS=http://localhost:${FRONTEND_PORT},http://${SERVER_IP}:${FRONTEND_PORT} -e AUDIO_STORAGE_DIR=/app/data/audio -e AUDIO_BASE_URL=http://${SERVER_IP}:${API_PORT}/audio -e MLFLOW_TRACKING_URI=http://voice-ai-mlflow:5000 -e MLFLOW_EXPERIMENT_NAME=voice-ai-tts-synthesis -e MLFLOW_VIDEO_EXPERIMENT_NAME=voice-ai-video-localization -e LOCALIZATION_PROVIDER=local -e VIDEO_JOBS_DIR=/app/data/video-jobs -e FFMPEG_PATH=ffmpeg -v ${ROOT_DIR}/data/audio:/app/data/audio -v ${ROOT_DIR}/data/video-jobs:/app/data/video-jobs -v ${ROOT_DIR}/data/artifacts:/app/data/artifacts -v ${ROOT_DIR}/artifacts/mlflow:/mlflow/artifacts ${IMAGE} 2>&1 | tee -a logs/backend.log"

  if [[ "${FRONTEND_MODE}" == "preview" ]]; then
    tmux -L "${TMUX_SOCKET}" new-session -d -s voice-ai-frontend -c "${ROOT_DIR}/frontend" \
      "${TASKSET_CMD} npm run preview -- --host 0.0.0.0 --port ${FRONTEND_PORT} 2>&1 | tee -a ../logs/frontend.log"
  else
    tmux -L "${TMUX_SOCKET}" new-session -d -s voice-ai-frontend -c "${ROOT_DIR}/frontend" \
      "${TASKSET_CMD} npm run dev -- --port ${FRONTEND_PORT} 2>&1 | tee -a ../logs/frontend.log"
  fi

  wait_for_url "backend health" "http://127.0.0.1:${API_PORT}/healthz" 45
  wait_for_url "frontend" "http://127.0.0.1:${FRONTEND_PORT}/" 30
}

stop() {
  tmux -L "${TMUX_SOCKET}" kill-session -t voice-ai-frontend >/dev/null 2>&1 || true
  tmux -L "${TMUX_SOCKET}" kill-session -t voice-ai-backend >/dev/null 2>&1 || true
  tmux -L "${TMUX_SOCKET}" kill-session -t voice-ai-mlflow >/dev/null 2>&1 || true
  docker rm -f voice-ai-backend voice-ai-mlflow >/dev/null 2>&1 || true
}

restart() {
  prepare_backend_env
  validate_backend_env
  stop
  start
}

backend_runtime_status() {
  if ! docker ps --format '{{.Names}}' | grep -qx 'voice-ai-backend'; then
    return 0
  fi

  docker exec voice-ai-backend sh -c 'if [ -n "${TTS_PROVIDER:-}" ]; then echo "backend TTS_PROVIDER: set"; else echo "backend TTS_PROVIDER: unset"; fi' 2>/dev/null || true
  docker exec voice-ai-backend sh -c 'if [ -n "${OPENAI_API_KEY:-}" ]; then echo "backend OPENAI_API_KEY: set"; else echo "backend OPENAI_API_KEY: unset"; fi' 2>/dev/null || true
  docker exec voice-ai-backend sh -c 'if [ -n "${OPENAI_TTS_MODEL:-}" ]; then echo "backend OPENAI_TTS_MODEL: set"; else echo "backend OPENAI_TTS_MODEL: unset"; fi' 2>/dev/null || true
  docker exec voice-ai-backend sh -c 'if [ -n "${OPENAI_TTS_VOICE:-}" ]; then echo "backend OPENAI_TTS_VOICE: set"; else echo "backend OPENAI_TTS_VOICE: unset"; fi' 2>/dev/null || true
  docker exec voice-ai-backend sh -c 'if [ -n "${OPENAI_TTS_RESPONSE_FORMAT:-}" ]; then echo "backend OPENAI_TTS_RESPONSE_FORMAT: set"; else echo "backend OPENAI_TTS_RESPONSE_FORMAT: unset"; fi' 2>/dev/null || true
  docker exec voice-ai-backend sh -c 'if [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]; then echo "backend GOOGLE_APPLICATION_CREDENTIALS: set"; else echo "backend GOOGLE_APPLICATION_CREDENTIALS: unset"; fi' 2>/dev/null || true
  docker exec voice-ai-backend sh -c 'if [ -n "${PUBLIC_DEMO_PROFILE:-}" ]; then echo "backend PUBLIC_DEMO_PROFILE: set"; else echo "backend PUBLIC_DEMO_PROFILE: unset"; fi' 2>/dev/null || true
  docker exec voice-ai-backend sh -c 'if [ "${REQUIRE_REAL_TTS:-0}" = "1" ]; then echo "backend REQUIRE_REAL_TTS: set"; else echo "backend REQUIRE_REAL_TTS: unset"; fi' 2>/dev/null || true
}

status() {
  echo "tmux socket: ${TMUX_SOCKET}"
  if [[ "${RUNTIME_ENV_LOADED}" == "1" ]]; then
    echo "runtime env file: loaded"
  else
    echo "runtime env file: not loaded"
  fi
  echo "taskset: ${TASKSET_CMD:-disabled}"
  echo "backend image: ${IMAGE}"
  echo "frontend mode: ${FRONTEND_MODE}; port: ${FRONTEND_PORT}"
  echo "mlflow allowed hosts: ${MLFLOW_ALLOWED_HOSTS}"
  tmux -L "${TMUX_SOCKET}" list-sessions 2>/dev/null || true
  docker ps --filter "name=voice-ai" --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
  backend_runtime_status
  curl -fsSI --max-time 3 "http://127.0.0.1:${FRONTEND_PORT}/" | sed -n '1,4p' || true
  curl -fsS --max-time 3 "http://127.0.0.1:${API_PORT}/healthz" || true
  echo
}

case "${1:-status}" in
  start) start ;;
  stop) stop ;;
  restart) restart ;;
  status) status ;;
  *) echo "Usage: $0 {start|stop|restart|status}" >&2; exit 2 ;;
esac

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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
TASKSET_CPUSET="${TASKSET_CPUSET:-0-3}"

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
  prepare_frontend
  docker network inspect "${NETWORK}" >/dev/null 2>&1 || docker network create "${NETWORK}" >/dev/null
  docker rm -f voice-ai-mlflow voice-ai-backend >/dev/null 2>&1 || true
  tmux -L "${TMUX_SOCKET}" kill-session -t voice-ai-mlflow >/dev/null 2>&1 || true
  tmux -L "${TMUX_SOCKET}" kill-session -t voice-ai-backend >/dev/null 2>&1 || true
  tmux -L "${TMUX_SOCKET}" kill-session -t voice-ai-frontend >/dev/null 2>&1 || true

  tmux -L "${TMUX_SOCKET}" new-session -d -s voice-ai-mlflow -c "${ROOT_DIR}" \
    "${TASKSET_CMD} docker run --rm --name voice-ai-mlflow --network ${NETWORK} -p 0.0.0.0:${MLFLOW_PORT}:5000 -v ${ROOT_DIR}/mlruns:/mlflow -v ${ROOT_DIR}/artifacts/mlflow:/mlflow/artifacts ${MLFLOW_IMAGE} mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:////mlflow/mlflow.db --default-artifact-root /mlflow/artifacts --serve-artifacts 2>&1 | tee -a logs/mlflow.log"

  tmux -L "${TMUX_SOCKET}" new-session -d -s voice-ai-backend -c "${ROOT_DIR}" \
    "${TASKSET_CMD} docker run --rm --name voice-ai-backend --network ${NETWORK} -p 0.0.0.0:${API_PORT}:8080 -e ENVIRONMENT=local -e PORT=8080 -e TTS_PROVIDER=local -e API_KEYS=\${API_KEYS:-} -e CORS_ALLOW_ORIGINS=http://localhost:${FRONTEND_PORT},http://${SERVER_IP}:${FRONTEND_PORT} -e AUDIO_STORAGE_DIR=/app/data/audio -e AUDIO_BASE_URL=http://${SERVER_IP}:${API_PORT}/audio -e MLFLOW_TRACKING_URI=http://voice-ai-mlflow:5000 -e MLFLOW_EXPERIMENT_NAME=voice-ai-tts-synthesis -e MLFLOW_VIDEO_EXPERIMENT_NAME=voice-ai-video-localization -e LOCALIZATION_PROVIDER=local -e VIDEO_JOBS_DIR=/app/data/video-jobs -e FFMPEG_PATH=ffmpeg -v ${ROOT_DIR}/data/audio:/app/data/audio -v ${ROOT_DIR}/data/video-jobs:/app/data/video-jobs -v ${ROOT_DIR}/data/artifacts:/app/data/artifacts ${IMAGE} 2>&1 | tee -a logs/backend.log"

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

status() {
  echo "tmux socket: ${TMUX_SOCKET}"
  echo "taskset: ${TASKSET_CMD:-disabled}"
  echo "backend image: ${IMAGE}"
  echo "frontend mode: ${FRONTEND_MODE}; port: ${FRONTEND_PORT}"
  tmux -L "${TMUX_SOCKET}" list-sessions 2>/dev/null || true
  docker ps --filter "name=voice-ai" --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
  curl -fsSI --max-time 3 "http://127.0.0.1:${FRONTEND_PORT}/" | sed -n '1,4p' || true
  curl -fsS --max-time 3 "http://127.0.0.1:${API_PORT}/healthz" || true
  echo
}

case "${1:-status}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  *) echo "Usage: $0 {start|stop|restart|status}" >&2; exit 2 ;;
esac

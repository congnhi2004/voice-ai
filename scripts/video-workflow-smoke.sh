#!/usr/bin/env bash
set -euo pipefail

IMAGE="${1:-voice-ai:local}"

echo "Checking FFmpeg in ${IMAGE}"
docker run --rm --entrypoint ffmpeg "${IMAGE}" -version | sed -n '1p'

echo "Checking FFprobe in ${IMAGE}"
docker run --rm --entrypoint ffprobe "${IMAGE}" -version | sed -n '1p'

if [[ -x scripts/app-video-smoke.sh ]]; then
  echo "Running app video smoke hook"
  scripts/app-video-smoke.sh "${IMAGE}"
else
  echo "No app video smoke hook found; FFmpeg/FFprobe container checks completed."
fi

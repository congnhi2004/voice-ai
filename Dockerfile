# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    ENVIRONMENT=production \
    AUDIO_STORAGE_DIR=/app/data/audio \
    VIDEO_STORAGE_DIR=/app/data/video \
    ARTIFACT_STORAGE_DIR=/app/data/artifacts \
    STATIC_FRONTEND_DIR=/app/frontend/dist

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates espeak-ng ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app /app/app
COPY scripts/docker-entrypoint.sh /app/scripts/docker-entrypoint.sh

RUN chmod +x /app/scripts/docker-entrypoint.sh \
    && mkdir -p "${AUDIO_STORAGE_DIR}" "${VIDEO_STORAGE_DIR}" "${ARTIFACT_STORAGE_DIR}" "${STATIC_FRONTEND_DIR}" /app/logs /app/mlruns /app/artifacts/mlflow \
    && adduser --disabled-password --gecos "" --home /app appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/healthz" || exit 1

# Assumes the FastAPI application object will be app.main:app.
# Cloud Run injects PORT; uvicorn binds all interfaces for container traffic.
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    service_name: str = "voice-ai"
    version: str = "0.1.0"
    environment: str = "local"
    port: int = 8080
    tts_provider: str = "auto"
    gcp_project_id: str | None = None
    google_application_credentials: str | None = None
    openai_api_key: str | None = None
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "coral"
    openai_tts_response_format: str = "wav"
    audio_storage_dir: Path = Path("data/audio")
    audio_base_url: str = "http://localhost:8080"
    api_keys: tuple[str, ...] = ()
    cors_allow_origins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:8080")
    max_input_chars: int = 5000
    log_level: str = "INFO"
    mlflow_tracking_uri: str | None = None
    mlflow_experiment_name: str = "voice-ai-tts-synthesis"
    mlflow_log_audio_artifacts: bool = True
    log_raw_text: bool = False
    video_jobs_dir: Path = Path("data/video-jobs")
    localization_provider: str = "local"
    ffmpeg_path: str = "ffmpeg"

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_keys)

    @property
    def service_base_url(self) -> str:
        if self.audio_base_url.endswith("/audio"):
            return self.audio_base_url[: -len("/audio")]
        return self.audio_base_url

    @property
    def audio_public_base_url(self) -> str:
        if self.audio_base_url.endswith("/audio"):
            return self.audio_base_url
        return f"{self.audio_base_url}/audio"


def load_settings() -> Settings:
    return Settings(
        environment=os.getenv("ENVIRONMENT", "local"),
        port=int(os.getenv("PORT", "8080")),
        tts_provider=os.getenv("TTS_PROVIDER", "auto").lower(),
        gcp_project_id=os.getenv("GCP_PROJECT_ID"),
        google_application_credentials=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_tts_model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
        openai_tts_voice=os.getenv("OPENAI_TTS_VOICE", "coral"),
        openai_tts_response_format=os.getenv("OPENAI_TTS_RESPONSE_FORMAT", "wav").lower(),
        audio_storage_dir=Path(os.getenv("AUDIO_STORAGE_DIR", "data/audio")),
        audio_base_url=os.getenv("AUDIO_BASE_URL", "http://localhost:8080").rstrip("/"),
        api_keys=tuple(_split_csv(os.getenv("API_KEYS"))),
        cors_allow_origins=tuple(_split_csv(os.getenv("CORS_ALLOW_ORIGINS")) or ["http://localhost:3000", "http://localhost:8080"]),
        max_input_chars=int(os.getenv("MAX_INPUT_CHARS", "5000")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        mlflow_tracking_uri=os.getenv("MLFLOW_TRACKING_URI"),
        mlflow_experiment_name=os.getenv("MLFLOW_EXPERIMENT_NAME", "voice-ai-tts-synthesis"),
        mlflow_log_audio_artifacts=os.getenv("MLFLOW_LOG_AUDIO_ARTIFACTS", "true").lower() in {"1", "true", "yes"},
        log_raw_text=os.getenv("LOG_RAW_TEXT", "false").lower() in {"1", "true", "yes"},
        video_jobs_dir=Path(os.getenv("VIDEO_JOBS_DIR", "data/video-jobs")),
        localization_provider=os.getenv("LOCALIZATION_PROVIDER", "local").lower(),
        ffmpeg_path=os.getenv("FFMPEG_PATH", "ffmpeg"),
    )

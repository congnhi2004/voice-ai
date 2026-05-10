from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

OPENAI_TTS_INPUT_MAX_CHARS = 4096
OPENAI_AUDIO_UPLOAD_LIMIT_BYTES = 25 * 1024 * 1024
LOCAL_DEV_JWT_SECRET = "local-dev-only-change-auth-jwt-secret-before-production"


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
    openai_tts_voice: str = "marin"
    openai_tts_response_format: str = "wav"
    openai_transcription_model: str = "gpt-4o-mini-transcribe"
    openai_translation_model: str = "gpt-4o-mini"
    espeak_ng_path: str = "espeak-ng"
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
    storage_provider: str = "local"
    audio_storage_mode: str = "local"
    video_storage_mode: str = "local"
    video_jobs_dir: Path = Path("data/video-jobs")
    localization_provider: str = "auto"
    ffmpeg_path: str = "ffmpeg"
    gcs_audio_bucket: str | None = None
    gcs_artifact_bucket: str | None = None
    gcs_audio_prefix: str = "voice-ai/audio"
    gcs_source_video_prefix: str = "voice-ai/video/source"
    gcs_rendered_video_prefix: str = "voice-ai/video/rendered"
    gcs_intermediate_prefix: str = "voice-ai/video/intermediate"
    signed_url_ttl_seconds: int = 3600
    auth_storage_path: Path = Path("data/auth-billing.sqlite3")
    auth_jwt_secret: str | None = None
    auth_jwt_algorithm: str = "HS256"
    auth_access_token_expire_minutes: int = 60
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_success_url: str | None = None
    stripe_cancel_url: str | None = None
    stripe_portal_return_url: str | None = None
    stripe_price_starter: str | None = None
    stripe_price_pro: str | None = None

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_keys)

    @property
    def production_like(self) -> bool:
        return self.environment.lower() in {"production", "prod", "staging", "public"}

    @property
    def jwt_secret(self) -> str | None:
        if self.auth_jwt_secret:
            return self.auth_jwt_secret
        if not self.production_like:
            return LOCAL_DEV_JWT_SECRET
        return None

    @property
    def auth_configured(self) -> bool:
        return bool(self.jwt_secret)

    @property
    def production_identity_configured(self) -> bool:
        return bool(self.production_like and self.auth_jwt_secret and self.auth_jwt_secret != LOCAL_DEV_JWT_SECRET)

    def tts_input_max_chars_for_provider(self, provider_name: str) -> int:
        if provider_name == "openai":
            return min(self.max_input_chars, OPENAI_TTS_INPUT_MAX_CHARS)
        return self.max_input_chars

    @property
    def stripe_configured(self) -> bool:
        return bool(
            self.stripe_secret_key
            and self.stripe_webhook_secret
            and self.stripe_success_url
            and self.stripe_cancel_url
            and self.stripe_portal_return_url
        )

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

    @property
    def audio_storage_provider(self) -> str:
        return self.storage_provider if self.storage_provider != "local" else self.audio_storage_mode

    @property
    def video_artifact_storage_provider(self) -> str:
        return self.storage_provider if self.storage_provider != "local" else self.video_storage_mode


def load_settings() -> Settings:
    storage_provider = os.getenv("STORAGE_PROVIDER", "local").lower()
    return Settings(
        environment=os.getenv("ENVIRONMENT", "local"),
        port=int(os.getenv("PORT", "8080")),
        tts_provider=os.getenv("TTS_PROVIDER", "auto").lower(),
        gcp_project_id=os.getenv("GCP_PROJECT_ID"),
        google_application_credentials=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_tts_model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
        openai_tts_voice=os.getenv("OPENAI_TTS_VOICE", "marin"),
        openai_tts_response_format=os.getenv("OPENAI_TTS_RESPONSE_FORMAT", "wav").lower(),
        openai_transcription_model=os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"),
        openai_translation_model=os.getenv("OPENAI_TRANSLATION_MODEL", "gpt-4o-mini"),
        espeak_ng_path=os.getenv("ESPEAK_NG_PATH", "espeak-ng"),
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
        storage_provider=storage_provider,
        audio_storage_mode=os.getenv("AUDIO_STORAGE_MODE", storage_provider).lower(),
        video_storage_mode=os.getenv("VIDEO_STORAGE_MODE", storage_provider).lower(),
        video_jobs_dir=Path(os.getenv("VIDEO_JOBS_DIR", "data/video-jobs")),
        localization_provider=os.getenv("LOCALIZATION_PROVIDER", "auto").lower(),
        ffmpeg_path=os.getenv("FFMPEG_PATH", "ffmpeg"),
        gcs_audio_bucket=os.getenv("GCS_AUDIO_BUCKET") or None,
        gcs_artifact_bucket=os.getenv("GCS_ARTIFACT_BUCKET") or None,
        gcs_audio_prefix=os.getenv("GCS_AUDIO_PREFIX", "voice-ai/audio").strip("/"),
        gcs_source_video_prefix=os.getenv("GCS_SOURCE_VIDEO_PREFIX", "voice-ai/video/source").strip("/"),
        gcs_rendered_video_prefix=os.getenv("GCS_RENDERED_VIDEO_PREFIX", "voice-ai/video/rendered").strip("/"),
        gcs_intermediate_prefix=os.getenv("GCS_INTERMEDIATE_PREFIX", "voice-ai/video/intermediate").strip("/"),
        signed_url_ttl_seconds=int(os.getenv("SIGNED_URL_TTL_SECONDS", "3600")),
        auth_storage_path=Path(os.getenv("AUTH_STORAGE_PATH", "data/auth-billing.sqlite3")),
        auth_jwt_secret=os.getenv("AUTH_JWT_SECRET"),
        auth_jwt_algorithm=os.getenv("AUTH_JWT_ALGORITHM", "HS256"),
        auth_access_token_expire_minutes=int(os.getenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "60")),
        stripe_secret_key=os.getenv("STRIPE_SECRET_KEY"),
        stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET"),
        stripe_success_url=os.getenv("STRIPE_SUCCESS_URL"),
        stripe_cancel_url=os.getenv("STRIPE_CANCEL_URL"),
        stripe_portal_return_url=os.getenv("STRIPE_PORTAL_RETURN_URL"),
        stripe_price_starter=os.getenv("STRIPE_PRICE_STARTER"),
        stripe_price_pro=os.getenv("STRIPE_PRICE_PRO"),
    )

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass

from .config import Settings
from .models import (
    CapabilitiesResponse,
    DemoAuthResponse,
    DemoUser,
    DemoWorkspaceStatus,
    PlanFeature,
    PricingPlan,
)


def pricing_plans() -> list[PricingPlan]:
    return [
        PricingPlan(
            id="demo-free",
            name="Demo Free",
            monthly_price_usd=0,
            included_minutes=20,
            overage_price_usd_per_minute=None,
            features=[
                PlanFeature(key="local_tts", label="Local demo TTS"),
                PlanFeature(key="video_demo", label="Video localization demo workflow"),
                PlanFeature(key="subtitles", label="SRT and VTT subtitle artifacts"),
            ],
        ),
        PricingPlan(
            id="starter-placeholder",
            name="Starter Placeholder",
            monthly_price_usd=49,
            included_minutes=500,
            overage_price_usd_per_minute=0.18,
            features=[
                PlanFeature(key="google_tts_ready", label="Google TTS provider support"),
                PlanFeature(key="mlflow_tracking", label="MLflow metadata tracking"),
                PlanFeature(key="api_access", label="API access with optional API key auth"),
            ],
        ),
    ]


def capabilities(settings: Settings, *, provider_name: str, ffmpeg_available: bool) -> CapabilitiesResponse:
    return CapabilitiesResponse(
        service=settings.service_name,
        environment=settings.environment,
        mode="demo" if settings.localization_provider == "local" else settings.localization_provider,
        tts={
            "available": True,
            "providers": ["local", "google", "openai"],
            "active_provider": provider_name,
            "encodings": ["MP3", "LINEAR16", "OGG_OPUS"],
            "local_fallback": True,
        },
        video_localization={
            "available": True,
            "source_languages": ["en-US", "en", "zh-CN", "zh"],
            "target_languages": ["vi", "vi-VN"],
            "demo_mode": settings.localization_provider == "local",
            "artifacts": ["source_video", "transcript", "subtitles_srt", "subtitles_vtt", "voiceover_audio", "localized_video"],
            "ffmpeg_available": ffmpeg_available,
        },
        auth={
            "available": True,
            "mode": "local-demo",
            "production_identity": False,
        },
        billing={
            "available": False,
            "mode": "pricing-copy-only",
            "production_billing": False,
        },
    )


def demo_workspace_status(settings: Settings, *, ffmpeg_available: bool) -> DemoWorkspaceStatus:
    return DemoWorkspaceStatus(
        workspace_id="demo",
        label="Local Demo Workspace",
        demo_only=True,
        tts_jobs_available=True,
        video_jobs_available=True,
        storage_mode="local-filesystem",
        mlflow_configured=bool(settings.mlflow_tracking_uri),
        ffmpeg_available=ffmpeg_available,
        notes=[
            "No production billing is connected.",
            "Demo auth is in-memory and resets when the process restarts.",
            "Cloud STT/Translation for video localization is not enabled in this local demo path.",
        ],
    )


@dataclass
class StoredDemoUser:
    user: DemoUser
    salt: str
    password_hash: str


class DemoAuthStore:
    def __init__(self) -> None:
        self._users_by_email: dict[str, StoredDemoUser] = {}
        self._tokens: dict[str, str] = {}

    def register(self, *, email: str, password: str, name: str | None) -> DemoAuthResponse:
        normalized = email.strip().lower()
        if normalized in self._users_by_email:
            raise ValueError("demo_user_exists")
        user = DemoUser(id=f"usr_{uuid.uuid4().hex}", email=normalized, name=name)
        salt = secrets.token_hex(16)
        self._users_by_email[normalized] = StoredDemoUser(user=user, salt=salt, password_hash=self._hash(password, salt))
        return self._issue(user)

    def login(self, *, email: str, password: str) -> DemoAuthResponse:
        normalized = email.strip().lower()
        stored = self._users_by_email.get(normalized)
        if not stored or not secrets.compare_digest(stored.password_hash, self._hash(password, stored.salt)):
            raise ValueError("invalid_demo_credentials")
        return self._issue(stored.user)

    def me(self, token: str) -> DemoUser | None:
        email = self._tokens.get(token)
        if not email:
            return None
        stored = self._users_by_email.get(email)
        return stored.user if stored else None

    def logout(self, token: str) -> bool:
        return self._tokens.pop(token, None) is not None

    def _issue(self, user: DemoUser) -> DemoAuthResponse:
        token = f"demo_{secrets.token_urlsafe(32)}"
        self._tokens[token] = user.email
        return DemoAuthResponse(user=user, access_token=token)

    def _hash(self, password: str, salt: str) -> str:
        return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()

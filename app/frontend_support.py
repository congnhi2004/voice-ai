from __future__ import annotations

from .auth_billing import available_plans
from .config import Settings
from .models import (
    CapabilitiesResponse,
    DemoWorkspaceStatus,
    PricingPlan,
)


def pricing_plans(settings: Settings) -> list[PricingPlan]:
    return available_plans(settings)


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
            "mode": "jwt-password",
            "production_identity": settings.auth_configured,
            "storage": "sqlite",
        },
        billing={
            "available": settings.stripe_configured,
            "mode": "stripe-subscriptions" if settings.stripe_configured else "not-configured",
            "production_billing": settings.stripe_configured,
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
            "Local SQLite auth and billing state is for development; production requires a durable managed database.",
            "Stripe billing returns not-configured errors until Stripe secrets and URLs are set.",
            "Cloud STT/Translation for video localization is not enabled in this local demo path.",
        ],
    )

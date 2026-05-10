from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


AudioEncoding = Literal["MP3", "LINEAR16", "OGG_OPUS"]
Gender = Literal["MALE", "FEMALE", "NEUTRAL", "SSML_VOICE_GENDER_UNSPECIFIED"]


class VoiceSelection(BaseModel):
    language_code: str = Field(..., min_length=2, examples=["en-US"])
    name: str | None = Field(default=None, examples=["en-US-Standard-C"])
    ssml_gender: Gender | None = None


class AudioOptions(BaseModel):
    encoding: AudioEncoding = "MP3"
    speaking_rate: float = Field(default=1.0, ge=0.25, le=4.0)
    pitch: float = Field(default=0.0, ge=-20.0, le=20.0)
    volume_gain_db: float = Field(default=0.0, ge=-96.0, le=16.0)
    sample_rate_hz: int = Field(default=24000, ge=8000, le=48000)


class SynthesizeRequest(BaseModel):
    text: str | None = Field(default=None)
    ssml: str | None = Field(default=None)
    voice: VoiceSelection
    audio: AudioOptions = Field(default_factory=AudioOptions)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def exactly_one_input(self) -> "SynthesizeRequest":
        has_text = bool(self.text)
        has_ssml = bool(self.ssml)
        if has_text == has_ssml:
            raise ValueError("Exactly one of text or ssml is required.")
        return self

    @property
    def input_text(self) -> str:
        return self.text if self.text is not None else self.ssml or ""

    @property
    def input_type(self) -> str:
        return "text" if self.text is not None else "ssml"


class VoiceInfo(BaseModel):
    name: str
    language_codes: list[str]
    ssml_gender: str
    natural_sample_rate_hz: int
    supported_encodings: list[AudioEncoding]


class ProviderInfo(BaseModel):
    name: str
    fallback: bool
    model: str


class AudioInfo(BaseModel):
    encoding: str
    bytes: int
    sample_rate_hz: int
    checksum_sha256: str
    content_type: str


class ObservabilityInfo(BaseModel):
    request_id: str
    mlflow_run_id: str | None = None
    warnings: list[str] = Field(default_factory=list)


class SynthesizeResponse(BaseModel):
    job_id: str
    status: Literal["succeeded"]
    audio_url: str
    audio_path: str
    duration_ms: int
    latency_ms: int
    provider: ProviderInfo
    voice: VoiceSelection
    audio: AudioInfo
    observability: ObservabilityInfo
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubtitleSegment(BaseModel):
    index: int
    start_ms: int
    end_ms: int
    source_text: str
    translated_text: str


class VideoArtifact(BaseModel):
    kind: str
    path: str
    url: str
    bytes: int
    checksum_sha256: str
    content_type: str


class VideoLocalizationStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    source_language: str
    target_language: str
    provider: ProviderInfo
    input_filename: str
    input_bytes: int
    transcript_chars: int
    translated_chars: int
    segments: list[SubtitleSegment]
    artifacts: list[VideoArtifact]
    latency_ms: int
    observability: ObservabilityInfo
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class PlanFeature(BaseModel):
    key: str
    label: str


class PricingPlan(BaseModel):
    id: str
    name: str
    monthly_price_usd: int
    included_minutes: int
    overage_price_usd_per_minute: float | None
    features: list[PlanFeature]
    demo_only: bool = True


class CapabilitiesResponse(BaseModel):
    service: str
    environment: str
    mode: str
    tts: dict[str, Any]
    video_localization: dict[str, Any]
    auth: dict[str, Any]
    billing: dict[str, Any]


class DemoWorkspaceStatus(BaseModel):
    workspace_id: str
    label: str
    demo_only: bool
    tts_jobs_available: bool
    video_jobs_available: bool
    storage_mode: str
    mlflow_configured: bool
    ffmpeg_available: bool
    notes: list[str]


class DemoAuthRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    name: str | None = None


class DemoLoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class DemoUser(BaseModel):
    id: str
    email: str
    name: str | None = None
    demo_only: bool = True


class DemoAuthResponse(BaseModel):
    user: DemoUser
    access_token: str
    token_type: str = "bearer"
    demo_only: bool = True
    warning: str = "Local demo auth only. Not production identity."

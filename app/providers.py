from __future__ import annotations

import base64
import hashlib
import math
import struct
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .models import SynthesizeRequest, VoiceInfo


@dataclass(frozen=True)
class ProviderHealth:
    name: str
    ready: bool
    detail: str | None = None


@dataclass(frozen=True)
class ProviderSynthesisResult:
    provider_name: str
    fallback: bool
    model: str
    audio_bytes: bytes
    extension: str
    content_type: str
    duration_ms: int
    provider_latency_ms: int


class TTSProvider:
    name = "base"
    fallback = False
    model = "unknown"

    def list_voices(self, language_code: str | None = None) -> list[VoiceInfo]:
        raise NotImplementedError

    def synthesize(self, request: SynthesizeRequest) -> ProviderSynthesisResult:
        raise NotImplementedError

    def healthcheck(self) -> ProviderHealth:
        raise NotImplementedError


class LocalFallbackProvider(TTSProvider):
    name = "local"
    fallback = True
    model = "deterministic-wav-tone-demo"

    _voices = [
        VoiceInfo(
            name="local-en-US-test-voice",
            language_codes=["en-US"],
            ssml_gender="NEUTRAL",
            natural_sample_rate_hz=24000,
            supported_encodings=["LINEAR16", "MP3", "OGG_OPUS"],
        ),
        VoiceInfo(
            name="local-vi-VN-test-voice",
            language_codes=["vi-VN"],
            ssml_gender="NEUTRAL",
            natural_sample_rate_hz=24000,
            supported_encodings=["LINEAR16", "MP3", "OGG_OPUS"],
        ),
    ]

    def list_voices(self, language_code: str | None = None) -> list[VoiceInfo]:
        if not language_code:
            return self._voices
        return [voice for voice in self._voices if language_code in voice.language_codes]

    def synthesize(self, request: SynthesizeRequest) -> ProviderSynthesisResult:
        started = time.perf_counter()
        audio_bytes, duration_ms = self._make_wav(request.input_text, request.audio.sample_rate_hz)
        return ProviderSynthesisResult(
            provider_name=self.name,
            fallback=True,
            model=self.model,
            audio_bytes=audio_bytes,
            extension="wav",
            content_type="audio/wav",
            duration_ms=duration_ms,
            provider_latency_ms=max(1, int((time.perf_counter() - started) * 1000)),
        )

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(name=self.name, ready=True)

    def _make_wav(self, text: str, sample_rate_hz: int) -> tuple[bytes, int]:
        import io

        digest = hashlib.sha256(text.encode("utf-8")).digest()
        frequency = 220 + digest[0]
        duration_seconds = min(2.0, max(0.4, 0.05 * max(1, len(text))))
        frame_count = int(sample_rate_hz * duration_seconds)
        amplitude = 12000
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate_hz)
            for frame in range(frame_count):
                envelope = min(1.0, frame / max(1, int(sample_rate_hz * 0.03)))
                sample = int(amplitude * envelope * math.sin(2 * math.pi * frequency * frame / sample_rate_hz))
                wav.writeframesraw(struct.pack("<h", sample))
        return buffer.getvalue(), int(duration_seconds * 1000)


class GoogleTTSProvider(TTSProvider):
    name = "google"
    fallback = False
    model = "cloud-text-to-speech"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        self._import_error: str | None = None
        try:
            from google.cloud import texttospeech

            self._texttospeech = texttospeech
        except Exception as exc:  # pragma: no cover - depends on optional dependency install
            self._texttospeech = None
            self._import_error = str(exc)

    def _get_client(self):
        if self._texttospeech is None:
            raise RuntimeError(f"google-cloud-texttospeech unavailable: {self._import_error}")
        if self._client is None:
            self._client = self._texttospeech.TextToSpeechClient()
        return self._client

    def list_voices(self, language_code: str | None = None) -> list[VoiceInfo]:
        response = self._get_client().list_voices(language_code=language_code)
        voices = []
        for voice in response.voices:
            gender = self._texttospeech.SsmlVoiceGender(voice.ssml_gender).name
            voices.append(
                VoiceInfo(
                    name=voice.name,
                    language_codes=list(voice.language_codes),
                    ssml_gender=gender,
                    natural_sample_rate_hz=voice.natural_sample_rate_hertz,
                    supported_encodings=["MP3", "LINEAR16", "OGG_OPUS"],
                )
            )
        return voices

    def synthesize(self, request: SynthesizeRequest) -> ProviderSynthesisResult:
        started = time.perf_counter()
        tts = self._texttospeech
        synthesis_input = tts.SynthesisInput(text=request.text) if request.text is not None else tts.SynthesisInput(ssml=request.ssml)
        gender_name = request.voice.ssml_gender or "SSML_VOICE_GENDER_UNSPECIFIED"
        voice = tts.VoiceSelectionParams(
            language_code=request.voice.language_code,
            name=request.voice.name,
            ssml_gender=getattr(tts.SsmlVoiceGender, gender_name),
        )
        audio_config = tts.AudioConfig(
            audio_encoding=getattr(tts.AudioEncoding, request.audio.encoding),
            speaking_rate=request.audio.speaking_rate,
            pitch=request.audio.pitch,
            volume_gain_db=request.audio.volume_gain_db,
            sample_rate_hertz=request.audio.sample_rate_hz,
        )
        response = self._get_client().synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
        audio_bytes = bytes(response.audio_content)
        extension = {"MP3": "mp3", "LINEAR16": "wav", "OGG_OPUS": "ogg"}[request.audio.encoding]
        content_type = {"MP3": "audio/mpeg", "LINEAR16": "audio/wav", "OGG_OPUS": "audio/ogg"}[request.audio.encoding]
        return ProviderSynthesisResult(
            provider_name=self.name,
            fallback=False,
            model=self.model,
            audio_bytes=audio_bytes,
            extension=extension,
            content_type=content_type,
            duration_ms=0,
            provider_latency_ms=max(1, int((time.perf_counter() - started) * 1000)),
        )

    def synthesize_rest_payload(self, request: SynthesizeRequest) -> dict:
        audio_config = {
            "audioEncoding": request.audio.encoding,
            "speakingRate": request.audio.speaking_rate,
            "pitch": request.audio.pitch,
            "volumeGainDb": request.audio.volume_gain_db,
            "sampleRateHertz": request.audio.sample_rate_hz,
        }
        voice = {"languageCode": request.voice.language_code}
        if request.voice.name:
            voice["name"] = request.voice.name
        if request.voice.ssml_gender:
            voice["ssmlGender"] = request.voice.ssml_gender
        return {
            "input": {"text": request.text} if request.text is not None else {"ssml": request.ssml},
            "voice": voice,
            "audioConfig": audio_config,
        }

    def decode_rest_audio_content(self, audio_content: str) -> bytes:
        return base64.b64decode(audio_content)

    def healthcheck(self) -> ProviderHealth:
        if self._texttospeech is None:
            return ProviderHealth(name=self.name, ready=False, detail=self._import_error)
        credentials = self.settings.google_application_credentials
        if credentials and not Path(credentials).exists():
            return ProviderHealth(name=self.name, ready=False, detail="GOOGLE_APPLICATION_CREDENTIALS file does not exist")
        if self.settings.tts_provider == "google" and not credentials:
            return ProviderHealth(name=self.name, ready=False, detail="GOOGLE_APPLICATION_CREDENTIALS is not set")
        return ProviderHealth(name=self.name, ready=True)


class OpenAITTSProvider(TTSProvider):
    name = "openai"
    fallback = False

    _voice_names = ["alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse"]

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = settings.openai_tts_model
        self._client = None
        self._import_error: str | None = None
        try:
            from openai import OpenAI

            self._openai_client = OpenAI
        except Exception as exc:  # pragma: no cover - depends on optional dependency install
            self._openai_client = None
            self._import_error = str(exc)

    def _get_client(self):
        if self._openai_client is None:
            raise RuntimeError(f"openai unavailable: {self._import_error}")
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        if self._client is None:
            self._client = self._openai_client(api_key=self.settings.openai_api_key)
        return self._client

    def list_voices(self, language_code: str | None = None) -> list[VoiceInfo]:
        if language_code and language_code not in {"vi", "vi-VN", "en", "en-US"}:
            return []
        return [
            VoiceInfo(
                name=voice,
                language_codes=["vi-VN", "en-US"],
                ssml_gender="NEUTRAL",
                natural_sample_rate_hz=24000,
                supported_encodings=["MP3", "LINEAR16"],
            )
            for voice in self._voice_names
        ]

    def synthesize(self, request: SynthesizeRequest) -> ProviderSynthesisResult:
        started = time.perf_counter()
        response_format = self._response_format()
        response = self._get_client().audio.speech.create(
            model=self.settings.openai_tts_model,
            voice=self._voice_for(request),
            input=request.input_text,
            response_format=response_format,
        )
        audio_bytes = self._response_bytes(response)
        extension = "mp3" if response_format == "mp3" else "wav"
        content_type = "audio/mpeg" if response_format == "mp3" else "audio/wav"
        return ProviderSynthesisResult(
            provider_name=self.name,
            fallback=False,
            model=self.settings.openai_tts_model,
            audio_bytes=audio_bytes,
            extension=extension,
            content_type=content_type,
            duration_ms=0,
            provider_latency_ms=max(1, int((time.perf_counter() - started) * 1000)),
        )

    def healthcheck(self) -> ProviderHealth:
        if self._openai_client is None:
            return ProviderHealth(name=self.name, ready=False, detail=self._import_error)
        if not self.settings.openai_api_key:
            return ProviderHealth(name=self.name, ready=False, detail="OPENAI_API_KEY is not set")
        try:
            self._response_format()
            self._configured_voice()
        except ValueError as exc:
            return ProviderHealth(name=self.name, ready=False, detail=str(exc))
        return ProviderHealth(name=self.name, ready=True)

    def _voice_for(self, request: SynthesizeRequest) -> str:
        if request.voice.name in self._voice_names:
            return request.voice.name
        return self._configured_voice()

    def _configured_voice(self) -> str:
        voice = self.settings.openai_tts_voice
        if voice not in self._voice_names:
            raise ValueError("OPENAI_TTS_VOICE must be one of the supported OpenAI TTS voices")
        return voice

    def _response_format(self) -> str:
        response_format = self.settings.openai_tts_response_format.lower()
        if response_format not in {"wav", "mp3"}:
            raise ValueError("OPENAI_TTS_RESPONSE_FORMAT must be wav or mp3")
        return response_format

    def _response_bytes(self, response) -> bytes:
        if isinstance(response, bytes):
            return response
        if hasattr(response, "read"):
            return bytes(response.read())
        if hasattr(response, "content"):
            return bytes(response.content)
        raise RuntimeError("OpenAI speech response did not include audio bytes")


def build_provider(settings: Settings) -> TTSProvider:
    if settings.tts_provider == "local":
        return LocalFallbackProvider()
    if settings.tts_provider == "google":
        return GoogleTTSProvider(settings)
    if settings.tts_provider == "openai":
        return OpenAITTSProvider(settings)
    if settings.google_application_credentials:
        google = GoogleTTSProvider(settings)
        if google.healthcheck().ready:
            return google
    if settings.openai_api_key:
        openai = OpenAITTSProvider(settings)
        if openai.healthcheck().ready:
            return openai
    return LocalFallbackProvider()

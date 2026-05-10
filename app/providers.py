from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
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
    sample_rate_hz: int
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


class UnsupportedVoiceError(ValueError):
    pass


class LocalFallbackProvider(TTSProvider):
    name = "local"
    fallback = True
    model = "espeak-ng-spoken-wav"

    _voice_by_language = {
        "en": "en-us",
        "en-US": "en-us",
        "vi": "vi",
        "vi-VN": "vi-vn-x-central",
    }

    _voices = [
        VoiceInfo(
            name="local-en-US-espeak-ng",
            language_codes=["en-US"],
            ssml_gender="NEUTRAL",
            natural_sample_rate_hz=24000,
            supported_encodings=["LINEAR16", "MP3", "OGG_OPUS"],
        ),
        VoiceInfo(
            name="local-vi-VN-espeak-ng-central",
            language_codes=["vi-VN"],
            ssml_gender="NEUTRAL",
            natural_sample_rate_hz=24000,
            supported_encodings=["LINEAR16", "MP3", "OGG_OPUS"],
        ),
    ]

    def __init__(self, settings: Settings):
        self.settings = settings

    def list_voices(self, language_code: str | None = None) -> list[VoiceInfo]:
        if not language_code:
            return self._voices
        return [voice for voice in self._voices if language_code in voice.language_codes]

    def synthesize(self, request: SynthesizeRequest) -> ProviderSynthesisResult:
        started = time.perf_counter()
        audio_bytes, duration_ms, sample_rate_hz = self._make_spoken_wav(request)
        return ProviderSynthesisResult(
            provider_name=self.name,
            fallback=True,
            model=self.model,
            audio_bytes=audio_bytes,
            extension="wav",
            content_type="audio/wav",
            duration_ms=duration_ms,
            sample_rate_hz=sample_rate_hz,
            provider_latency_ms=max(1, int((time.perf_counter() - started) * 1000)),
        )

    def healthcheck(self) -> ProviderHealth:
        binary = self._binary()
        if not binary:
            return ProviderHealth(
                name=self.name,
                ready=False,
                detail="espeak-ng binary is not available; install espeak-ng or set ESPEAK_NG_PATH",
            )
        return ProviderHealth(name=self.name, ready=True, detail=f"speech engine: {Path(binary).name}")

    def _binary(self) -> str | None:
        return shutil.which(self.settings.espeak_ng_path)

    def _voice_for(self, request: SynthesizeRequest) -> str:
        if request.voice.name in {"local-vi-VN-espeak-ng-central", "vi-vn-x-central"}:
            return "vi-vn-x-central"
        if request.voice.name in {"local-en-US-espeak-ng", "en-us"}:
            return "en-us"
        return self._voice_by_language.get(request.voice.language_code, request.voice.language_code.lower())

    def _make_spoken_wav(self, request: SynthesizeRequest) -> tuple[bytes, int, int]:
        binary = self._binary()
        if not binary:
            raise RuntimeError("espeak-ng binary is not available; install espeak-ng or set ESPEAK_NG_PATH")

        with tempfile.TemporaryDirectory(prefix="voice-ai-espeak-") as tmp_dir:
            output_path = Path(tmp_dir) / "speech.wav"
            speed_wpm = max(80, min(500, int(175 * request.audio.speaking_rate)))
            pitch = max(0, min(99, int(50 + request.audio.pitch)))
            amplitude = max(0, min(200, int(100 + request.audio.volume_gain_db)))
            command = [
                binary,
                "-b",
                "1",
                "-v",
                self._voice_for(request),
                "-s",
                str(speed_wpm),
                "-p",
                str(pitch),
                "-a",
                str(amplitude),
                "-w",
                str(output_path),
            ]
            if request.input_type == "ssml":
                command.append("-m")
            command.append(request.input_text)
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("espeak-ng speech synthesis timed out") from exc
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
                raise RuntimeError(f"espeak-ng speech synthesis failed: {detail}")
            audio_bytes = output_path.read_bytes()
            if not audio_bytes.startswith(b"RIFF"):
                raise RuntimeError("espeak-ng did not produce a WAV/RIFF file")
            with wave.open(str(output_path), "rb") as wav:
                frame_rate = wav.getframerate()
                frames = wav.getnframes()
                duration_ms = int((frames / frame_rate) * 1000) if frame_rate else 0
            return audio_bytes, duration_ms, frame_rate


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
            sample_rate_hz=request.audio.sample_rate_hz,
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

    _voice_names = [
        "marin",
        "cedar",
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "fable",
        "onyx",
        "nova",
        "sage",
        "shimmer",
        "verse",
    ]

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
            sample_rate_hz=request.audio.sample_rate_hz,
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
        if request.voice.name:
            if request.voice.name in self._voice_names:
                return request.voice.name
            raise UnsupportedVoiceError(
                f"Unsupported OpenAI TTS voice '{request.voice.name}'. Supported built-in voices: {', '.join(self._voice_names)}"
            )
        return self._configured_voice()

    def _configured_voice(self) -> str:
        voice = self.settings.openai_tts_voice
        if voice not in self._voice_names:
            raise UnsupportedVoiceError(f"OPENAI_TTS_VOICE must be one of the supported OpenAI TTS voices: {', '.join(self._voice_names)}")
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
        return LocalFallbackProvider(settings)
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
    return LocalFallbackProvider(settings)

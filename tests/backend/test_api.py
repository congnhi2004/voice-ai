from __future__ import annotations

import math
import struct
import wave
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import OPENAI_AUDIO_UPLOAD_LIMIT_BYTES, OPENAI_TTS_INPUT_MAX_CHARS, Settings
from app.main import create_app
from app.providers import LocalFallbackProvider, OpenAITTSProvider, build_provider
from app.storage import GCSStorage
from app.video_localization import DispatchResult, OpenAIVideoLocalizationProvider, VideoDispatchError


def make_client(tmp_path: Path, **overrides) -> TestClient:
    settings = Settings(
        tts_provider=overrides.pop("tts_provider", "local"),
        audio_storage_dir=tmp_path / "audio",
        video_jobs_dir=tmp_path / "video-jobs",
        audio_base_url=overrides.pop("audio_base_url", "http://testserver"),
        auth_storage_path=overrides.pop("auth_storage_path", tmp_path / "auth-billing.sqlite3"),
        api_keys=overrides.pop("api_keys", ()),
        max_input_chars=overrides.pop("max_input_chars", 5000),
        mlflow_tracking_uri=overrides.pop("mlflow_tracking_uri", None),
        **overrides,
    )
    return TestClient(create_app(settings))


def synth_payload(text: str = "Hello from tests.") -> dict:
    return {
        "text": text,
        "voice": {"language_code": "en-US", "name": "local-en-US-espeak-ng", "ssml_gender": "NEUTRAL"},
        "audio": {"encoding": "LINEAR16", "sample_rate_hz": 24000},
        "metadata": {"client_reference_id": "pytest"},
    }


def vi_synth_payload(text: str = "Xin chao tu bai kiem thu.") -> dict:
    return {
        "text": text,
        "voice": {"language_code": "vi-VN", "name": "coral", "ssml_gender": "NEUTRAL"},
        "audio": {"encoding": "LINEAR16", "sample_rate_hz": 24000},
        "metadata": {"client_reference_id": "pytest-openai"},
    }


def vi_synth_payload_without_voice_name(text: str = "Xin chao tu bai kiem thu.") -> dict:
    return {
        "text": text,
        "voice": {"language_code": "vi-VN", "ssml_gender": "NEUTRAL"},
        "audio": {"encoding": "LINEAR16", "sample_rate_hz": 24000},
        "metadata": {"client_reference_id": "pytest-openai-default"},
    }


class FakeSpeechResponse:
    def __init__(self, content: bytes):
        self.content = content


class FakeSpeech:
    def __init__(self, content: bytes = b"RIFFopenai-real-speech-wav", error: Exception | None = None):
        self.content = content
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return FakeSpeechResponse(self.content)


class FakeTranscriptionResponse:
    def __init__(self, text: str):
        self.text = text


class FakeTranscriptions:
    def __init__(self, text: str = "Hello from the uploaded English video.", error: Exception | None = None):
        self.text = text
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return FakeTranscriptionResponse(self.text)


class FakeResponsesResult:
    def __init__(self, output_text: str):
        self.output_text = output_text


class FakeResponses:
    def __init__(self, output_text: str = "Xin chao tu video da tai len.", error: Exception | None = None):
        self.output_text = output_text
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return FakeResponsesResult(self.output_text)


class FakeOpenAIClient:
    def __init__(
        self,
        speech: FakeSpeech | None = None,
        transcriptions: FakeTranscriptions | None = None,
        responses: FakeResponses | None = None,
    ):
        self.audio = type(
            "Audio",
            (),
            {
                "speech": speech or FakeSpeech(),
                "transcriptions": transcriptions or FakeTranscriptions(),
            },
        )()
        self.responses = responses or FakeResponses()


class FakeGCSBlob:
    def __init__(self, bucket_name: str, name: str, uploads: dict[str, dict]):
        self.bucket_name = bucket_name
        self.name = name
        self.uploads = uploads

    def upload_from_string(self, data: bytes, content_type: str | None = None):
        self.uploads[f"gs://{self.bucket_name}/{self.name}"] = {"data": data, "content_type": content_type}

    def upload_from_filename(self, filename: str, content_type: str | None = None):
        self.uploads[f"gs://{self.bucket_name}/{self.name}"] = {"data": Path(filename).read_bytes(), "content_type": content_type}

    def generate_signed_url(self, **kwargs):
        method = kwargs.get("method", "GET")
        ttl = int(kwargs["expiration"].total_seconds())
        return f"https://signed.example/{self.bucket_name}/{self.name}?method={method}&ttl={ttl}&X-Goog-Signature=fake"

    def download_as_bytes(self):
        return self.uploads[f"gs://{self.bucket_name}/{self.name}"]["data"]

    def download_to_filename(self, filename: str):
        Path(filename).write_bytes(self.download_as_bytes())


class FakeGCSBucket:
    def __init__(self, name: str, uploads: dict[str, dict]):
        self.name = name
        self.uploads = uploads

    def blob(self, name: str):
        return FakeGCSBlob(self.name, name, self.uploads)


FAKE_MP4_BYTES = b"\x00\x00\x00\x18ftypmp42demo-video"
ORIGINAL_SHUTIL_WHICH = shutil.which


def write_fake_spoken_wav(path: Path, sample_rate_hz: int = 22050) -> None:
    frame_count = int(sample_rate_hz * 0.35)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate_hz)
        for frame in range(frame_count):
            frequency = 220 + ((frame // 900) % 7) * 45
            envelope = min(1.0, frame / max(1, int(sample_rate_hz * 0.02)))
            sample = int(9000 * envelope * math.sin(2 * math.pi * frequency * frame / sample_rate_hz))
            wav.writeframesraw(struct.pack("<h", sample))


@pytest.fixture
def fake_espeak_ng(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_which(command: str) -> str | None:
        if command == "espeak-ng":
            return "/usr/bin/espeak-ng"
        return ORIGINAL_SHUTIL_WHICH(command)

    def fake_run(command, check=False, stdout=None, stderr=None, text=None, timeout=None):
        calls.append(list(command))
        output_path = Path(command[command.index("-w") + 1])
        write_fake_spoken_wav(output_path)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("app.providers.shutil.which", fake_which)
    monkeypatch.setattr("app.providers.subprocess.run", fake_run)
    return calls


def ffmpeg_command(*args: str) -> list[str]:
    if shutil.which("taskset"):
        return ["taskset", "-c", "0-3", *args]
    return list(args)


@pytest.fixture
def valid_mp4_bytes(tmp_path: Path) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg is not available; skipping valid MP4 mux assertion")
    output = tmp_path / "valid-source.mp4"
    subprocess.run(
        ffmpeg_command(
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=160x120:rate=10:duration=1",
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "mpeg4",
            "-movflags",
            "+faststart",
            str(output),
        ),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    return output.read_bytes()


def test_health_and_readiness_local(tmp_path: Path, fake_espeak_ng: list[list[str]]):
    client = make_client(tmp_path)

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    health_alias = client.get("/health")
    assert health_alias.status_code == 200
    assert health_alias.json() == health.json()

    ready = client.get("/readyz")
    assert ready.status_code == 200
    body = ready.json()
    assert body["provider"] == {"name": "local", "ready": True, "detail": "speech engine: espeak-ng"}
    assert body["storage"]["ready"] is True
    assert body["mlflow"]["configured"] is False


def test_voices_contract(tmp_path: Path):
    client = make_client(tmp_path)

    response = client.get("/v1/voices?language_code=en-US")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "local"
    assert body["voices"][0]["name"] == "local-en-US-espeak-ng"
    assert "LINEAR16" in body["voices"][0]["supported_encodings"]


def test_synthesize_local_fallback_creates_playable_spoken_wav(tmp_path: Path, fake_espeak_ng: list[list[str]]):
    client = make_client(tmp_path)

    response = client.post("/v1/synthesize", json=synth_payload(), headers={"X-Request-ID": "req_test"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req_test"
    assert response.headers["X-Job-ID"].startswith("tts_")
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["provider"] == {"name": "local", "fallback": True, "model": "espeak-ng-spoken-wav"}
    assert body["audio"]["encoding"] == "LINEAR16"
    assert body["audio"]["content_type"] == "audio/wav"
    assert body["audio"]["sample_rate_hz"] == 22050
    assert body["audio"]["bytes"] > 1000
    assert body["observability"]["request_id"] == "req_test"
    assert body["metadata"]["client_reference_id"] == "pytest"

    audio_path = Path(body["audio_path"])
    assert audio_path.exists()
    with wave.open(str(audio_path), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 22050
        assert wav.getnframes() > 0

    audio_response = client.get(body["audio_url"].replace("http://testserver", ""))
    assert audio_response.status_code == 200
    assert len(audio_response.content) == body["audio"]["bytes"]
    assert audio_response.content.startswith(b"RIFF")
    assert fake_espeak_ng
    assert fake_espeak_ng[0][:5] == ["/usr/bin/espeak-ng", "-b", "1", "-v", "en-us"]
    assert "-w" in fake_espeak_ng[0]


def test_local_provider_without_espeak_ng_fails_clearly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(LocalFallbackProvider, "_binary", lambda self: None)
    client = make_client(tmp_path)

    ready = client.get("/readyz")
    assert ready.status_code == 503
    assert ready.json()["provider"] == {
        "name": "local",
        "ready": False,
        "detail": "espeak-ng binary is not available; install espeak-ng or set ESPEAK_NG_PATH",
    }

    response = client.post("/v1/synthesize", json=synth_payload())
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "synthesis_failed"
    assert "espeak-ng binary is not available" in body["error"]["details"]["error"]


def test_public_urls_do_not_duplicate_audio_prefix_when_env_contains_audio_mount(tmp_path: Path, fake_espeak_ng: list[list[str]]):
    client = make_client(tmp_path, audio_base_url="http://testserver/audio")

    tts = client.post("/v1/synthesize", json=synth_payload())
    assert tts.status_code == 200
    audio_url = tts.json()["audio_url"]
    assert audio_url.startswith("http://testserver/audio/tts_")
    assert "/audio/audio/" not in audio_url
    audio_response = client.get(audio_url.replace("http://testserver", ""))
    assert audio_response.status_code == 200
    assert len(audio_response.content) > 1000
    assert audio_response.content.startswith(b"RIFF")

    video = client.post(
        "/v1/video-localization/jobs",
        data={"source_language": "en-US", "target_language": "vi"},
        files={"file": ("sample.mp4", FAKE_MP4_BYTES, "video/mp4")},
    )
    assert video.status_code == 400
    assert video.json()["error"]["code"] == "invalid_video_upload"


def test_gcs_audio_storage_uploads_and_returns_signed_url(tmp_path: Path, fake_espeak_ng: list[list[str]], monkeypatch: pytest.MonkeyPatch):
    uploads: dict[str, dict] = {}

    def fake_bucket(self):
        return FakeGCSBucket(self.bucket_name, uploads)

    monkeypatch.setattr("app.storage.GCSStorage._get_bucket", fake_bucket)
    client = make_client(
        tmp_path,
        storage_provider="gcs",
        gcs_audio_bucket="voice-ai-audio-test",
        gcs_artifact_bucket="voice-ai-artifact-test",
        gcs_audio_prefix="voice-ai/audio-test",
        signed_url_ttl_seconds=900,
    )

    response = client.post("/v1/synthesize", json=synth_payload(), headers={"X-Request-ID": "req_gcs_audio"})

    assert response.status_code == 200
    body = response.json()
    assert body["audio_url"].startswith("https://signed.example/voice-ai-audio-test/voice-ai/audio-test/tts_")
    assert "ttl=900" in body["audio_url"]
    assert body["audio_path"].endswith(".wav")
    uploaded_uri = next(uri for uri in uploads if uri.startswith("gs://voice-ai-audio-test/voice-ai/audio-test/tts_"))
    assert uploads[uploaded_uri]["data"].startswith(b"RIFF")
    assert uploads[uploaded_uri]["content_type"] == "audio/wav"


def test_video_localization_rejects_fake_mp4_with_clear_contract_error(tmp_path: Path):
    client = make_client(tmp_path)

    response = client.post(
        "/v1/video-localization/jobs",
        data={"source_language": "en-US", "target_language": "vi"},
        files={"file": ("sample.mp4", FAKE_MP4_BYTES, "video/mp4")},
        headers={"X-Request-ID": "req_invalid_video"},
    )

    assert response.status_code == 400
    assert response.headers["X-Request-ID"] == "req_invalid_video"
    body = response.json()
    assert body["error"]["code"] == "invalid_video_upload"
    assert body["error"]["message"] == "Uploaded MP4 is too small to contain a playable video."
    assert body["error"]["details"] == {"filename": "sample.mp4", "content_type": "video/mp4"}
    assert body["job_id"].startswith("vid_")


def test_api_key_auth_missing_and_valid(tmp_path: Path, fake_espeak_ng: list[list[str]]):
    client = make_client(tmp_path, api_keys=("secret",))

    missing = client.post("/v1/synthesize", json=synth_payload())
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "missing_api_key"

    invalid = client.post("/v1/synthesize", json=synth_payload(), headers={"X-API-Key": "bad"})
    assert invalid.status_code == 403
    assert invalid.json()["error"]["code"] == "invalid_api_key"

    valid = client.post("/v1/synthesize", json=synth_payload(), headers={"Authorization": "Bearer secret"})
    assert valid.status_code == 200


def test_max_input_chars_returns_contract_error(tmp_path: Path):
    client = make_client(tmp_path, max_input_chars=5)

    response = client.post("/v1/synthesize", json=synth_payload("too long"))

    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "input_too_large"
    assert body["request_id"].startswith("req_")


def test_malformed_synthesize_input_returns_structured_validation_error(tmp_path: Path):
    client = make_client(tmp_path)
    payload = synth_payload("Hello")
    payload["ssml"] = "<speak>Hello</speak>"

    response = client.post("/v1/synthesize", json=payload, headers={"X-Request-ID": "req_validation"})

    assert response.status_code == 422
    assert response.headers["X-Request-ID"] == "req_validation"
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["request_id"] == "req_validation"
    errors = body["error"]["details"]["errors"]
    assert errors[0]["type"] == "value_error"
    assert errors[0]["ctx"]["error"] == "Exactly one of text or ssml is required."


def test_google_required_credentials_readiness_failure(tmp_path: Path):
    client = make_client(tmp_path, tts_provider="google", google_application_credentials=None)

    response = client.get("/readyz")

    assert response.status_code == 503
    body = response.json()
    assert body["provider"]["name"] == "google"
    assert body["provider"]["ready"] is False
    assert "GOOGLE_APPLICATION_CREDENTIALS" in body["provider"]["detail"]


def test_auto_provider_selects_openai_when_key_exists_and_google_unavailable():
    provider = build_provider(Settings(tts_provider="auto", openai_api_key="dummy_openai_provider_selection"))

    assert provider.name == "openai"
    assert provider.fallback is False


def test_openai_voices_contract_when_provider_active(tmp_path: Path):
    client = make_client(tmp_path, tts_provider="openai", openai_api_key="dummy_openai_voices")

    response = client.get("/v1/voices?language_code=vi-VN")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "openai"
    voice_names = {voice["name"] for voice in body["voices"]}
    assert body["voices"][0]["name"] == "marin"
    assert body["voices"][1]["name"] == "cedar"
    assert {"marin", "cedar"} <= voice_names
    assert "coral" in voice_names
    assert all("LINEAR16" in voice["supported_encodings"] for voice in body["voices"])


def test_openai_readiness_accepts_marin_and_cedar_configured_voices(tmp_path: Path):
    for voice in ("marin", "cedar", "coral"):
        client = make_client(tmp_path / voice, tts_provider="openai", openai_api_key="dummy_openai_ready", openai_tts_voice=voice)

        response = client.get("/readyz")

        assert response.status_code == 200
        assert response.json()["provider"] == {"name": "openai", "ready": True, "detail": None}


def test_synthesize_openai_uses_mocked_client_for_vietnamese_wav(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    speech = FakeSpeech(content=b"RIFFmock-openai-vietnamese-spoken-audio")
    monkeypatch.setattr(OpenAITTSProvider, "_get_client", lambda self: FakeOpenAIClient(speech))
    client = make_client(tmp_path, tts_provider="openai", openai_api_key="dummy_openai_tts")

    response = client.post("/v1/synthesize", json=vi_synth_payload("Xin chao, day la giong noi that."))

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == {"name": "openai", "fallback": False, "model": "gpt-4o-mini-tts"}
    assert body["audio"]["encoding"] == "LINEAR16"
    assert body["audio"]["content_type"] == "audio/wav"
    assert Path(body["audio_path"]).read_bytes() == b"RIFFmock-openai-vietnamese-spoken-audio"
    assert speech.calls == [
        {
            "model": "gpt-4o-mini-tts",
            "voice": "coral",
            "input": "Xin chao, day la giong noi that.",
            "response_format": "wav",
        }
    ]


def test_synthesize_openai_uses_marin_as_default_quality_voice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    speech = FakeSpeech(content=b"RIFFmock-openai-default-marin-audio")
    monkeypatch.setattr(OpenAITTSProvider, "_get_client", lambda self: FakeOpenAIClient(speech))
    client = make_client(tmp_path, tts_provider="openai", openai_api_key="dummy_openai_tts")

    response = client.post("/v1/synthesize", json=vi_synth_payload_without_voice_name())

    assert response.status_code == 200
    assert speech.calls[0]["voice"] == "marin"


def test_synthesize_openai_accepts_marin_and_cedar_request_voices(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    speech = FakeSpeech(content=b"RIFFmock-openai-premium-voice-audio")
    monkeypatch.setattr(OpenAITTSProvider, "_get_client", lambda self: FakeOpenAIClient(speech))
    client = make_client(tmp_path, tts_provider="openai", openai_api_key="dummy_openai_tts")

    for voice in ("marin", "cedar"):
        payload = vi_synth_payload(f"Xin chao tu giong {voice}.")
        payload["voice"]["name"] = voice
        response = client.post("/v1/synthesize", json=payload)

        assert response.status_code == 200

    assert [call["voice"] for call in speech.calls] == ["marin", "cedar"]


def test_synthesize_openai_rejects_invalid_request_voice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    speech = FakeSpeech(content=b"RIFFshould-not-be-used")
    monkeypatch.setattr(OpenAITTSProvider, "_get_client", lambda self: FakeOpenAIClient(speech))
    client = make_client(tmp_path, tts_provider="openai", openai_api_key="dummy_openai_tts")
    payload = vi_synth_payload()
    payload["voice"]["name"] = "not-a-real-openai-voice"

    response = client.post("/v1/synthesize", json=payload)

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "unsupported_voice"
    assert "not-a-real-openai-voice" in body["error"]["details"]["error"]
    assert "marin" in body["error"]["details"]["error"]
    assert speech.calls == []


def test_openai_mp3_response_format_is_reflected_in_audio_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    speech = FakeSpeech(content=b"ID3mock-openai-mp3")
    monkeypatch.setattr(OpenAITTSProvider, "_get_client", lambda self: FakeOpenAIClient(speech))
    client = make_client(tmp_path, tts_provider="openai", openai_api_key="dummy_openai_tts", openai_tts_response_format="mp3")

    response = client.post("/v1/synthesize", json=vi_synth_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["audio"]["encoding"] == "MP3"
    assert body["audio"]["content_type"] == "audio/mpeg"
    assert body["audio_url"].endswith(".mp3")
    assert speech.calls[0]["response_format"] == "mp3"


def test_openai_provider_errors_redact_configured_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
    secret = "dummy_openai_redaction_value"
    speech = FakeSpeech(error=RuntimeError(f"upstream rejected api key {secret}"))
    monkeypatch.setattr(OpenAITTSProvider, "_get_client", lambda self: FakeOpenAIClient(speech))
    client = make_client(tmp_path, tts_provider="openai", openai_api_key=secret)

    response = client.post("/v1/synthesize", json=vi_synth_payload())

    assert response.status_code == 503
    assert secret not in response.text
    assert "[redacted]" in response.text
    assert secret not in caplog.text


def test_openai_tts_rejects_input_over_provider_limit_before_provider_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    speech = FakeSpeech(content=b"RIFFshould-not-be-called")
    monkeypatch.setattr(OpenAITTSProvider, "_get_client", lambda self: FakeOpenAIClient(speech))
    client = make_client(tmp_path, tts_provider="openai", openai_api_key="dummy_openai_tts", max_input_chars=5000)

    response = client.post("/v1/synthesize", json=vi_synth_payload("x" * (OPENAI_TTS_INPUT_MAX_CHARS + 1)))

    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "input_too_large"
    assert body["error"]["details"]["provider"] == "openai"
    assert body["error"]["details"]["max_input_chars"] == OPENAI_TTS_INPUT_MAX_CHARS
    assert body["error"]["details"]["configured_max_input_chars"] == 5000
    assert speech.calls == []

    capabilities = client.get("/v1/product/capabilities").json()
    assert capabilities["tts"]["active_provider"] == "openai"
    assert capabilities["tts"]["max_input_chars"] == OPENAI_TTS_INPUT_MAX_CHARS


def test_video_localization_demo_workflow_creates_artifacts_and_status(tmp_path: Path, valid_mp4_bytes: bytes, fake_espeak_ng: list[list[str]]):
    client = make_client(tmp_path)

    response = client.post(
        "/v1/video-localization/jobs",
        data={"source_language": "en-US", "target_language": "vi"},
        files={"file": ("sample.mp4", valid_mp4_bytes, "video/mp4")},
        headers={"X-Request-ID": "req_video"},
    )

    assert response.status_code == 200
    assert response.headers["X-Job-ID"].startswith("vid_")
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["target_language"] == "vi"
    assert body["provider"]["fallback"] is True
    assert body["transcript_chars"] > 0
    assert body["translated_chars"] > 0
    assert body["segments"][0]["translated_text"].startswith("Ban dich tieng Viet demo:")
    artifact_kinds = {artifact["kind"] for artifact in body["artifacts"]}
    assert {"source_video", "transcript", "subtitles_srt", "subtitles_vtt", "voiceover_audio", "localized_video"} <= artifact_kinds

    status_response = client.get(f"/v1/video-localization/jobs/{body['job_id']}")
    assert status_response.status_code == 200
    assert status_response.json()["job_id"] == body["job_id"]

    for artifact in body["artifacts"]:
        download = client.get(artifact["url"].replace("http://testserver", ""))
        assert download.status_code == 200, artifact
        assert len(download.content) == artifact["bytes"]
        if artifact["kind"] == "subtitles_srt":
            assert b"Ban dich tieng Viet demo:" in download.content
        if artifact["kind"] == "voiceover_audio":
            assert download.content.startswith(b"RIFF")
        if artifact["kind"] == "transcript":
            assert b'"segments"' in download.content
        if artifact["kind"] == "localized_video":
            assert download.content.startswith(b"\x00\x00\x00")


def test_gcs_video_artifacts_upload_and_refresh_signed_urls(
    tmp_path: Path,
    fake_espeak_ng: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
):
    uploads: dict[str, dict] = {}

    def fake_bucket(self):
        return FakeGCSBucket(self.bucket_name, uploads)

    monkeypatch.setattr("app.storage.GCSStorage._get_bucket", fake_bucket)
    monkeypatch.setattr("app.video_localization.validate_mp4_container", lambda path, settings: None)

    def fake_render(settings, source, audio, subtitles, output):
        output.write_bytes(b"\x00\x00\x00 fake localized mp4")
        return None

    monkeypatch.setattr("app.video_localization.render_or_copy_video", fake_render)
    client = make_client(
        tmp_path,
        storage_provider="gcs",
        gcs_audio_bucket="voice-ai-audio-test",
        gcs_artifact_bucket="voice-ai-artifact-test",
        gcs_audio_prefix="voice-ai/audio-test",
        gcs_source_video_prefix="voice-ai/video/source-test",
        gcs_intermediate_prefix="voice-ai/video/intermediate-test",
        gcs_rendered_video_prefix="voice-ai/video/rendered-test",
        signed_url_ttl_seconds=1200,
    )

    response = client.post(
        "/v1/video-localization/jobs",
        data={"source_language": "en-US", "target_language": "vi"},
        files={"file": ("sample.mp4", FAKE_MP4_BYTES, "video/mp4")},
    )

    assert response.status_code == 200
    body = response.json()
    source = next(artifact for artifact in body["artifacts"] if artifact["kind"] == "source_video")
    rendered = next(artifact for artifact in body["artifacts"] if artifact["kind"] == "localized_video")
    transcript = next(artifact for artifact in body["artifacts"] if artifact["kind"] == "transcript")
    assert source["path"].startswith("gs://voice-ai-artifact-test/voice-ai/video/source-test/")
    assert rendered["path"].startswith("gs://voice-ai-artifact-test/voice-ai/video/rendered-test/")
    assert transcript["path"].startswith("gs://voice-ai-artifact-test/voice-ai/video/intermediate-test/")
    assert all(artifact["url"].startswith("https://signed.example/voice-ai-artifact-test/") for artifact in body["artifacts"])
    assert any(uri.startswith("gs://voice-ai-artifact-test/voice-ai/video/source-test/") for uri in uploads)
    assert any(uri.startswith("gs://voice-ai-artifact-test/voice-ai/video/rendered-test/") for uri in uploads)

    status_response = client.get(f"/v1/video-localization/jobs/{body['job_id']}")
    assert status_response.status_code == 200
    assert "ttl=1200" in status_response.json()["artifacts"][0]["url"]

    filename = rendered["path"].rsplit("/", 1)[-1]
    redirect = client.get(f"/v1/video-localization/jobs/{body['job_id']}/artifacts/{filename}", follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"].startswith("https://signed.example/voice-ai-artifact-test/")


def test_video_cloud_tasks_mode_creates_queued_job_and_status_polling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    dispatched: list[str] = []

    monkeypatch.setattr("app.video_localization.CloudTasksVideoDispatcher.readiness", lambda self: (True, None))

    def fake_dispatch(self, job_id: str):
        dispatched.append(job_id)
        return DispatchResult(mode="cloud_tasks", task_name=f"task/{job_id}", detail="queued")

    monkeypatch.setattr("app.video_localization.CloudTasksVideoDispatcher.dispatch", fake_dispatch)
    client = make_client(
        tmp_path,
        video_job_dispatch_mode="cloud_tasks",
        cloud_tasks_project_id="voice-ai-test",
        cloud_tasks_queue="video-localization",
        cloud_tasks_handler_url="https://voice-ai.example/internal/video-localization/tasks",
        cloud_tasks_service_account_email="tasks@voice-ai-test.iam.gserviceaccount.com",
        internal_task_token="test-token",
    )

    response = client.post(
        "/v1/video-localization/jobs",
        data={"source_language": "en-US", "target_language": "vi"},
        files={"file": ("sample.mp4", FAKE_MP4_BYTES, "video/mp4")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["dispatch"]["mode"] == "cloud_tasks"
    assert body["dispatch"]["task_name"] == f"task/{body['job_id']}"
    assert body["artifacts"] == []
    assert dispatched == [body["job_id"]]

    status_response = client.get(f"/v1/video-localization/jobs/{body['job_id']}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "queued"


def test_internal_video_task_handler_processes_job_idempotently(
    tmp_path: Path,
    fake_espeak_ng: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("app.video_localization.CloudTasksVideoDispatcher.readiness", lambda self: (True, None))
    monkeypatch.setattr(
        "app.video_localization.CloudTasksVideoDispatcher.dispatch",
        lambda self, job_id: DispatchResult(mode="cloud_tasks", task_name=f"task/{job_id}", detail="queued"),
    )
    monkeypatch.setattr("app.video_localization.validate_mp4_container", lambda path, settings: None)
    render_calls: list[str] = []

    def fake_render(settings, source, audio, subtitles, output):
        render_calls.append(str(output))
        output.write_bytes(b"\x00\x00\x00 fake localized mp4")
        return None

    monkeypatch.setattr("app.video_localization.render_or_copy_video", fake_render)
    client = make_client(
        tmp_path,
        video_job_dispatch_mode="cloud_tasks",
        cloud_tasks_project_id="voice-ai-test",
        cloud_tasks_queue="video-localization",
        cloud_tasks_handler_url="https://voice-ai.example/internal/video-localization/tasks",
        cloud_tasks_service_account_email="tasks@voice-ai-test.iam.gserviceaccount.com",
        internal_task_token="test-token",
    )
    queued = client.post(
        "/v1/video-localization/jobs",
        data={"source_language": "en-US", "target_language": "vi"},
        files={"file": ("sample.mp4", FAKE_MP4_BYTES, "video/mp4")},
    ).json()

    unauthorized = client.post(f"/internal/video-localization/tasks/{queued['job_id']}")
    assert unauthorized.status_code == 403
    assert unauthorized.json()["error"]["code"] == "invalid_internal_task_token"

    first = client.post(f"/internal/video-localization/tasks/{queued['job_id']}", headers={"X-Internal-Task-Token": "test-token"})
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["status"] == "succeeded"
    assert len(render_calls) == 1

    second = client.post(f"/internal/video-localization/tasks/{queued['job_id']}", headers={"X-Internal-Task-Token": "test-token"})
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["status"] == "succeeded"
    assert len(second_body["artifacts"]) == len(first_body["artifacts"])
    assert len(render_calls) == 1


def test_readyz_reports_video_storage_and_dispatch_modes(tmp_path: Path, fake_espeak_ng: list[list[str]], monkeypatch: pytest.MonkeyPatch):
    uploads: dict[str, dict] = {}

    def fake_bucket(self):
        return FakeGCSBucket(self.bucket_name, uploads)

    monkeypatch.setattr("app.storage.GCSStorage._get_bucket", fake_bucket)
    monkeypatch.setattr("app.video_localization.CloudTasksVideoDispatcher.readiness", lambda self: (True, None))
    client = make_client(
        tmp_path,
        storage_provider="gcs",
        gcs_audio_bucket="voice-ai-audio-test",
        gcs_artifact_bucket="voice-ai-artifact-test",
        video_job_dispatch_mode="cloud_tasks",
        cloud_tasks_project_id="voice-ai-test",
        cloud_tasks_queue="video-localization",
        cloud_tasks_handler_url="https://voice-ai.example/internal/video-localization/tasks",
        cloud_tasks_service_account_email="tasks@voice-ai-test.iam.gserviceaccount.com",
    )

    response = client.get("/readyz")

    assert response.status_code == 200
    body = response.json()
    assert body["storage"]["mode"] == "gcs"
    assert body["video_localization"]["storage"] == {
        "mode": "gcs",
        "job_metadata_mode": "gcs",
        "artifact_bucket": "voice-ai-artifact-test",
    }
    assert body["video_localization"]["dispatch"]["mode"] == "cloud_tasks"
    assert body["video_localization"]["dispatch"]["ready"] is True


def test_gcs_storage_downloads_uploaded_bytes_by_uri(tmp_path: Path):
    uploads: dict[str, dict] = {}
    settings = Settings(gcs_artifact_bucket="voice-ai-artifact-test", signed_url_ttl_seconds=60)
    storage = GCSStorage(settings, "voice-ai-artifact-test", client=type("Client", (), {"bucket": lambda self, name: FakeGCSBucket(name, uploads)})())

    stored = storage.upload_bytes("voice-ai/video/jobs/job-1/status.json", b'{"status":"queued"}', "application/json")

    assert stored.storage_uri == "gs://voice-ai-artifact-test/voice-ai/video/jobs/job-1/status.json"
    assert storage.download_bytes(stored.storage_uri) == b'{"status":"queued"}'


def test_video_dispatch_failure_maps_to_failed_job_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.video_localization.CloudTasksVideoDispatcher.readiness", lambda self: (True, None))
    monkeypatch.setattr(
        "app.video_localization.CloudTasksVideoDispatcher.dispatch",
        lambda self, job_id: (_ for _ in ()).throw(VideoDispatchError("queue unavailable")),
    )
    client = make_client(
        tmp_path,
        video_job_dispatch_mode="cloud_tasks",
        cloud_tasks_project_id="voice-ai-test",
        cloud_tasks_queue="video-localization",
        cloud_tasks_handler_url="https://voice-ai.example/internal/video-localization/tasks",
        cloud_tasks_service_account_email="tasks@voice-ai-test.iam.gserviceaccount.com",
    )

    response = client.post(
        "/v1/video-localization/jobs",
        data={"source_language": "en-US", "target_language": "vi"},
        files={"file": ("sample.mp4", FAKE_MP4_BYTES, "video/mp4")},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "video_dispatch_failed"
    status_response = client.get(f"/v1/video-localization/jobs/{body['job_id']}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "failed"


def test_video_storage_failure_maps_to_contract_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def failing_upload(self, local_path, object_name, content_type=None):
        raise RuntimeError("gcs write failed")

    monkeypatch.setattr("app.storage.GCSStorage._get_bucket", lambda self: FakeGCSBucket(self.bucket_name, {}))
    monkeypatch.setattr("app.storage.GCSStorage.upload_file", failing_upload)
    client = make_client(
        tmp_path,
        storage_provider="gcs",
        gcs_audio_bucket="voice-ai-audio-test",
        gcs_artifact_bucket="voice-ai-artifact-test",
    )

    response = client.post(
        "/v1/video-localization/jobs",
        data={"source_language": "en-US", "target_language": "vi"},
        files={"file": ("sample.mp4", FAKE_MP4_BYTES, "video/mp4")},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "video_storage_failed"


def test_video_localization_auto_uses_openai_pipeline_when_key_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    speech = FakeSpeech(content=b"RIFFmock-openai-video-vietnamese-speech")
    transcriptions = FakeTranscriptions(text="Welcome to the product demo.")
    responses = FakeResponses(output_text="Chao mung ban den voi ban demo san pham.")
    fake_client = FakeOpenAIClient(speech=speech, transcriptions=transcriptions, responses=responses)
    monkeypatch.setattr(OpenAIVideoLocalizationProvider, "_get_client", lambda self: fake_client)
    monkeypatch.setattr(OpenAITTSProvider, "_get_client", lambda self: fake_client)
    monkeypatch.setattr("app.video_localization.probe_video", lambda path, settings: 3200)
    monkeypatch.setattr("app.video_localization.extract_audio", lambda settings, source, output: output.write_bytes(b"ID3source-audio"))

    def fake_render(settings, source, audio, subtitles, output):
        output.write_bytes(source.read_bytes())
        return None

    monkeypatch.setattr("app.video_localization.render_or_copy_video", fake_render)
    client = make_client(tmp_path, tts_provider="local", openai_api_key="dummy_openai_video_key")

    response = client.post(
        "/v1/video-localization/jobs",
        data={"source_language": "en-US", "target_language": "vi", "voice_name": "marin"},
        files={"file": ("sample.mp4", FAKE_MP4_BYTES, "video/mp4")},
        headers={"X-Request-ID": "req_openai_video"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"]["name"] == "openai"
    assert body["provider"]["fallback"] is False
    assert "gpt-4o-mini-transcribe" in body["provider"]["model"]
    assert body["segments"][0]["source_text"] == "Welcome to the product demo."
    assert body["segments"][0]["translated_text"] == "Chao mung ban den voi ban demo san pham."
    artifact_kinds = {artifact["kind"] for artifact in body["artifacts"]}
    assert {"source_audio", "voiceover_audio", "localized_video"} <= artifact_kinds
    assert transcriptions.calls[0]["model"] == "gpt-4o-mini-transcribe"
    assert transcriptions.calls[0]["language"] == "en"
    assert responses.calls[0]["model"] == "gpt-4o-mini"
    assert speech.calls[0]["model"] == "gpt-4o-mini-tts"
    assert speech.calls[0]["voice"] == "marin"
    assert "dummy_openai_video_key" not in response.text


def test_video_localization_provider_errors_redact_openai_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
    secret = "dummy_openai_video_secret"
    fake_client = FakeOpenAIClient(transcriptions=FakeTranscriptions(error=RuntimeError(f"bad key {secret}")))
    monkeypatch.setattr(OpenAIVideoLocalizationProvider, "_get_client", lambda self: fake_client)
    monkeypatch.setattr("app.video_localization.probe_video", lambda path, settings: 3200)
    monkeypatch.setattr("app.video_localization.extract_audio", lambda settings, source, output: output.write_bytes(b"ID3source-audio"))
    client = make_client(tmp_path, tts_provider="local", openai_api_key=secret)

    response = client.post(
        "/v1/video-localization/jobs",
        data={"source_language": "en-US", "target_language": "vi"},
        files={"file": ("sample.mp4", FAKE_MP4_BYTES, "video/mp4")},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "video_provider_failed"
    assert secret not in response.text
    assert "[redacted]" in response.text
    assert secret not in caplog.text


def test_video_localization_rejects_oversized_upload_before_provider(tmp_path: Path):
    client = make_client(tmp_path, openai_api_key="dummy_openai_video_key")

    response = client.post(
        "/v1/video-localization/jobs",
        data={"source_language": "en-US", "target_language": "vi"},
        files={"file": ("huge.mp4", b"0" * (25 * 1024 * 1024 + 1), "video/mp4")},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "unsupported_video_upload"
    assert "25 MB" in body["error"]["message"]
    assert body["error"]["details"]["max_upload_bytes"] == OPENAI_AUDIO_UPLOAD_LIMIT_BYTES


def test_public_video_artifact_urls_do_not_use_audio_prefix(tmp_path: Path, valid_mp4_bytes: bytes, fake_espeak_ng: list[list[str]]):
    client = make_client(tmp_path, audio_base_url="http://testserver/audio")

    video = client.post(
        "/v1/video-localization/jobs",
        data={"source_language": "en-US", "target_language": "vi"},
        files={"file": ("sample.mp4", valid_mp4_bytes, "video/mp4")},
    )
    assert video.status_code == 200
    srt_url = next(artifact["url"] for artifact in video.json()["artifacts"] if artifact["kind"] == "subtitles_srt")
    assert srt_url.startswith("http://testserver/v1/video-localization/jobs/")
    assert "/audio/v1/" not in srt_url
    srt_response = client.get(srt_url.replace("http://testserver", ""))
    assert srt_response.status_code == 200
    assert b"Ban dich tieng Viet demo:" in srt_response.content


def test_mlflow_tracking_records_tts_and_video_runs_when_configured(tmp_path: Path, valid_mp4_bytes: bytes, fake_espeak_ng: list[list[str]]):
    import mlflow

    tracking_dir = tmp_path / "mlruns"
    client = make_client(tmp_path, mlflow_tracking_uri=tracking_dir.as_uri(), mlflow_log_audio_artifacts=False)

    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert ready.json()["mlflow"] == {"configured": True, "ready": True, "detail": None}

    tts = client.post("/v1/synthesize", json=synth_payload("MLflow TTS test."))
    assert tts.status_code == 200
    tts_body = tts.json()
    tts_run_id = tts_body["observability"]["mlflow_run_id"]
    assert tts_run_id
    assert tts_body["observability"]["warnings"] == []

    video = client.post(
        "/v1/video-localization/jobs",
        data={"source_language": "en-US", "target_language": "vi"},
        files={"file": ("sample.mp4", valid_mp4_bytes, "video/mp4")},
    )
    assert video.status_code == 200
    video_body = video.json()
    video_run_id = video_body["observability"]["mlflow_run_id"]
    assert video_run_id
    assert video_run_id != tts_run_id

    mlflow.set_tracking_uri(tracking_dir.as_uri())
    experiment = mlflow.get_experiment_by_name("voice-ai-tts-synthesis")
    assert experiment is not None
    runs = mlflow.search_runs(experiment_ids=[experiment.experiment_id], output_format="list")
    run_ids = {run.info.run_id for run in runs}
    assert {tts_run_id, video_run_id} <= run_ids


def test_openapi_includes_tts_and_video_paths(tmp_path: Path):
    client = make_client(tmp_path)

    schema = client.get("/openapi.json").json()

    assert "/health" in schema["paths"]
    assert "/v1/synthesize" in schema["paths"]
    assert "/v1/video-localization/jobs" in schema["paths"]
    assert "/v1/video-localization/jobs/{job_id}" in schema["paths"]
    assert "/v1/product/plans" in schema["paths"]
    assert "/v1/product/capabilities" in schema["paths"]
    assert "/v1/demo/workspace" in schema["paths"]
    assert "/v1/billing/checkout-session" in schema["paths"]
    assert "/v1/billing/checkout" in schema["paths"]
    assert "/v1/billing/customer-portal" in schema["paths"]
    assert "/v1/billing/portal" in schema["paths"]
    assert "/v1/billing/stripe-webhook" in schema["paths"]


def test_public_product_and_demo_workspace_endpoints(tmp_path: Path):
    client = make_client(tmp_path)

    plans = client.get("/v1/product/plans")
    assert plans.status_code == 200
    plans_body = plans.json()
    assert plans_body["billing"]["production_billing"] is False
    assert plans_body["billing"]["mode"] == "not-configured"
    assert plans_body["plans"][0]["id"] == "free"
    assert plans_body["plans"][0]["demo_only"] is False

    capabilities = client.get("/v1/product/capabilities")
    assert capabilities.status_code == 200
    capabilities_body = capabilities.json()
    assert capabilities_body["tts"]["available"] is True
    assert capabilities_body["tts"]["max_input_chars"] == 5000
    assert capabilities_body["video_localization"]["max_upload_bytes"] == OPENAI_AUDIO_UPLOAD_LIMIT_BYTES
    assert capabilities_body["video_localization"]["target_languages"] == ["vi", "vi-VN"]
    assert capabilities_body["auth"]["mode"] == "jwt-password"
    assert capabilities_body["auth"]["configured"] is True
    assert capabilities_body["auth"]["production_identity"] is False
    assert capabilities_body["billing"]["production_billing"] is False

    workspace = client.get("/v1/demo/workspace")
    assert workspace.status_code == 200
    workspace_body = workspace.json()
    assert workspace_body["workspace_id"] == "demo"
    assert workspace_body["demo_only"] is True
    assert workspace_body["tts_jobs_available"] is True
    assert workspace_body["video_jobs_available"] is True


def test_auth_register_login_me_logout_uses_jwt_and_hash_storage(tmp_path: Path):
    client = make_client(tmp_path)
    credentials = {"email": "User@Example.com", "password": "local-demo-pass", "name": "Demo User"}

    registered = client.post("/v1/auth/register", json=credentials)
    assert registered.status_code == 200
    registered_body = registered.json()
    assert registered_body["user"]["email"] == "user@example.com"
    assert registered_body["access_token"].count(".") == 2
    assert "password" not in registered.text

    duplicate = client.post("/v1/auth/register", json=credentials)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "user_exists"

    bad_login = client.post("/v1/auth/login", json={"email": "user@example.com", "password": "wrong-pass"})
    assert bad_login.status_code == 401
    assert bad_login.json()["error"]["code"] == "invalid_credentials"

    login = client.post("/v1/auth/login", json={"email": "user@example.com", "password": "local-demo-pass"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "user@example.com"

    logout = client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout.status_code == 200
    assert logout.json() == {"logged_out": True}

    after_logout = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert after_logout.status_code == 401
    assert after_logout.json()["error"]["code"] == "invalid_bearer_token"

    db_text = (tmp_path / "auth-billing.sqlite3").read_bytes()
    assert b"local-demo-pass" not in db_text


def test_production_auth_requires_jwt_secret(tmp_path: Path):
    client = make_client(tmp_path, environment="production")

    response = client.post("/v1/auth/register", json={"email": "prod@example.com", "password": "prod-pass-123"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "auth_not_configured"


def test_billing_checkout_not_configured_returns_503(tmp_path: Path):
    client = make_client(tmp_path)
    token = client.post("/v1/auth/register", json={"email": "bill@example.com", "password": "billing-pass-123"}).json()["access_token"]

    response = client.post("/v1/billing/checkout-session", json={"plan_id": "starter"}, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "billing_not_configured"

    alias = client.post("/v1/billing/checkout", json={"plan_id": "starter"}, headers={"Authorization": f"Bearer {token}"})
    assert alias.status_code == 503
    assert alias.json()["error"]["code"] == "billing_not_configured"


def test_billing_checkout_and_portal_use_mocked_stripe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    class FakeStripeBillingClient:
        def __init__(self, settings):
            self.settings = settings

        def require_configured(self):
            return None

        def create_customer(self, *, email: str, name: str | None, user_id: str) -> str:
            return "cus_test_123"

        def create_checkout_session(self, *, customer_id: str, price_id: str, plan_id: str, user_id: str):
            assert customer_id == "cus_test_123"
            assert price_id == "price_starter"
            assert plan_id == "starter"
            return "https://checkout.stripe.test/session", "cs_test_123"

        def create_portal_session(self, *, customer_id: str):
            assert customer_id == "cus_test_123"
            return "https://billing.stripe.test/session", "bps_test_123"

    monkeypatch.setattr("app.main.StripeBillingClient", FakeStripeBillingClient)
    client = make_client(
        tmp_path,
        stripe_secret_key="sk_test_mock",
        stripe_webhook_secret="whsec_mock",
        stripe_success_url="https://example.com/success",
        stripe_cancel_url="https://example.com/cancel",
        stripe_portal_return_url="https://example.com/account",
        stripe_price_starter="price_starter",
    )
    token = client.post("/v1/auth/register", json={"email": "pay@example.com", "password": "billing-pass-123"}).json()["access_token"]

    checkout = client.post("/v1/billing/checkout-session", json={"plan_id": "starter"}, headers={"Authorization": f"Bearer {token}"})
    assert checkout.status_code == 200
    assert checkout.json() == {"url": "https://checkout.stripe.test/session", "session_id": "cs_test_123"}

    checkout_alias = client.post("/v1/billing/checkout", json={"plan_id": "starter"}, headers={"Authorization": f"Bearer {token}"})
    assert checkout_alias.status_code == 200
    assert checkout_alias.json() == {"url": "https://checkout.stripe.test/session", "session_id": "cs_test_123"}

    portal = client.post("/v1/billing/customer-portal", headers={"Authorization": f"Bearer {token}"})
    assert portal.status_code == 200
    assert portal.json() == {"url": "https://billing.stripe.test/session", "session_id": "bps_test_123"}

    portal_alias = client.post("/v1/billing/portal", headers={"Authorization": f"Bearer {token}"})
    assert portal_alias.status_code == 200
    assert portal_alias.json() == {"url": "https://billing.stripe.test/session", "session_id": "bps_test_123"}


def test_stripe_webhook_verifies_signature_and_provisions_subscription(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    class FakeStripeBillingClient:
        def __init__(self, settings):
            self.settings = settings

        def construct_event(self, *, payload: bytes, signature: str):
            assert payload == b'{"ignored": true}'
            assert signature == "t=123,v1=abc"
            return {
                "id": "evt_test_123",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "customer": "cus_test_123",
                        "subscription": "sub_test_123",
                        "status": "complete",
                        "payment_status": "paid",
                        "metadata": {"plan_id": "starter"},
                    }
                },
            }

    monkeypatch.setattr("app.main.StripeBillingClient", FakeStripeBillingClient)
    client = make_client(
        tmp_path,
        stripe_secret_key="sk_test_mock",
        stripe_webhook_secret="whsec_mock",
        stripe_success_url="https://example.com/success",
        stripe_cancel_url="https://example.com/cancel",
        stripe_portal_return_url="https://example.com/account",
        stripe_price_starter="price_starter",
    )
    token = client.post("/v1/auth/register", json={"email": "hook@example.com", "password": "billing-pass-123"}).json()["access_token"]
    user = client.app.state.auth_service.user_from_token(token)
    client.app.state.auth_store.set_stripe_customer(user.id, "cus_test_123")

    response = client.post("/v1/billing/stripe-webhook", content=b'{"ignored": true}', headers={"Stripe-Signature": "t=123,v1=abc"})

    assert response.status_code == 200
    assert response.json()["event_type"] == "checkout.session.completed"
    subscription = client.get("/v1/billing/subscription", headers={"Authorization": f"Bearer {token}"})
    assert subscription.status_code == 200
    assert subscription.json()["plan_id"] == "starter"
    assert subscription.json()["subscription_status"] == "active"


def test_stripe_checkout_completed_does_not_activate_unpaid_subscription(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    class FakeStripeBillingClient:
        def __init__(self, settings):
            self.settings = settings

        def construct_event(self, *, payload: bytes, signature: str):
            return {
                "id": "evt_unpaid_checkout",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "customer": "cus_unpaid_123",
                        "subscription": "sub_unpaid_123",
                        "status": "complete",
                        "payment_status": "unpaid",
                        "metadata": {"plan_id": "starter"},
                    }
                },
            }

    monkeypatch.setattr("app.main.StripeBillingClient", FakeStripeBillingClient)
    client = make_client(
        tmp_path,
        stripe_secret_key="sk_test_mock",
        stripe_webhook_secret="whsec_mock",
        stripe_success_url="https://example.com/success",
        stripe_cancel_url="https://example.com/cancel",
        stripe_portal_return_url="https://example.com/account",
        stripe_price_starter="price_starter",
    )
    token = client.post("/v1/auth/register", json={"email": "unpaid@example.com", "password": "billing-pass-123"}).json()["access_token"]
    user = client.app.state.auth_service.user_from_token(token)
    client.app.state.auth_store.set_stripe_customer(user.id, "cus_unpaid_123")

    response = client.post("/v1/billing/stripe-webhook", content=b"{}", headers={"Stripe-Signature": "t=123,v1=abc"})

    assert response.status_code == 200
    subscription = client.get("/v1/billing/subscription", headers={"Authorization": f"Bearer {token}"})
    assert subscription.status_code == 200
    assert subscription.json()["plan_id"] == "free"
    assert subscription.json()["subscription_status"] == "none"


def test_stripe_invoice_paid_provisions_subscription_from_price_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    class FakeStripeBillingClient:
        def __init__(self, settings):
            self.settings = settings

        def construct_event(self, *, payload: bytes, signature: str):
            return {
                "id": "evt_invoice_paid",
                "type": "invoice.paid",
                "data": {
                    "object": {
                        "customer": "cus_invoice_123",
                        "subscription": "sub_invoice_123",
                        "lines": {"data": [{"price": {"id": "price_pro"}}]},
                    }
                },
            }

    monkeypatch.setattr("app.main.StripeBillingClient", FakeStripeBillingClient)
    client = make_client(
        tmp_path,
        stripe_secret_key="sk_test_mock",
        stripe_webhook_secret="whsec_mock",
        stripe_success_url="https://example.com/success",
        stripe_cancel_url="https://example.com/cancel",
        stripe_portal_return_url="https://example.com/account",
        stripe_price_starter="price_starter",
        stripe_price_pro="price_pro",
    )
    token = client.post("/v1/auth/register", json={"email": "invoice@example.com", "password": "billing-pass-123"}).json()["access_token"]
    user = client.app.state.auth_service.user_from_token(token)
    client.app.state.auth_store.set_stripe_customer(user.id, "cus_invoice_123")

    response = client.post("/v1/billing/stripe-webhook", content=b"{}", headers={"Stripe-Signature": "t=123,v1=abc"})

    assert response.status_code == 200
    subscription = client.get("/v1/billing/subscription", headers={"Authorization": f"Bearer {token}"})
    assert subscription.status_code == 200
    assert subscription.json()["plan_id"] == "pro"
    assert subscription.json()["subscription_status"] == "active"

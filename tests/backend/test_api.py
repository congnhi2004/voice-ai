from __future__ import annotations

import math
import struct
import wave
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers import LocalFallbackProvider, OpenAITTSProvider, build_provider


def make_client(tmp_path: Path, **overrides) -> TestClient:
    settings = Settings(
        tts_provider=overrides.pop("tts_provider", "local"),
        audio_storage_dir=tmp_path / "audio",
        video_jobs_dir=tmp_path / "video-jobs",
        audio_base_url=overrides.pop("audio_base_url", "http://testserver"),
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


class FakeOpenAIClient:
    def __init__(self, speech: FakeSpeech):
        self.audio = type("Audio", (), {"speech": speech})()


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


def test_public_product_and_demo_workspace_endpoints(tmp_path: Path):
    client = make_client(tmp_path)

    plans = client.get("/v1/product/plans")
    assert plans.status_code == 200
    plans_body = plans.json()
    assert plans_body["billing"] == {"production_billing": False, "demo_only": True}
    assert plans_body["plans"][0]["id"] == "demo-free"
    assert plans_body["plans"][0]["demo_only"] is True

    capabilities = client.get("/v1/product/capabilities")
    assert capabilities.status_code == 200
    capabilities_body = capabilities.json()
    assert capabilities_body["tts"]["available"] is True
    assert capabilities_body["video_localization"]["target_languages"] == ["vi", "vi-VN"]
    assert capabilities_body["auth"]["mode"] == "local-demo"
    assert capabilities_body["billing"]["production_billing"] is False

    workspace = client.get("/v1/demo/workspace")
    assert workspace.status_code == 200
    workspace_body = workspace.json()
    assert workspace_body["workspace_id"] == "demo"
    assert workspace_body["demo_only"] is True
    assert workspace_body["tts_jobs_available"] is True
    assert workspace_body["video_jobs_available"] is True


def test_demo_auth_register_login_me_logout(tmp_path: Path):
    client = make_client(tmp_path)
    credentials = {"email": "User@Example.com", "password": "local-demo-pass", "name": "Demo User"}

    registered = client.post("/v1/auth/register", json=credentials)
    assert registered.status_code == 200
    registered_body = registered.json()
    assert registered_body["demo_only"] is True
    assert registered_body["user"]["email"] == "user@example.com"
    assert registered_body["access_token"].startswith("demo_")
    assert "password" not in registered.text

    duplicate = client.post("/v1/auth/register", json=credentials)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "demo_user_exists"

    bad_login = client.post("/v1/auth/login", json={"email": "user@example.com", "password": "wrong-pass"})
    assert bad_login.status_code == 401
    assert bad_login.json()["error"]["code"] == "invalid_demo_credentials"

    login = client.post("/v1/auth/login", json={"email": "user@example.com", "password": "local-demo-pass"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "user@example.com"

    logout = client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout.status_code == 200
    assert logout.json() == {"logged_out": True, "demo_only": True}

    after_logout = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert after_logout.status_code == 401
    assert after_logout.json()["error"]["code"] == "invalid_demo_token"

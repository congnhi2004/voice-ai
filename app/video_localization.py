from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .models import (
    AudioOptions,
    ProviderInfo,
    SynthesizeRequest,
    SubtitleSegment,
    VideoArtifact,
    VideoLocalizationStatus,
    VoiceSelection,
)
from .observability import MlflowTracker
from .providers import OpenAITTSProvider, TTSProvider
from .storage import GCSStorage, join_object_name


OPENAI_AUDIO_UPLOAD_LIMIT_BYTES = 25 * 1024 * 1024
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}
SUPPORTED_VIDEO_CONTENT_TYPES = {"video/mp4", "video/webm", "video/quicktime", "video/x-m4v"}


@dataclass(frozen=True)
class LocalizedText:
    source_language: str
    target_language: str
    segments: list[SubtitleSegment]


class VideoValidationError(ValueError):
    """Raised when an uploaded video is not usable as a source MP4."""


class VideoRenderError(RuntimeError):
    """Raised when FFmpeg cannot create a usable localized MP4."""


class VideoProviderError(RuntimeError):
    """Raised when a real localization provider cannot complete a stage."""


class LocalVideoLocalizationProvider:
    name = "local"
    fallback = True
    model = "deterministic-video-localization-demo"

    def transcribe(self, source_language: str, uploaded_bytes: bytes) -> str:
        size_hint = len(uploaded_bytes)
        if source_language.startswith("zh"):
            return f"Demo transcript from uploaded Chinese video, {size_hint} bytes."
        return f"Demo transcript from uploaded English video, {size_hint} bytes."

    def translate_to_vietnamese(self, transcript: str, source_language: str) -> str:
        return f"Ban dich tieng Viet demo: {transcript}"

    def segment(self, transcript: str, translated: str) -> list[SubtitleSegment]:
        duration_ms = max(1500, min(8000, len(translated) * 35))
        return [
            SubtitleSegment(
                index=1,
                start_ms=0,
                end_ms=duration_ms,
                source_text=transcript,
                translated_text=translated,
            )
        ]


class OpenAIVideoLocalizationProvider:
    name = "openai"
    fallback = False

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = f"{settings.openai_transcription_model}+{settings.openai_translation_model}+{settings.openai_tts_model}"
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
            raise VideoProviderError(f"openai unavailable: {self._import_error}")
        if not self.settings.openai_api_key:
            raise VideoProviderError("OPENAI_API_KEY is not set")
        if self._client is None:
            self._client = self._openai_client(api_key=self.settings.openai_api_key)
        return self._client

    def transcribe(self, source_language: str, audio_path: Path) -> str:
        started = time.perf_counter()
        language = normalize_source_language(source_language)
        try:
            with audio_path.open("rb") as audio_file:
                response = self._get_client().audio.transcriptions.create(
                    model=self.settings.openai_transcription_model,
                    file=audio_file,
                    language=None if language == "auto" else language,
                    response_format="json",
                )
        except Exception as exc:
            raise VideoProviderError(f"OpenAI transcription failed: {exc}") from exc
        text = getattr(response, "text", None)
        if text is None and isinstance(response, dict):
            text = response.get("text")
        if text is None:
            text = str(response)
        transcript = text.strip()
        if not transcript:
            raise VideoProviderError("OpenAI transcription returned empty text")
        self.last_transcription_latency_ms = max(1, int((time.perf_counter() - started) * 1000))
        return transcript

    def translate_to_vietnamese(self, transcript: str, source_language: str) -> str:
        started = time.perf_counter()
        prompt = (
            "Translate and lightly adapt this Chinese or English video transcript into natural Vietnamese narration. "
            "Return only the Vietnamese script. Do not add notes, markdown, timestamps, or labels."
        )
        try:
            response = self._get_client().responses.create(
                model=self.settings.openai_translation_model,
                instructions=prompt,
                input=f"Source language: {source_language}\nTranscript:\n{transcript}",
            )
        except Exception as exc:
            raise VideoProviderError(f"OpenAI Vietnamese translation failed: {exc}") from exc
        translated = getattr(response, "output_text", None)
        if not translated:
            translated = _extract_response_text(response)
        translated = translated.strip()
        if not translated:
            raise VideoProviderError("OpenAI translation returned empty text")
        self.last_translation_latency_ms = max(1, int((time.perf_counter() - started) * 1000))
        return translated

    def segment(self, transcript: str, translated: str, duration_ms: int) -> list[SubtitleSegment]:
        return make_single_segment(transcript, translated, duration_ms)


class VideoJobStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.video_jobs_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        return self.root / job_id

    def save_status(self, status: VideoLocalizationStatus) -> None:
        path = self.job_dir(status.job_id) / "status.json"
        path.write_text(status.model_dump_json(indent=2), encoding="utf-8")

    def load_status(self, job_id: str) -> VideoLocalizationStatus | None:
        path = self.job_dir(job_id) / "status.json"
        if not path.exists():
            return None
        return VideoLocalizationStatus.model_validate_json(path.read_text(encoding="utf-8"))

    def artifact_path(self, job_id: str, filename: str) -> Path:
        path = (self.job_dir(job_id) / filename).resolve()
        root = self.job_dir(job_id).resolve()
        if root not in path.parents and path != root:
            raise ValueError("Artifact path escapes job directory")
        return path


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_source_language(source_language: str) -> str:
    value = source_language.strip().lower()
    if value in {"auto", ""}:
        return "auto"
    if value.startswith("zh"):
        return "zh"
    if value.startswith("en"):
        return "en"
    raise VideoValidationError("Only Chinese or English source video is supported.")


def validate_video_upload_metadata(filename: str | None, content_type: str | None, size_bytes: int) -> None:
    suffix = Path(filename or "").suffix.lower()
    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    if suffix and suffix not in SUPPORTED_VIDEO_EXTENSIONS:
        raise VideoValidationError("Unsupported video extension. Use MP4, WebM, MOV, or M4V.")
    if normalized_content_type and normalized_content_type not in SUPPORTED_VIDEO_CONTENT_TYPES and not normalized_content_type.startswith("video/"):
        raise VideoValidationError("Upload must be a supported video file.")
    if size_bytes > OPENAI_AUDIO_UPLOAD_LIMIT_BYTES:
        raise VideoValidationError("Uploaded video exceeds the 25 MB provider limit.")


def make_single_segment(transcript: str, translated: str, duration_ms: int) -> list[SubtitleSegment]:
    duration = max(1500, min(max(duration_ms, 1500), 10 * 60 * 1000))
    return [
        SubtitleSegment(
            index=1,
            start_ms=0,
            end_ms=duration,
            source_text=transcript,
            translated_text=translated,
        )
    ]


def _extract_response_text(response) -> str:
    output = getattr(response, "output", None)
    if not output:
        return ""
    chunks: list[str] = []
    for item in output:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(text)
    return "\n".join(chunks)


def ms_to_srt_time(ms: int) -> str:
    seconds, milli = divmod(ms, 1000)
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02}:{minute:02}:{sec:02},{milli:03}"


def ms_to_vtt_time(ms: int) -> str:
    return ms_to_srt_time(ms).replace(",", ".")


def write_subtitles(job_dir: Path, segments: list[SubtitleSegment]) -> tuple[Path, Path]:
    srt_path = job_dir / "subtitles.vi.srt"
    vtt_path = job_dir / "subtitles.vi.vtt"
    srt_blocks = []
    vtt_blocks = ["WEBVTT", ""]
    for segment in segments:
        srt_blocks.append(
            f"{segment.index}\n{ms_to_srt_time(segment.start_ms)} --> {ms_to_srt_time(segment.end_ms)}\n{segment.translated_text}\n"
        )
        vtt_blocks.append(
            f"{ms_to_vtt_time(segment.start_ms)} --> {ms_to_vtt_time(segment.end_ms)}\n{segment.translated_text}\n"
        )
    srt_path.write_text("\n".join(srt_blocks), encoding="utf-8")
    vtt_path.write_text("\n".join(vtt_blocks), encoding="utf-8")
    return srt_path, vtt_path


def artifact(settings: Settings, job_id: str, kind: str, path: Path, content_type: str, artifact_storage: GCSStorage | None = None) -> VideoArtifact:
    if artifact_storage is not None:
        object_name = video_object_name(settings, job_id, kind, path.name)
        stored = artifact_storage.upload_file(path, object_name, content_type)
        return VideoArtifact(
            kind=kind,
            path=stored.path,
            url=stored.url,
            bytes=stored.bytes,
            checksum_sha256=stored.checksum_sha256,
            content_type=stored.content_type,
        )
    return VideoArtifact(
        kind=kind,
        path=str(path),
        url=f"{settings.service_base_url}/v1/video-localization/jobs/{job_id}/artifacts/{path.name}",
        bytes=path.stat().st_size,
        checksum_sha256=checksum(path),
        content_type=content_type,
    )


def video_object_name(settings: Settings, job_id: str, kind: str, filename: str) -> str:
    if kind == "source_video":
        prefix = settings.gcs_source_video_prefix
    elif kind == "localized_video":
        prefix = settings.gcs_rendered_video_prefix
    else:
        prefix = settings.gcs_intermediate_prefix
    return join_object_name(prefix, f"{job_id}/{filename}")


def _ffprobe_path(settings: Settings) -> str | None:
    ffmpeg = shutil.which(settings.ffmpeg_path)
    if ffmpeg:
        sibling = Path(ffmpeg).with_name("ffprobe")
        if sibling.exists():
            return str(sibling)
    return shutil.which("ffprobe")


def _top_level_mp4_boxes(data: bytes) -> set[str]:
    boxes: set[str] = set()
    offset = 0
    while offset + 8 <= len(data):
        size = int.from_bytes(data[offset : offset + 4], "big")
        box_type = data[offset + 4 : offset + 8]
        header_size = 8
        if size == 1:
            if offset + 16 > len(data):
                raise VideoValidationError("MP4 box has an incomplete extended size header.")
            size = int.from_bytes(data[offset + 8 : offset + 16], "big")
            header_size = 16
        elif size == 0:
            size = len(data) - offset
        if size < header_size or offset + size > len(data):
            label = box_type.decode("ascii", errors="replace")
            raise VideoValidationError(f"MP4 box {label!r} has an invalid size.")
        boxes.add(box_type.decode("ascii", errors="ignore"))
        offset += size
    return boxes


def validate_mp4_container(path: Path, settings: Settings) -> None:
    data = path.read_bytes()
    if len(data) < 32:
        raise VideoValidationError("Uploaded MP4 is too small to contain a playable video.")
    try:
        boxes = _top_level_mp4_boxes(data)
    except VideoValidationError:
        raise
    except Exception as exc:
        raise VideoValidationError(f"Uploaded MP4 could not be parsed: {exc}") from exc
    if "ftyp" not in boxes:
        raise VideoValidationError("Uploaded file is missing the MP4 ftyp box.")
    if "mdat" not in boxes:
        raise VideoValidationError("Uploaded MP4 has no media data.")
    if "moov" not in boxes and "moof" not in boxes:
        raise VideoValidationError("Uploaded MP4 is missing movie metadata.")

    ffprobe = _ffprobe_path(settings)
    if not ffprobe:
        return
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_type",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "ffprobe rejected the uploaded MP4").strip()
        raise VideoValidationError(f"Uploaded MP4 is not a valid playable video: {detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoValidationError("Uploaded MP4 validation timed out.") from exc
    try:
        streams = json.loads(completed.stdout or "{}").get("streams", [])
    except json.JSONDecodeError as exc:
        raise VideoValidationError("Uploaded MP4 validation returned malformed ffprobe output.") from exc
    if not any(stream.get("codec_type") == "video" for stream in streams):
        raise VideoValidationError("Uploaded MP4 does not contain a video stream.")


def probe_video(path: Path, settings: Settings) -> int:
    ffprobe = _ffprobe_path(settings)
    if not ffprobe:
        raise VideoValidationError("ffprobe is required for real video localization.")
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "ffprobe rejected the uploaded video").strip()
        raise VideoValidationError(f"Uploaded video is not playable: {detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoValidationError("Uploaded video probe timed out.") from exc
    try:
        data = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise VideoValidationError("Uploaded video probe returned malformed ffprobe output.") from exc
    streams = data.get("streams", [])
    if not any(stream.get("codec_type") == "video" for stream in streams):
        raise VideoValidationError("Uploaded video does not contain a video stream.")
    if not any(stream.get("codec_type") == "audio" for stream in streams):
        raise VideoValidationError("Uploaded video does not contain an audio stream to transcribe.")
    try:
        duration_ms = int(float(data.get("format", {}).get("duration") or 0) * 1000)
    except (TypeError, ValueError):
        duration_ms = 0
    return max(duration_ms, 1500)


def extract_audio(settings: Settings, input_video: Path, output_audio: Path) -> None:
    ffmpeg = shutil.which(settings.ffmpeg_path)
    if not ffmpeg:
        raise VideoValidationError("ffmpeg is required to extract audio for real video localization.")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(input_video),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "64k",
        str(output_audio),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "ffmpeg audio extraction failed").strip()
        raise VideoRenderError(f"FFmpeg could not extract source audio: {detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoRenderError("FFmpeg audio extraction timed out.") from exc
    if not output_audio.exists() or output_audio.stat().st_size == 0:
        raise VideoRenderError("FFmpeg did not produce extracted audio.")
    if output_audio.stat().st_size > OPENAI_AUDIO_UPLOAD_LIMIT_BYTES:
        raise VideoValidationError("Extracted audio exceeds the 25 MB provider upload limit.")


def render_or_copy_video(settings: Settings, input_video: Path, vietnamese_audio: Path, subtitles: Path, output_video: Path) -> str | None:
    ffmpeg = shutil.which(settings.ffmpeg_path)
    if not ffmpeg:
        shutil.copyfile(input_video, output_video)
        return "ffmpeg not available; final MP4 is a validated local demo copy of the uploaded video while audio/subtitle artifacts are generated separately"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(input_video),
        "-i",
        str(vietnamese_audio),
        "-i",
        str(subtitles),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-map",
        "2:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-c:s",
        "mov_text",
        "-metadata:s:a:0",
        "language=vie",
        "-metadata:s:s:0",
        "language=vie",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_video),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
        validate_mp4_container(output_video, settings)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "ffmpeg mux failed").strip()
        if output_video.exists():
            output_video.unlink()
        raise VideoRenderError(f"FFmpeg could not mux localized MP4: {detail}") from exc
    except Exception as exc:
        if output_video.exists():
            output_video.unlink()
        raise VideoRenderError(f"Localized MP4 validation failed: {exc}") from exc
    return None


def safe_source_filename(input_filename: str) -> str:
    name = Path(input_filename).name or "source.mp4"
    if Path(name).suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
        return f"{Path(name).stem or 'source'}.mp4"
    return name


def build_video_provider(settings: Settings):
    requested = settings.localization_provider
    if requested == "local":
        return LocalVideoLocalizationProvider()
    if requested == "openai":
        return OpenAIVideoLocalizationProvider(settings)
    if settings.openai_api_key:
        return OpenAIVideoLocalizationProvider(settings)
    return LocalVideoLocalizationProvider()


def tts_provider_for_video(settings: Settings, current_provider: TTSProvider) -> TTSProvider:
    if settings.openai_api_key and current_provider.name != "openai":
        openai_provider = OpenAITTSProvider(settings)
        if openai_provider.healthcheck().ready:
            return openai_provider
    return current_provider


def localize_video(
    *,
    settings: Settings,
    store: VideoJobStore,
    tracker: MlflowTracker,
    tts_provider: TTSProvider,
    request_id: str,
    job_id: str,
    input_filename: str,
    input_content_type: str | None,
    uploaded_bytes: bytes,
    source_language: str,
    voice_name: str | None,
    artifact_storage: GCSStorage | None = None,
) -> VideoLocalizationStatus:
    started = time.perf_counter()
    job_dir = store.job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    source_path = job_dir / safe_source_filename(input_filename)
    source_path.write_bytes(uploaded_bytes)
    validate_video_upload_metadata(input_filename, input_content_type, len(uploaded_bytes))

    provider = build_video_provider(settings)
    if provider.name == "local":
        validate_mp4_container(source_path, settings)
        transcript = provider.transcribe(source_language, uploaded_bytes)
        translated = provider.translate_to_vietnamese(transcript, source_language)
        segments = provider.segment(transcript, translated)
    else:
        normalize_source_language(source_language)
        duration_ms = probe_video(source_path, settings)
        extracted_audio_path = job_dir / "source-audio.mp3"
        extract_audio(settings, source_path, extracted_audio_path)
        transcript = provider.transcribe(source_language, extracted_audio_path)
        translated = provider.translate_to_vietnamese(transcript, source_language)
        segments = provider.segment(transcript, translated, duration_ms)
    transcript_path = job_dir / "transcript.json"
    transcript_path.write_text(
        json.dumps(
            {
                "source_language": source_language,
                "target_language": "vi",
                "segments": [segment.model_dump() for segment in segments],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    srt_path, vtt_path = write_subtitles(job_dir, segments)

    video_tts_provider = tts_provider_for_video(settings, tts_provider)
    tts_request = SynthesizeRequest(
        text=translated,
        voice=VoiceSelection(language_code="vi-VN", name=voice_name or None, ssml_gender="NEUTRAL"),
        audio=AudioOptions(encoding="LINEAR16", sample_rate_hz=24000),
        metadata={"video_job_id": job_id},
    )
    tts_result = video_tts_provider.synthesize(tts_request)
    audio_path = job_dir / "voiceover.vi.wav"
    audio_path.write_bytes(tts_result.audio_bytes)
    output_video = job_dir / "localized.vi.mp4"
    warnings = []
    mux_warning = render_or_copy_video(settings, source_path, audio_path, srt_path, output_video)
    if mux_warning:
        warnings.append(mux_warning)

    latency_ms = max(1, int((time.perf_counter() - started) * 1000))
    artifacts = [
        artifact(settings, job_id, "source_video", source_path, input_content_type or "video/mp4", artifact_storage),
        *(
            [artifact(settings, job_id, "source_audio", extracted_audio_path, "audio/mpeg", artifact_storage)]
            if provider.name != "local"
            else []
        ),
        artifact(settings, job_id, "transcript", transcript_path, "application/json", artifact_storage),
        artifact(settings, job_id, "subtitles_srt", srt_path, "application/x-subrip", artifact_storage),
        artifact(settings, job_id, "subtitles_vtt", vtt_path, "text/vtt", artifact_storage),
        artifact(settings, job_id, "voiceover_audio", audio_path, "audio/wav", artifact_storage),
        artifact(settings, job_id, "localized_video", output_video, "video/mp4", artifact_storage),
    ]
    mlflow = tracker.track_synthesis(
        request_id=request_id,
        job_id=job_id,
        provider=f"video-{provider.name}",
        fallback=provider.fallback,
        environment=settings.environment,
        voice_name=voice_name or getattr(video_tts_provider, "settings", settings).openai_tts_voice if video_tts_provider.name == "openai" else voice_name or "local-vi-VN-test-voice",
        language_code="vi-VN",
        audio_encoding="LINEAR16",
        speaking_rate=1.0,
        pitch=0.0,
        sample_rate_hz=24000,
        input_type="video",
        input_chars=len(translated),
        latency_ms=latency_ms,
        provider_latency_ms=latency_ms,
        duration_ms=tts_result.duration_ms,
        audio_bytes=audio_path.stat().st_size,
        success=True,
        audio_path=audio_path,
        checksum_sha256=checksum(audio_path),
        status="succeeded",
    )
    if mlflow.warning and settings.environment != "production":
        warnings.append(mlflow.warning)
    status = VideoLocalizationStatus(
        job_id=job_id,
        status="succeeded",
        source_language=source_language,
        target_language="vi",
        provider=ProviderInfo(name=provider.name, fallback=provider.fallback, model=provider.model),
        input_filename=input_filename,
        input_bytes=len(uploaded_bytes),
        transcript_chars=len(transcript),
        translated_chars=len(translated),
        segments=segments,
        artifacts=artifacts,
        latency_ms=latency_ms,
        observability={"request_id": request_id, "mlflow_run_id": mlflow.run_id, "warnings": [mlflow.warning] if mlflow.warning else []},
        warnings=warnings,
    )
    store.save_status(status)
    return status

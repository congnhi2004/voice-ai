from __future__ import annotations

import hashlib
from datetime import timedelta
from dataclasses import dataclass
import mimetypes
from pathlib import Path
from typing import BinaryIO

from .config import Settings


@dataclass(frozen=True)
class StoredAudio:
    path: Path
    url: str
    bytes: int
    checksum_sha256: str
    storage_uri: str


@dataclass(frozen=True)
class StoredArtifact:
    path: str
    url: str
    bytes: int
    checksum_sha256: str
    content_type: str
    storage_uri: str
    local_path: Path | None = None


class LocalAudioStorage:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.audio_storage_dir

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        probe = self.root / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)

    def health(self) -> tuple[bool, str | None]:
        try:
            self.ensure_ready()
            return True, None
        except Exception as exc:
            return False, str(exc)

    def save(self, job_id: str, extension: str, audio_bytes: bytes) -> StoredAudio:
        self.ensure_ready()
        filename = f"{job_id}.{extension}"
        path = self.root / filename
        path.write_bytes(audio_bytes)
        checksum = hashlib.sha256(audio_bytes).hexdigest()
        return StoredAudio(
            path=path,
            url=f"{self.settings.audio_public_base_url}/{filename}",
            bytes=len(audio_bytes),
            checksum_sha256=checksum,
            storage_uri=str(path),
        )


class GCSStorage:
    def __init__(self, settings: Settings, bucket_name: str, client=None):
        self.settings = settings
        self.bucket_name = bucket_name
        self._client = client
        self._bucket = None

    @property
    def mode(self) -> str:
        return "gcs"

    def _get_client(self):
        if self._client is None:
            try:
                from google.cloud import storage
            except Exception as exc:  # pragma: no cover - depends on optional dependency install
                raise RuntimeError("google-cloud-storage is required when storage provider is gcs") from exc
            self._client = storage.Client(project=self.settings.gcp_project_id)
        return self._client

    def _get_bucket(self):
        if self._bucket is None:
            self._bucket = self._get_client().bucket(self.bucket_name)
        return self._bucket

    def ensure_ready(self) -> None:
        if not self.bucket_name:
            raise RuntimeError("GCS bucket is not configured")
        self._get_bucket()

    def health(self) -> tuple[bool, str | None]:
        try:
            self.ensure_ready()
            return True, None
        except Exception as exc:
            return False, str(exc)

    def upload_bytes(self, object_name: str, data: bytes, content_type: str) -> StoredArtifact:
        checksum = hashlib.sha256(data).hexdigest()
        blob = self._get_bucket().blob(object_name)
        blob.upload_from_string(data, content_type=content_type)
        url = self.signed_url(object_name, method="GET")
        return StoredArtifact(
            path=f"gs://{self.bucket_name}/{object_name}",
            url=url,
            bytes=len(data),
            checksum_sha256=checksum,
            content_type=content_type,
            storage_uri=f"gs://{self.bucket_name}/{object_name}",
        )

    def upload_file(self, local_path: Path, object_name: str, content_type: str | None = None) -> StoredArtifact:
        resolved_content_type = content_type or mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
        blob = self._get_bucket().blob(object_name)
        blob.upload_from_filename(str(local_path), content_type=resolved_content_type)
        return StoredArtifact(
            path=f"gs://{self.bucket_name}/{object_name}",
            url=self.signed_url(object_name, method="GET"),
            bytes=local_path.stat().st_size,
            checksum_sha256=file_checksum(local_path),
            content_type=resolved_content_type,
            storage_uri=f"gs://{self.bucket_name}/{object_name}",
            local_path=local_path,
        )

    def download_bytes(self, storage_uri: str) -> bytes:
        object_name = self.object_name_from_uri(storage_uri)
        blob = self._get_bucket().blob(object_name)
        return blob.download_as_bytes()

    def download_to_filename(self, storage_uri: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        object_name = self.object_name_from_uri(storage_uri)
        blob = self._get_bucket().blob(object_name)
        blob.download_to_filename(str(destination))

    def object_name_from_uri(self, storage_uri: str) -> str:
        prefix = f"gs://{self.bucket_name}/"
        if not storage_uri.startswith(prefix):
            raise ValueError("GCS URI does not belong to the configured artifact bucket")
        return storage_uri.removeprefix(prefix)

    def signed_url(self, object_name: str, method: str = "GET", content_type: str | None = None) -> str:
        blob = self._get_bucket().blob(object_name)
        kwargs = {
            "version": "v4",
            "expiration": timedelta(seconds=self.settings.signed_url_ttl_seconds),
            "method": method,
        }
        if content_type:
            kwargs["content_type"] = content_type
        return blob.generate_signed_url(**kwargs)


class GCSAudioStorage:
    def __init__(self, settings: Settings, gcs: GCSStorage):
        self.settings = settings
        self.root = settings.audio_storage_dir
        self.gcs = gcs

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.gcs.ensure_ready()

    def health(self) -> tuple[bool, str | None]:
        return self.gcs.health()

    def save(self, job_id: str, extension: str, audio_bytes: bytes) -> StoredAudio:
        self.root.mkdir(parents=True, exist_ok=True)
        filename = f"{job_id}.{extension}"
        path = self.root / filename
        path.write_bytes(audio_bytes)
        content_type = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
        }.get(extension.lower(), "application/octet-stream")
        object_name = join_object_name(self.settings.gcs_audio_prefix, filename)
        stored = self.gcs.upload_bytes(object_name, audio_bytes, content_type)
        return StoredAudio(
            path=path,
            url=stored.url,
            bytes=stored.bytes,
            checksum_sha256=stored.checksum_sha256,
            storage_uri=stored.storage_uri,
        )


def file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        return stream_checksum(handle, digest)


def stream_checksum(handle: BinaryIO, digest) -> str:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def join_object_name(prefix: str, filename: str) -> str:
    clean_prefix = prefix.strip("/")
    clean_filename = filename.lstrip("/")
    if not clean_prefix:
        return clean_filename
    return f"{clean_prefix}/{clean_filename}"


def build_audio_storage(settings: Settings, client=None):
    if settings.audio_storage_provider == "gcs":
        if not settings.gcs_audio_bucket:
            raise RuntimeError("GCS_AUDIO_BUCKET is required when audio storage provider is gcs")
        return GCSAudioStorage(settings, GCSStorage(settings, settings.gcs_audio_bucket, client=client))
    return LocalAudioStorage(settings)


def build_artifact_storage(settings: Settings, client=None) -> GCSStorage | None:
    if settings.video_artifact_storage_provider == "gcs":
        if not settings.gcs_artifact_bucket:
            raise RuntimeError("GCS_ARTIFACT_BUCKET is required when video storage provider is gcs")
        return GCSStorage(settings, settings.gcs_artifact_bucket, client=client)
    return None

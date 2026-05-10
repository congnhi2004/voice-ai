from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .config import Settings


@dataclass(frozen=True)
class StoredAudio:
    path: Path
    url: str
    bytes: int
    checksum_sha256: str


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
        )

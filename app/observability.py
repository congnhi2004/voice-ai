from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Settings


@dataclass(frozen=True)
class MlflowResult:
    run_id: str | None
    warning: str | None = None


class MlflowTracker:
    def __init__(self, settings: Settings):
        self.settings = settings

    def readiness(self) -> tuple[bool, bool, str | None]:
        if not self.settings.mlflow_tracking_uri:
            return False, True, "MLFLOW_TRACKING_URI is not configured"
        try:
            import mlflow

            mlflow.set_tracking_uri(self.settings.mlflow_tracking_uri)
            mlflow.set_experiment(self.settings.mlflow_experiment_name)
            return True, True, None
        except Exception as exc:
            return True, False, str(exc)

    def track_synthesis(
        self,
        *,
        request_id: str,
        job_id: str,
        provider: str,
        fallback: bool,
        environment: str,
        voice_name: str | None,
        language_code: str,
        audio_encoding: str,
        speaking_rate: float,
        pitch: float,
        sample_rate_hz: int,
        input_type: str,
        input_chars: int,
        latency_ms: int,
        provider_latency_ms: int,
        duration_ms: int,
        audio_bytes: int,
        success: bool,
        audio_path: Path,
        checksum_sha256: str,
        status: str,
    ) -> MlflowResult:
        if not self.settings.mlflow_tracking_uri:
            return MlflowResult(run_id=None, warning="MLflow tracking URI not configured")
        try:
            import mlflow

            mlflow.set_tracking_uri(self.settings.mlflow_tracking_uri)
            mlflow.set_experiment(self.settings.mlflow_experiment_name)
            with mlflow.start_run(run_name=job_id) as run:
                mlflow.set_tags(
                    {
                        "job_id": job_id,
                        "request_id": request_id,
                        "provider": provider,
                        "environment": environment,
                        "service_version": self.settings.version,
                        "fallback": str(fallback).lower(),
                        "status": status,
                    }
                )
                mlflow.log_params(
                    {
                        "voice_name": voice_name or "",
                        "language_code": language_code,
                        "audio_encoding": audio_encoding,
                        "speaking_rate": speaking_rate,
                        "pitch": pitch,
                        "sample_rate_hz": sample_rate_hz,
                        "input_type": input_type,
                        "input_chars": input_chars,
                    }
                )
                mlflow.log_metrics(
                    {
                        "latency_ms": latency_ms,
                        "provider_latency_ms": provider_latency_ms,
                        "duration_ms": duration_ms,
                        "audio_bytes": audio_bytes,
                        "input_chars": input_chars,
                        "success": 1.0 if success else 0.0,
                    }
                )
                artifact_ref: dict[str, Any] = {
                    "audio_path": str(audio_path),
                    "checksum_sha256": checksum_sha256,
                    "audio_bytes": audio_bytes,
                    "status": status,
                }
                with tempfile.TemporaryDirectory() as tmpdir:
                    ref_path = Path(tmpdir) / "audio_reference.json"
                    ref_path.write_text(json.dumps(artifact_ref, indent=2), encoding="utf-8")
                    mlflow.log_artifact(str(ref_path), artifact_path="metadata")
                if self.settings.mlflow_log_audio_artifacts and audio_path.exists():
                    mlflow.log_artifact(str(audio_path), artifact_path="audio")
                return MlflowResult(run_id=run.info.run_id)
        except Exception as exc:
            return MlflowResult(run_id=None, warning=f"MLflow tracking failed: {exc}")

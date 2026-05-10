from __future__ import annotations

import logging
import shutil
import time
import uuid
from contextvars import ContextVar
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .auth_billing import (
    AuthBillingError,
    AuthBillingStore,
    AuthNotConfiguredError,
    AuthService,
    BillingNotConfiguredError,
    BillingService,
    StripeBillingClient,
)
from .config import Settings, load_settings
from .frontend_support import capabilities, demo_workspace_status, pricing_plans
from .logging_config import configure_logging
from .models import (
    AudioInfo,
    AuthLoginRequest,
    AuthRegisterRequest,
    BillingSessionResponse,
    CheckoutSessionRequest,
    ObservabilityInfo,
    ProviderInfo,
    SubscriptionState,
    SynthesizeRequest,
    SynthesizeResponse,
)
from .observability import MlflowTracker
from .providers import UnsupportedVoiceError, build_provider
from .storage import build_artifact_storage, build_audio_storage
from .video_localization import (
    OPENAI_AUDIO_UPLOAD_LIMIT_BYTES,
    VideoJobStore,
    VideoProviderError,
    VideoRenderError,
    VideoValidationError,
    build_video_provider,
    localize_video,
    validate_video_upload_metadata,
)

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
logger = logging.getLogger("voice_ai")


def redact_configured_secrets(message: str, settings: Settings) -> str:
    redacted = message
    for secret in (settings.openai_api_key,):
        if secret:
            redacted = redacted.replace(secret, "[redacted]")
    return redacted


def problem(code: str, message: str, request_id: str, status_code: int, details: dict | None = None, job_id: str | None = None) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details or {}}, "request_id": request_id}
    if job_id:
        body["job_id"] = job_id
    return JSONResponse(status_code=status_code, content=body)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    configure_logging(settings.log_level)
    storage = build_audio_storage(settings)
    artifact_storage = build_artifact_storage(settings)
    provider = build_provider(settings)
    tracker = MlflowTracker(settings)
    video_store = VideoJobStore(settings)
    auth_store = AuthBillingStore(settings.auth_storage_path)
    auth_service = AuthService(settings, auth_store)
    billing_service = BillingService(settings, auth_store, StripeBillingClient(settings))

    app = FastAPI(title="Voice AI TTS API", version=settings.version)
    app.state.settings = settings
    app.state.storage = storage
    app.state.artifact_storage = artifact_storage
    app.state.provider = provider
    app.state.tracker = tracker
    app.state.video_store = video_store
    app.state.auth_store = auth_store
    app.state.auth_service = auth_service
    app.state.billing_service = billing_service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Job-ID"],
    )

    settings.audio_storage_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/audio", StaticFiles(directory=str(settings.audio_storage_dir)), name="audio")

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex}"
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            latency_ms = int((time.perf_counter() - started) * 1000)
            status_code = response.status_code if response else 500
            if response is not None:
                response.headers["X-Request-ID"] = request_id
            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "route": request.url.path,
                    "method": request.method,
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                },
            )
            request_id_var.reset(token)

    async def require_api_key(authorization: str | None = Header(default=None), x_api_key: str | None = Header(default=None)) -> None:
        if not settings.auth_enabled:
            return
        candidate = x_api_key
        if not candidate and authorization and authorization.lower().startswith("bearer "):
            candidate = authorization.split(" ", 1)[1].strip()
        if not candidate:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "missing_api_key", "message": "API key is required."})
        if candidate not in settings.api_keys:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "invalid_api_key", "message": "API key is invalid."})

    def bearer_token(authorization: str | None) -> str | None:
        if authorization and authorization.lower().startswith("bearer "):
            return authorization.split(" ", 1)[1].strip()
        return None

    async def current_user(authorization: str | None = Header(default=None)):
        token = bearer_token(authorization)
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "missing_bearer_token", "message": "Bearer token is required."})
        try:
            user = auth_service.user_from_token(token)
        except AuthNotConfiguredError as exc:
            raise HTTPException(status_code=503, detail={"code": "auth_not_configured", "message": str(exc)}) from exc
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "invalid_bearer_token", "message": "Bearer token is invalid or expired."})
        return user

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "http_error", "message": str(exc.detail)}
        return problem(
            detail.get("code", "http_error"),
            detail.get("message", str(exc.detail)),
            request_id_var.get(),
            exc.status_code,
            details=detail.get("details", {}),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return problem("validation_error", "Request validation failed.", request_id_var.get(), status.HTTP_422_UNPROCESSABLE_ENTITY, {"errors": exc.errors()})

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "service": settings.service_name, "version": settings.version}

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": settings.service_name, "version": settings.version}

    @app.get("/v1/product/plans")
    async def product_plans():
        return {
            "plans": [plan.model_dump() for plan in pricing_plans(settings)],
            "billing": {
                "production_billing": settings.stripe_configured,
                "mode": "stripe-subscriptions" if settings.stripe_configured else "not-configured",
                "checkout_available": settings.stripe_configured,
            },
        }

    @app.get("/v1/product/capabilities")
    async def product_capabilities():
        return capabilities(settings, provider_name=provider.name, ffmpeg_available=shutil.which(settings.ffmpeg_path) is not None)

    @app.get("/v1/demo/workspace")
    async def demo_workspace():
        return demo_workspace_status(settings, ffmpeg_available=shutil.which(settings.ffmpeg_path) is not None)

    @app.post("/v1/auth/register")
    async def register(payload: AuthRegisterRequest):
        try:
            user, token = auth_service.register(email=payload.email, password=payload.password, name=payload.name)
            return {"user": user.model_dump(), "access_token": token, "token_type": "bearer", "expires_in": settings.auth_access_token_expire_minutes * 60}
        except AuthNotConfiguredError as exc:
            return problem("auth_not_configured", str(exc), request_id_var.get(), 503)
        except AuthBillingError:
            return problem("user_exists", "A user already exists for this email.", request_id_var.get(), 409)

    @app.post("/v1/auth/login")
    async def login(payload: AuthLoginRequest):
        try:
            result = auth_service.login(email=payload.email, password=payload.password)
        except AuthNotConfiguredError as exc:
            return problem("auth_not_configured", str(exc), request_id_var.get(), 503)
        if result is None:
            return problem("invalid_credentials", "Invalid email or password.", request_id_var.get(), 401)
        user, token = result
        return {"user": user.model_dump(), "access_token": token, "token_type": "bearer", "expires_in": settings.auth_access_token_expire_minutes * 60}

    @app.post("/v1/auth/logout")
    async def logout(authorization: str | None = Header(default=None)):
        token = bearer_token(authorization)
        if not token:
            return problem("missing_bearer_token", "Bearer token is required.", request_id_var.get(), 401)
        try:
            logged_out = auth_service.revoke_token(token)
        except AuthNotConfiguredError as exc:
            return problem("auth_not_configured", str(exc), request_id_var.get(), 503)
        if not logged_out:
            return problem("invalid_bearer_token", "Bearer token is invalid or expired.", request_id_var.get(), 401)
        return {"logged_out": True}

    @app.get("/v1/auth/me")
    async def me(user=Depends(current_user)):
        return {"user": user.public().model_dump()}

    @app.get("/v1/billing/subscription", response_model=SubscriptionState)
    async def billing_subscription(user=Depends(current_user)):
        return user.subscription()

    @app.post("/v1/billing/checkout-session", response_model=BillingSessionResponse)
    async def create_checkout_session(payload: CheckoutSessionRequest, user=Depends(current_user)):
        try:
            url, session_id = billing_service.create_checkout_session(user=user, plan_id=payload.plan_id)
            return BillingSessionResponse(url=url, session_id=session_id)
        except BillingNotConfiguredError as exc:
            return problem("billing_not_configured", str(exc), request_id_var.get(), 503)
        except AuthBillingError as exc:
            code = str(exc) or "billing_error"
            return problem(code, "Requested plan cannot be billed.", request_id_var.get(), 400)

    @app.post("/v1/billing/customer-portal", response_model=BillingSessionResponse)
    async def create_customer_portal(user=Depends(current_user)):
        try:
            url, session_id = billing_service.create_portal_session(user=user)
            return BillingSessionResponse(url=url, session_id=session_id)
        except BillingNotConfiguredError as exc:
            return problem("billing_not_configured", str(exc), request_id_var.get(), 503)
        except AuthBillingError:
            return problem("missing_stripe_customer", "No Stripe customer is linked to this user yet.", request_id_var.get(), 409)

    @app.post("/v1/billing/stripe-webhook")
    async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None, alias="Stripe-Signature")):
        if not stripe_signature:
            return problem("missing_stripe_signature", "Stripe-Signature header is required.", request_id_var.get(), 400)
        payload = await request.body()
        try:
            return billing_service.handle_webhook(payload=payload, signature=stripe_signature)
        except BillingNotConfiguredError as exc:
            return problem("billing_not_configured", str(exc), request_id_var.get(), 503)
        except Exception:
            return problem("invalid_stripe_webhook", "Stripe webhook payload or signature is invalid.", request_id_var.get(), 400)

    @app.get("/readyz")
    async def readyz():
        provider_health = provider.healthcheck()
        storage_ready, storage_detail = storage.health()
        mlflow_configured, mlflow_ready, mlflow_detail = tracker.readiness()
        ready = provider_health.ready and storage_ready and mlflow_ready
        body = {
            "status": "ready" if ready else "not_ready",
            "provider": {"name": provider_health.name, "ready": provider_health.ready, "detail": provider_health.detail},
            "storage": {"mode": settings.audio_storage_provider, "ready": storage_ready, "detail": storage_detail},
            "mlflow": {"configured": mlflow_configured, "ready": mlflow_ready, "detail": mlflow_detail},
            "video_localization": {
                "mode": settings.localization_provider,
                "ready": True,
                "ffmpeg_available": shutil.which(settings.ffmpeg_path) is not None,
                "provider": build_video_provider(settings).name,
                "detail": "auto mode uses OpenAI when OPENAI_API_KEY is set; local fallback remains available without credentials",
            },
        }
        return JSONResponse(status_code=200 if ready else 503, content=body)

    @app.get("/v1/voices", dependencies=[Depends(require_api_key)])
    async def voices(language_code: str | None = Query(default=None)):
        try:
            return {"provider": provider.name, "voices": [voice.model_dump() for voice in provider.list_voices(language_code)]}
        except Exception as exc:
            logger.error(
                "voice_list_failed",
                extra={"request_id": request_id_var.get(), "provider": provider.name, "error_code": "provider_unavailable", "error_class": exc.__class__.__name__},
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "provider_unavailable",
                    "message": "Text-to-speech provider is not ready.",
                    "details": {"provider": provider.name, "error": redact_configured_secrets(str(exc), settings)},
                },
            )

    @app.post("/v1/synthesize", response_model=SynthesizeResponse, dependencies=[Depends(require_api_key)])
    async def synthesize(payload: SynthesizeRequest, response: Response, idempotency_key: str | None = Header(default=None)):
        input_chars = len(payload.input_text)
        if input_chars > settings.max_input_chars:
            return problem("input_too_large", "Input exceeds MAX_INPUT_CHARS.", request_id_var.get(), 413, {"max_input_chars": settings.max_input_chars})

        job_id = f"tts_{uuid.uuid4().hex}"
        response.headers["X-Job-ID"] = job_id
        started = time.perf_counter()
        try:
            result = provider.synthesize(payload)
            stored = storage.save(job_id, result.extension, result.audio_bytes)
            latency_ms = max(1, int((time.perf_counter() - started) * 1000))
            audio_encoding = {"audio/wav": "LINEAR16", "audio/mpeg": "MP3", "audio/ogg": "OGG_OPUS"}.get(result.content_type, payload.audio.encoding)
            mlflow = tracker.track_synthesis(
                request_id=request_id_var.get(),
                job_id=job_id,
                provider=result.provider_name,
                fallback=result.fallback,
                environment=settings.environment,
                voice_name=payload.voice.name,
                language_code=payload.voice.language_code,
                audio_encoding=audio_encoding,
                speaking_rate=payload.audio.speaking_rate,
                pitch=payload.audio.pitch,
                sample_rate_hz=result.sample_rate_hz,
                input_type=payload.input_type,
                input_chars=input_chars,
                latency_ms=latency_ms,
                provider_latency_ms=result.provider_latency_ms,
                duration_ms=result.duration_ms,
                audio_bytes=stored.bytes,
                success=True,
                audio_path=stored.path,
                checksum_sha256=stored.checksum_sha256,
                status="succeeded",
            )
            warnings = [mlflow.warning] if mlflow.warning and settings.environment != "production" else []
            logger.info(
                "synthesis_completed",
                extra={
                    "request_id": request_id_var.get(),
                    "job_id": job_id,
                    "provider": result.provider_name,
                    "voice_name": payload.voice.name,
                    "language_code": payload.voice.language_code,
                    "audio_encoding": audio_encoding,
                    "input_type": payload.input_type,
                    "input_chars": input_chars,
                    "latency_ms": latency_ms,
                },
            )
            return SynthesizeResponse(
                job_id=job_id,
                status="succeeded",
                audio_url=stored.url,
                audio_path=str(stored.path),
                duration_ms=result.duration_ms,
                latency_ms=latency_ms,
                provider=ProviderInfo(name=result.provider_name, fallback=result.fallback, model=result.model),
                voice=payload.voice,
                audio=AudioInfo(
                    encoding=audio_encoding,
                    bytes=stored.bytes,
                    sample_rate_hz=result.sample_rate_hz,
                    checksum_sha256=stored.checksum_sha256,
                    content_type=result.content_type,
                ),
                observability=ObservabilityInfo(request_id=request_id_var.get(), mlflow_run_id=mlflow.run_id, warnings=warnings),
                metadata=payload.metadata,
            )
        except UnsupportedVoiceError as exc:
            return problem(
                "unsupported_voice",
                "Requested OpenAI TTS voice is not supported.",
                request_id_var.get(),
                400,
                {"provider": provider.name, "error": str(exc)},
                job_id=job_id,
            )
        except Exception as exc:
            logger.error(
                "synthesis_failed",
                extra={
                    "request_id": request_id_var.get(),
                    "job_id": job_id,
                    "provider": provider.name,
                    "error_code": "synthesis_failed",
                    "error_class": exc.__class__.__name__,
                    "input_chars": input_chars,
                },
            )
            return problem(
                "synthesis_failed",
                "Text-to-speech synthesis failed.",
                request_id_var.get(),
                503,
                {"provider": provider.name, "error": redact_configured_secrets(str(exc), settings)},
                job_id=job_id,
            )

    @app.post("/v1/video-localization/jobs", dependencies=[Depends(require_api_key)])
    async def create_video_localization_job(
        response: Response,
        file: UploadFile = File(..., description="Chinese or English source video"),
        source_language: str = Form(default="en-US"),
        target_language: str = Form(default="vi"),
        voice_name: str | None = Form(default=None),
    ):
        if target_language.lower() not in {"vi", "vi-vn"}:
            return problem("unsupported_target_language", "Only Vietnamese target localization is supported in this backend slice.", request_id_var.get(), 400, {"target_language": target_language})
        job_id = f"vid_{uuid.uuid4().hex}"
        response.headers["X-Job-ID"] = job_id
        uploaded_bytes = await file.read()
        if not uploaded_bytes:
            return problem("empty_upload", "Uploaded video is empty.", request_id_var.get(), 400, job_id=job_id)
        try:
            validate_video_upload_metadata(file.filename, file.content_type, len(uploaded_bytes))
        except VideoValidationError as exc:
            return problem(
                "unsupported_video_upload",
                str(exc),
                request_id_var.get(),
                400,
                {"filename": file.filename, "content_type": file.content_type, "max_bytes": OPENAI_AUDIO_UPLOAD_LIMIT_BYTES},
                job_id=job_id,
            )
        try:
            status_body = localize_video(
                settings=settings,
                store=video_store,
                tracker=tracker,
                tts_provider=provider,
                request_id=request_id_var.get(),
                job_id=job_id,
                input_filename=file.filename or "source.mp4",
                input_content_type=file.content_type,
                uploaded_bytes=uploaded_bytes,
                source_language=source_language,
                voice_name=voice_name,
                artifact_storage=artifact_storage,
            )
            logger.info(
                "video_localization_completed",
                extra={
                    "request_id": request_id_var.get(),
                    "job_id": job_id,
                    "provider": status_body.provider.name,
                    "input_chars": status_body.transcript_chars,
                    "latency_ms": status_body.latency_ms,
                },
            )
            return status_body
        except VideoValidationError as exc:
            logger.info(
                "video_localization_rejected",
                extra={"request_id": request_id_var.get(), "job_id": job_id, "error_code": "invalid_video_upload"},
            )
            return problem("invalid_video_upload", str(exc), request_id_var.get(), 400, {"filename": file.filename, "content_type": file.content_type}, job_id=job_id)
        except VideoRenderError as exc:
            logger.exception("video_render_failed", extra={"request_id": request_id_var.get(), "job_id": job_id, "error_code": "video_render_failed"})
            return problem("video_render_failed", str(exc), request_id_var.get(), 503, {"filename": file.filename}, job_id=job_id)
        except VideoProviderError as exc:
            logger.exception("video_provider_failed", extra={"request_id": request_id_var.get(), "job_id": job_id, "error_code": "video_provider_failed"})
            return problem(
                "video_provider_failed",
                "Video localization provider failed.",
                request_id_var.get(),
                503,
                {"error": redact_configured_secrets(str(exc), settings)},
                job_id=job_id,
            )
        except Exception as exc:
            logger.exception("video_localization_failed", extra={"request_id": request_id_var.get(), "job_id": job_id, "error_code": "video_localization_failed"})
            return problem("video_localization_failed", "Video localization failed.", request_id_var.get(), 500, {"error": redact_configured_secrets(str(exc), settings)}, job_id=job_id)

    @app.get("/v1/video-localization/jobs/{job_id}", dependencies=[Depends(require_api_key)])
    async def get_video_localization_job(job_id: str):
        status_body = video_store.load_status(job_id)
        if status_body is None:
            return problem("job_not_found", "Video localization job was not found.", request_id_var.get(), 404, {"job_id": job_id})
        if artifact_storage is not None:
            status_body = status_body.model_copy(
                update={
                    "artifacts": [
                        artifact.model_copy(update={"url": artifact_storage.signed_url(artifact.path.removeprefix(f"gs://{artifact_storage.bucket_name}/"))})
                        if artifact.path.startswith(f"gs://{artifact_storage.bucket_name}/")
                        else artifact
                        for artifact in status_body.artifacts
                    ]
                }
            )
        return status_body

    @app.get("/v1/video-localization/jobs/{job_id}/artifacts/{filename}", dependencies=[Depends(require_api_key)])
    async def get_video_localization_artifact(job_id: str, filename: str):
        from fastapi.responses import FileResponse

        status_body = video_store.load_status(job_id)
        if artifact_storage is not None and status_body is not None:
            for artifact in status_body.artifacts:
                if artifact.path.rsplit("/", 1)[-1] == filename and artifact.path.startswith(f"gs://{artifact_storage.bucket_name}/"):
                    object_name = artifact.path.removeprefix(f"gs://{artifact_storage.bucket_name}/")
                    return RedirectResponse(url=artifact_storage.signed_url(object_name), status_code=307)
        try:
            path = video_store.artifact_path(job_id, filename)
        except ValueError:
            return problem("invalid_artifact_path", "Invalid artifact path.", request_id_var.get(), 400, {"filename": filename})
        if not path.exists() or not path.is_file():
            return problem("artifact_not_found", "Video localization artifact was not found.", request_id_var.get(), 404, {"job_id": job_id, "filename": filename})
        media_type = {
            ".mp4": "video/mp4",
            ".wav": "audio/wav",
            ".srt": "application/x-subrip",
            ".vtt": "text/vtt",
            ".json": "application/json",
        }.get(path.suffix.lower(), "application/octet-stream")
        return FileResponse(path, media_type=media_type, filename=path.name)

    return app


app = create_app()

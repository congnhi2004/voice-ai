# Voice AI Project Brief

## Product

Voice AI is a production video localization, transcription, translation, subtitle, and text-to-speech product. Users can upload a Chinese or English video and receive Vietnamese transcript/script, Vietnamese subtitle files, Vietnamese voice/dub audio, and a downloadable final localized MP4.

The first sellable product is a reliable Vietnamese localization pipeline for short-form and business videos, backed by Google Speech-to-Text, Google Cloud Translation, Google Cloud Text-to-Speech, FFmpeg media processing, MLflow tracking, and Cloud Run/GCP deployment.

For a step-by-step learning path from empty workspace to production readiness, use `docs/tutorial-from-zero-to-production.md`.

## Outcomes

- Users can upload English or Chinese source videos and download Vietnamese localized artifacts.
- Users can list supported voices, synthesize Vietnamese text or SSML, and retrieve generated audio.
- Users can retrieve Vietnamese transcript/script, SRT/VTT subtitles, Vietnamese TTS audio, and final rendered MP4 outputs.
- Operators can deploy the service to Cloud Run and observe usage, latency, failures, and provider behavior.
- Product and QA can verify each release through concrete acceptance evidence.
- Implementers can work from stable API, security, observability, and deployment contracts.

## Target Customers

- Content production teams localizing English/Chinese clips into Vietnamese.
- Education, training, and sales teams repurposing source video into Vietnamese assets.
- SaaS teams embedding voice previews in workflows.
- Internal business tools that need auditable, centralized video localization and TTS generation.

## MVP Scope

- FastAPI service with health, readiness, voices, synthesize, upload, localization job, status, artifact, and download routes.
- Video upload for English or Chinese source files.
- Long-running localization jobs that extract audio, transcribe source speech, translate to Vietnamese, generate Vietnamese subtitles, synthesize Vietnamese voice audio, and render a final localized MP4.
- Google Speech-to-Text provider for asynchronous or long-audio transcription.
- Google Cloud Translation provider for Vietnamese translation.
- Google Cloud Text-to-Speech provider using synchronous synthesis.
- FFmpeg-based media processing for audio extraction, subtitle mux/burn-in, audio replacement/mix, and MP4 rendering.
- Local demo provider that does not require Google credentials and can generate deterministic placeholder transcript, subtitle, audio, and video artifacts.
- JSON response containing job id, audio URL/path, duration, latency, provider, and metadata.
- Local file storage for development; production storage path designed for Cloud Run and Cloud Storage.
- MLflow Tracking for request/job-level runs, parameters, metrics, tags, and media artifact references.
- API key protection, CORS allowlist, request size limits, and structured error handling.
- CI/CD pipeline with lint, type/test, container build, and Cloud Run deployment gates.

## Non-Goals For MVP

- Custom voice training.
- Long-form asynchronous audio generation.
- Real-time streaming synthesis.
- Human subtitle editing workflow.
- Fully automatic lip-sync or voice cloning.
- User billing portal.
- Full multi-tenant admin console.

## Official References

- Google Cloud Speech-to-Text asynchronous recognition: https://cloud.google.com/speech-to-text/docs/async-recognize
- Google Cloud Speech-to-Text supported languages: https://cloud.google.com/speech-to-text/docs/speech-to-text-supported-languages
- Google Cloud Translation supported languages: https://cloud.google.com/translate/docs/languages
- Google Cloud Text-to-Speech `text:synthesize`: https://docs.cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize
- Google create audio guide: https://cloud.google.com/text-to-speech/docs/create-audio
- Cloud Run FastAPI quickstart: https://docs.cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-fastapi-service
- Cloud Run overview: https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run
- MLflow Tracking docs: https://mlflow.org/docs/latest/ml/tracking
- Google Cloud Video Intelligence speech transcription: https://cloud.google.com/video-intelligence/docs/speech-transcription
- FFmpeg documentation: https://ffmpeg.org/documentation.html

## Current Source Notes

- Google Speech-to-Text supports asynchronous recognition for longer audio files and has language support covering English and Chinese variants, so it is the preferred transcription service for Chinese/English source videos.
- Google Cloud Translation supports Vietnamese as a target language.
- Google Cloud Text-to-Speech `text:synthesize` remains the Vietnamese voice/dub generation provider.
- Google Cloud Video Intelligence speech transcription is English-only for that feature, so it is not the primary transcription path for this Chinese/English localization MVP.
- FFmpeg is the media processing boundary for extraction, subtitle packaging or burn-in, audio track handling, and final MP4 rendering.

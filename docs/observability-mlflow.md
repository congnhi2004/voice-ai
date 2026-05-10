# Observability And MLflow

## Goals

- Trace every synthesis request from API request to audio artifact.
- Monitor latency, failures, provider health, and usage.
- Use MLflow Tracking for product and model/provider lifecycle evidence.
- Keep privacy-safe telemetry by default.

## Structured Logs

Each request log should include:

- `timestamp`
- `level`
- `request_id`
- `job_id`
- `route`
- `method`
- `status_code`
- `provider`
- `voice_name`
- `language_code`
- `audio_encoding`
- `input_type`
- `input_chars`
- `latency_ms`
- `error_code`

Do not log raw text unless a secure debug mode is explicitly enabled outside production.

## Runtime Metrics

Minimum service metrics:

- Request count by route/status.
- Synthesis count by provider/status.
- Latency histogram for API and provider calls.
- Character count by key/tenant.
- Audio bytes generated.
- Provider error count and quota/rate-limit count.
- MLflow logging success/failure count.

## MLflow Tracking Design

Create one MLflow run per synthesis request or per batch item if batching is added later.

Suggested experiment:

- `voice-ai-tts-synthesis`

Run tags:

- `job_id`
- `request_id`
- `tenant_id`
- `provider`
- `environment`
- `service_version`
- `fallback`

Run params:

- `voice_name`
- `language_code`
- `audio_encoding`
- `speaking_rate`
- `pitch`
- `sample_rate_hz`
- `input_type`
- `input_chars`

Run metrics:

- `latency_ms`
- `provider_latency_ms`
- `duration_ms`
- `audio_bytes`
- `input_chars`
- `success`

Artifacts:

- Local/staging: generated audio artifact when privacy policy allows.
- Production: artifact reference JSON containing storage URI, checksum, and retention class.

MLflow docs support programmatic tracking, querying runs, logging metrics, and searching by metrics/params. This is enough for the MVP to compare provider settings, quality reviews, latency, and failure rates.

## Health And Alerts

Readiness should check:

- Active provider configuration.
- Audio storage writability or object storage access.
- MLflow tracking URI configured and optionally reachable.

Recommended alerts:

- Error rate over 5% for 5 minutes.
- P95 latency above target for 10 minutes.
- Google provider auth failures.
- Google quota/rate-limit errors.
- MLflow logging failures above threshold.
- Audio storage write failures.

## Dashboards

Minimum dashboard panels:

- Requests by route/status.
- Synthesis success/failure by provider.
- P50/P95/P99 latency.
- Character volume and generated audio bytes.
- Top provider errors.
- MLflow run count and logging failures.


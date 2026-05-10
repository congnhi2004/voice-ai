# Security And Privacy

## Security Goals

- Keep Google credentials server-side only.
- Prevent unauthorized synthesis and audio retrieval.
- Avoid logging sensitive user text by default.
- Make production secrets auditable and rotatable.
- Support future tenant isolation without rewriting the API contract.

## Authentication

MVP authentication uses API keys.

Required behavior:

- Clients send `Authorization: Bearer <api_key>` or `X-API-Key: <api_key>`.
- The service validates against configured keys or a secret-backed key registry.
- Invalid or missing credentials return structured `401`.
- Authorization failures return `403`.

Recommended future path:

- Tenant-scoped API keys with usage limits.
- Optional OAuth/OIDC for dashboard users.
- Service-to-service auth through Cloud Run IAM for internal deployments.

## Secrets

Secrets must not be committed.

Required environment variables:

- `GOOGLE_APPLICATION_CREDENTIALS`: local path to a service account JSON file for development only.
- `GCP_PROJECT_ID`: Google Cloud project id.
- `API_KEYS`: comma-separated keys or secret reference for MVP.
- `MLFLOW_TRACKING_URI`: MLflow tracking server or local file URI.
- `OPENAI_API_KEY`: user-provided OpenAI key only when a verified feature or test explicitly requires it.

Production should prefer Secret Manager and Cloud Run service identity over local credential files.

### User-Provided API Key Handling

Treat user-provided `OPENAI_API_KEY` values and all cloud/API keys as secrets. This applies to Google Cloud credentials, provider API keys, MLflow credentials, deploy tokens, CI/CD tokens, signed URL secrets, and temporary test keys.

Required handling:

- Never commit secret values.
- Never echo secret values in commands, terminal output, chat, docs, logs, reports, screenshots, or acceptance evidence.
- Never paste secret values into subagent prompts, subagent reports, product docs, completion summaries, or issue text.
- Never place real secret values in `.env.example`; examples must contain placeholders such as `[redacted]` or descriptive variable names only.
- Pass secrets only through environment variables for narrow test commands when no safer secret manager path is available.
- Redact secret-like values as `[redacted]` in docs, logs, reports, and evidence.
- Recommend rotating any key that appeared in chat, terminal output, logs, reports, screenshots, or docs after test use.
- Prefer managed secret stores for persistent environments. For GCP deployments, use Google Secret Manager or Cloud Run service identity where possible.
- Apply least privilege, key scoping, and environment separation. Do not reuse personal keys as project-wide staging or production credentials.

Allowed documentation pattern:

```bash
export OPENAI_API_KEY="[redacted]"
export GOOGLE_APPLICATION_CREDENTIALS="[redacted]"
```

Disallowed documentation pattern:

```bash
export OPENAI_API_KEY="<real key>"
```

## Privacy Controls

- Do not log raw input text by default.
- Log text length, input type, language, voice, encoding, request id, job id, tenant id, provider, status, and latency.
- If product needs raw text retention, require explicit tenant policy, retention limit, and access controls.
- Audio files can contain personal data and must be protected as customer content.

## Data Retention

MVP defaults:

- Local generated audio can be deleted manually.
- Production audio retention default: 30 days unless tenant contract requires otherwise.
- MLflow run metadata retention default: 180 days.
- Raw request bodies are not retained.

## CORS

- `CORS_ALLOW_ORIGINS` must be explicit in production.
- Wildcard origins are acceptable only for local development.
- Allow only required methods: `GET`, `POST`, `OPTIONS`.
- Allow only required headers: `Authorization`, `X-API-Key`, `Content-Type`, `X-Request-ID`, `Idempotency-Key`.

## Abuse Prevention

- Enforce max characters per request.
- Enforce per-key rate limits.
- Track character count and provider cost indicators.
- Add quotas before public launch.
- Reject unsupported encodings and invalid SSML.

## Security Acceptance

- No application source references plaintext production keys.
- API rejects unauthenticated synthesis.
- Logs do not contain raw text in normal mode.
- Logs, reports, docs, screenshots, and acceptance evidence contain no unredacted user-provided API keys or cloud/API keys.
- `.env.example` contains only variable names and placeholders, never real secret values.
- Any key that appeared in chat or another non-secret surface is rotated after test use.
- Generated audio URLs follow access policy.
- Google credential absence is detected by readiness and covered in tests.

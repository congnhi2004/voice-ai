# Backend Auth Billing Report - 2026-05-10

## Scope

Implemented a production-oriented backend auth and billing slice without committing live secrets. Local development still works without Stripe secrets, but production-like environments require explicit auth configuration and billing endpoints return clear not-configured errors until Stripe configuration is present.

## Files Changed

- `app/auth_billing.py`
- `app/config.py`
- `app/frontend_support.py`
- `app/main.py`
- `app/models.py`
- `tests/backend/test_api.py`
- `requirements.txt`
- `.env.example`
- `docs/subagents/backend-auth-billing-report-20260510.md`

## Official Sources Checked

- FastAPI OAuth2/JWT password hashing docs: `https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/`
- Stripe subscriptions with Checkout Sessions: `https://docs.stripe.com/payments/subscriptions`
- Stripe Checkout Session API reference: `https://docs.stripe.com/api/checkout/sessions/create`
- Stripe webhook signature verification: `https://docs.stripe.com/webhooks?lang=python`
- Stripe webhook signature troubleshooting/raw body guidance: `https://docs.stripe.com/webhooks/signature`
- Stripe Customer Portal Session API reference: `https://docs.stripe.com/api/customer_portal/sessions`

## Context7

- `/fastapi/fastapi`, topic: `OAuth2 JWT password hashing security dependencies request body headers TestClient`
- `/stripe/stripe-python`, topic: `Checkout Session subscription Billing Portal Session Webhook construct_event Python`
- `/jpadilla/pyjwt`, topic: `encode decode exp sub algorithms exceptions`
  - Retrieval was blocked by the Context7 tool because the returned docs contained a secret-like sample value. PyJWT usage was kept to standard `encode` and `decode` with `exp`, `sub`, `jti`, and configured algorithms.

## Implemented Endpoints

- `POST /v1/auth/register`
  - Creates a SQLite-backed user.
  - Hashes passwords with `pwdlib` recommended Argon2 hashing.
  - Returns a PyJWT bearer token with `sub`, `email`, `jti`, `iat`, and `exp`.

- `POST /v1/auth/login`
  - Verifies the password hash.
  - Returns a new JWT bearer token.

- `POST /v1/auth/logout`
  - Revokes the current token `jti` in SQLite so subsequent `/me` calls fail.

- `GET /v1/auth/me`
  - Validates JWT signature, expiry, user existence, and token revocation.

- `GET /v1/billing/subscription`
  - Returns local subscription state and computed entitlements.

- `POST /v1/billing/checkout-session`
  - Requires authenticated user.
  - Creates or reuses a Stripe customer.
  - Creates a Stripe Checkout Session with `mode=subscription`, configured Stripe price ID, success URL, cancel URL, metadata, and subscription metadata.
  - Returns `503 billing_not_configured` when Stripe env vars are absent.

- `POST /v1/billing/customer-portal`
  - Requires authenticated user and linked Stripe customer.
  - Creates a Stripe Customer Portal Session with configured return URL.
  - Returns explicit errors when Stripe is not configured or no customer exists.

- `POST /v1/billing/stripe-webhook`
  - Reads the raw request body with `await request.body()`.
  - Requires `Stripe-Signature`.
  - Verifies through Stripe webhook construction before provisioning.
  - Idempotently records Stripe event IDs.
  - Provisions subscription status for `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, and `customer.subscription.deleted`.

## Env Vars Added

- `AUTH_STORAGE_PATH`
- `AUTH_JWT_SECRET`
- `AUTH_JWT_ALGORITHM`
- `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_SUCCESS_URL`
- `STRIPE_CANCEL_URL`
- `STRIPE_PORTAL_RETURN_URL`
- `STRIPE_PRICE_STARTER`
- `STRIPE_PRICE_PRO`

Production-like `ENVIRONMENT` values (`production`, `prod`, `staging`, `public`) require `AUTH_JWT_SECRET`; local development uses a development-only JWT secret if none is configured.

## Tests

- `taskset -c 0-3 python3 -m pytest tests/backend/test_api.py -q`
  - Result: `30 passed, 3 skipped, 2 warnings`

- `taskset -c 0-3 python3 -m pytest tests/backend -q`
  - Result: `30 passed, 3 skipped, 2 warnings`

Tests mock Stripe and do not make live Stripe calls. Coverage includes password non-persistence, JWT login/me/logout, production auth not-configured behavior, Stripe billing not-configured behavior, mocked Checkout and Portal sessions, and webhook signature path/provisioning.

## Remaining Production Requirements

- Replace local SQLite auth/billing state with a managed durable database before commercial production.
- Set real secrets through Secret Manager or equivalent runtime secret injection:
  - `AUTH_JWT_SECRET`
  - `STRIPE_SECRET_KEY`
  - `STRIPE_WEBHOOK_SECRET`
- Configure real Stripe Products/Prices and set `STRIPE_PRICE_STARTER` and `STRIPE_PRICE_PRO`.
- Configure Stripe webhook endpoint URL to `POST /v1/billing/stripe-webhook`.
- Configure real app URLs for checkout success, cancellation, and customer portal return.
- Add account/email verification, password reset, rate limiting, audit logs, and admin/customer support flows before full commercial launch.

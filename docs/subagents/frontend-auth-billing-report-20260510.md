# Frontend Auth Billing Report - 2026-05-10

## Role

Frontend Auth Billing Agent.

## Changed files

- `frontend/src/api.ts`
- `frontend/src/main.ts`
- `frontend/src/styles.css`
- `frontend/src/e2e/app.spec.ts`
- `docs/subagents/frontend-auth-billing-report-20260510.md`

## UX flows and states

- Preserved the TTS studio as the first working screen and left the video localization tab/workflow intact.
- Added frontend API shapes for product capabilities, pricing plans, register/login/me/logout, subscription status, Stripe Checkout session, and billing portal session.
- Added session-aware account UI in the right rail:
  - signed-out state with login/sign-up actions;
  - signed-in state with email, identity mode, plan, subscription, entitlement summary, refresh, billing portal, and logout;
  - clear disabled state when billing capabilities report unavailable.
- Upgraded pricing to render backend-provided plans from `/v1/product/plans`.
- Added plan-selection buttons that call Checkout only when capabilities report production billing or checkout/Stripe availability.
- Added form validation for auth email/password with inline `role="alert"` errors, no browser-only validation dependency.
- Added clear not-configured states for billing:
  - `pricing-copy-only` shows plan copy but disables purchase;
  - portal and Checkout buttons are disabled or return direct error text;
  - subscription status degrades to "not available yet" if endpoint is missing.

## Backend assumptions

- Current capability endpoint: `GET /v1/product/capabilities`.
- Current plan endpoint: `GET /v1/product/plans`.
- Auth endpoints assumed from backend support report: `POST /v1/auth/register`, `POST /v1/auth/login`, `GET /v1/auth/me`, `POST /v1/auth/logout`.
- Future billing endpoints assumed for frontend readiness:
  - `GET /v1/billing/subscription`
  - `POST /v1/billing/checkout`
  - `POST /v1/billing/portal`
- Checkout response may return `url` or `checkout_url`.
- Portal response may return `url` or `portal_url`.
- Session token may be returned as `access_token`, `token`, or `session_token`.
- Current evidence says auth is `local-demo` and billing is unavailable/pricing-copy-only, so production purchase UX remains disabled until Backend Auth Billing Agent exposes Stripe-backed capabilities.

## Context7 and current sources

- Context7 `/vitejs/vite/v7.0.0`, topic: `env variables build TypeScript vanilla app`.
- Context7 `/microsoft/typescript/v5.8.3`, topic: `strict DOM fetch type narrowing discriminated unions`.
- Context7 `/microsoft/playwright`, topic: `test locators screenshots web first assertions route mocking`.
- Stripe official docs checked:
  - `https://docs.stripe.com/api/checkout/sessions/create`
  - `https://docs.stripe.com/customer-management`
  - `https://docs.stripe.com/customer-management/integrate-customer-portal`
- Accessibility sources checked:
  - `https://www.w3.org/WAI/tutorials/forms/`
  - `https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html`

## Verification

- `npm run lint` - pass.
- `npm run test` - pass, `src/__tests__/api.test.ts` 4 tests.
- `npm run build` - pass, Vite production build completed.
- `npm run test:e2e` - blocked before app execution because Playwright Chromium cannot load `libgbm.so.1`.
- Dependency workaround attempted:
  - `npx playwright install-deps chromium` failed because sudo requires an interactive password.
  - direct `apt-get install -y libgbm1` failed because current user cannot lock apt directories.

## Screenshots

- No new screenshots captured in this run because Chromium could not launch due missing `libgbm.so.1`.
- Existing e2e screenshot paths remain in the test file for TTS/video once browser dependencies are available.

## Remaining blockers

- Install Playwright browser system dependency `libgbm1` or run e2e in an image that includes Chromium dependencies.
- Backend must expose production auth and Stripe-backed billing capabilities before Checkout and portal buttons become enabled in production.
- Backend must define the final subscription/entitlement payload shape; frontend currently accepts flexible fields and displays conservative fallbacks.

## Ghi chú deploy bổ sung - 2026-05-10

- `vite preview` ở public URL phục vụ `frontend/dist`, không phục vụ trực tiếp `frontend/src`. Sau khi sửa `frontend/src/main.ts` hoặc `frontend/src/styles.css`, chạy lại lint/build/E2E rồi restart tmux session `voice-ai-frontend` hoặc chạy `scripts/local-services.sh restart`.
- Xác minh `http://103.27.237.252:4174/` bằng asset hash mới, screenshot Playwright, console không lỗi, và không có panel chồng lấn.
- Bài học CSS: tránh class grid tái sử dụng quá rộng làm override layout container. Lỗi chồng lấn đến từ `workspace-grid` đi cùng `workflow-lanes`; cần override cụ thể `.workspace-grid.workflow-lanes`.

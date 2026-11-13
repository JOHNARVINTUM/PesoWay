# PesoWay

PesoWay is a local-only payment-gateway prototype built with Django and Django REST Framework. It will simulate payment flows only; it does not connect to banks, wallets, cards, or real customer funds.

## Phase 1 foundation

The initial architecture is a modular Django monolith:

- `accounts`: authentication and role-ready custom user model.
- `merchants`: merchant ownership, registered applications, and scoped API keys.
- `security`: API-key authentication and reusable scope permission.
- `payments`, `transactions`, `webhooks`, `dashboard`: implemented modules; `simulator` remains the future controlled payment-method boundary.
- `config`: environment-driven project configuration and OpenAPI endpoints.

## Phase 2 payment engine

The following simulated-only endpoints are available under `/api/v1/`:

- `POST /payment-intents/` creates a PHP payment intent. It requires `payments:write` and an `Idempotency-Key` header.
- `GET /payment-intents/{id}/` retrieves a merchant-owned intent and requires `payments:read`.
- `POST /payment-intents/{id}/cancel/` cancels a nonterminal intent and requires `payments:write`.

Responses use `{ "data": ... }`; errors use `{ "error": { "code", "message", "details"? } }`. Send API credentials as `Authorization: Bearer pw_...`. Amounts are integer centavos only; statuses are server-controlled. The engine does not provide a route to mark an intent successful.

`PaymentIntent` belongs to both a `Merchant` and its issuing `Application`, uses a non-sequential UUID public ID, has a merchant-unique reference, and is protected by amount/currency database constraints. `PaymentAttempt` is present as the future simulator boundary and cannot alter intents yet. `IdempotencyRecord` is unique per merchant, operation, and client key and stores a request fingerprint plus its completed response.

## Simulator and merchant operations

The controlled simulator creates attempts at `POST /api/v1/payment-intents/{id}/attempts/` (`payments:write`) and completes them at `POST /api/v1/simulator/payment-attempts/{reference}/complete/` (`simulator:write`). It accepts only the named test scenarios `succeeded`, `failed`, and `canceled`, is always labeled as simulation, and never accepts arbitrary payment status input.

PesoWay provides its own hosted simulation checkout at `/checkout/{payment-intent-id}/` when `PESOWAY_SIMULATOR_ENABLED=true`. It presents simulated Card, GCash, Maya, and QR Ph choices, then displays a separate test-authorization page before a server-controlled outcome. It never collects real card, wallet, PIN, or OTP data. The simulator is enabled by default only in local debug mode; a deployed test environment must opt in explicitly while keeping `DJANGO_DEBUG=false`.

Set `return_url` when creating an intent to return a customer to the merchant application after checkout. PesoWay appends `payment_intent=<uuid>` and `status=succeeded`; local HTTP URLs are permitted only in debug mode, while deployed flows require HTTPS.

Session login/logout is available at `/api/v1/auth/login/` and `/api/v1/auth/logout/`; login is limited to five requests per fifteen minutes per username. Merchant owners can create and revoke API keys through `/api/v1/merchant/api-keys/`; raw API key secrets are returned only when created.

## Security baseline

- API keys contain a public prefix plus random secret. Only a SHA-256 hash is stored; the raw value is available to the creator once.
- A key becomes unusable when it, its application, or its merchant is inactive.
- Authentication uses the `Authorization: Bearer <key>` header and returns a merchant-bound principal, so later API views can enforce resource ownership.
- Django password validators, secure/HTTP-only cookies, CSRF protection, clickjacking protection, content-type protection, a restrictive referrer policy, and environment-backed secrets are configured.
- PostgreSQL is the normal development database. SQLite is restricted to explicitly opted-in local exploration and automated tests.
- Fixed-window rate-limit counters are stored and incremented atomically in the database. Security-sensitive actions write non-secret audit records.
- Every payment lookup filters by the authenticated merchant. Cross-merchant IDs return a generic 404.

Remaining security work includes login lockout, simulator hardening, endpoint-specific abuse monitoring, and PostgreSQL production verification.

## Phase 3 webhooks

Webhook endpoints are registered at `POST /api/v1/webhook-endpoints/` with `webhooks:write`; their signing secret is shown only in that response and stored encrypted with `WEBHOOK_ENCRYPTION_KEY`. Subscribe to `payment_intent.created` and/or `payment_intent.canceled`. Events and delivery history are available to the owning merchant at `GET /api/v1/webhook-events/` with `webhooks:read`.

Use `python manage.py deliver_webhooks` from a local scheduler to process the PostgreSQL-backed outbox. Each POST carries `X-PesoWay-Event`, `X-PesoWay-Timestamp`, and `X-PesoWay-Signature: v1=<HMAC-SHA256>`; the signature covers `<timestamp>.<raw body>`. Receivers should validate the timestamp, signature, and event ID idempotently. Delivery attempts use exponential backoff and stop after five failures. Endpoints must be public HTTPS hosts; private, loopback, link-local, and redirect targets are rejected.

For Vercel deployments, `GET /internal/cron/deliver-webhooks/` invokes the same outbox service through a protected Cron route. It requires `CRON_SECRET` and is configured as a daily job for Vercel Hobby compatibility. See [`docs/vercel-webhook-delivery.md`](docs/vercel-webhook-delivery.md) for required environment variables, safe testing, and the important Hobby scheduling limitation.

After a successful controlled simulation, PesoWay also makes one bounded, best-effort delivery attempt for the new success event after its database transaction commits. This lets a normal single-endpoint integration update promptly; the outbox and protected Cron route remain the durable retry fallback if the receiver is unavailable.

## Phase 4 financial operations

`GET /api/v1/transactions/` returns merchant-scoped append-only ledger entries with `transactions:read`. `POST /api/v1/refunds/` requires `refunds:write` and creates a simulated refund only for a succeeded intent; it locks the intent, prevents over-refunds, and records a negative immutable ledger entry. The session-protected merchant monitoring view is available at `/dashboard/`.

## Phase 5 hardening

Operational data cleanup is dry-run by default: run `python manage.py cleanup_pesoway_data`, review counts, then explicitly run `python manage.py cleanup_pesoway_data --execute`. It retains rate-limit counters for two days, idempotency records for seven days, security audit logs for one year, and completed webhook delivery data for its documented retention window. See [`docs/integration-example.md`](docs/integration-example.md) for a server-side API and webhook-verification example.

## Local setup

1. Create and activate a virtual environment using Python 3.12+.
2. Install development dependencies: `pip install -r requirements-dev.txt`.
3. Copy `.env.example` to `.env`, then load those variables with your preferred local environment tool. Never commit `.env`.
4. Create a local PostgreSQL database and role matching `POSTGRES_*` values.
5. Run `python manage.py migrate` and `python manage.py check --deploy`.

### Neon remote PostgreSQL

Neon’s `neon init` writes an ignored `.env.local` containing `DATABASE_URL`. PesoWay reads it automatically for local development and requires TLS by default. Run `python manage.py migrate` after linking, but keep `.env.local`, connection strings, and Neon credentials out of Git and client-side code. Use the unpooled Neon URL for migrations or PostgreSQL locking/concurrency work if Neon provides both URLs.

For a temporary SQLite-only local run, set `USE_SQLITE=true`; do not use it for concurrency or financial workflow validation.

## API documentation

After the server is running, the OpenAPI schema and Swagger UI are available at `/api/schema/` and `/api/docs/`.

## Tests

Run `pytest`. Tests use isolated in-memory SQLite settings and cover API key handling, strict validation, merchant isolation, payment state transitions, idempotency, ledger/refund rules, webhook signing/retries, and safe cleanup. PostgreSQL-specific locking test coverage is included but skipped under SQLite; run it against a PostgreSQL test database with `DJANGO_SETTINGS_MODULE=config.settings` and correctly provisioned `POSTGRES_*` variables.

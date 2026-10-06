# Operations Runbook — Haus&Home V1

Audience: engineers deploying and operating the storefront. Pair this with the
[README](./README.md) for architecture and local dev.

## Environments

| Env      | Frontend              | API                      | Notes                     |
|----------|-----------------------|--------------------------|---------------------------|
| Dev      | localhost:3000        | localhost:8000           | `docker compose up`       |
| Staging  | staging.example.com   | api.staging.example.com  | auto-deploy on `main`     |
| Prod     | www.example.com       | api.example.com          | promoted from staging     |

Each environment is a separate database, Redis, secret set and payment-gateway
key set. Nothing is shared across environments.

## Secrets & configuration

All config is environment-driven (see `backend/.env.example` and
`frontend/.env.local.example`). **Secrets live in the platform's secret store /
GitHub Environments, never in the repo.**

Required in staging/prod:

- `SECRET_KEY` — long random string (`python -c "import secrets;print(secrets.token_urlsafe(48))"`)
- `DATABASE_URL` — managed Postgres connection string
- `REDIS_URL`
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` — from the Stripe dashboard
- `BACKEND_CORS_ORIGINS` — the exact storefront origin(s)
- `FRONTEND_URL`, `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_API_URL`, `API_URL_INTERNAL`
- `EMAIL_BACKEND=smtp` + SMTP credentials (or swap `services/email.py` for SES/SendGrid)
- `SENTRY_DSN` — enables error tracking
- `ENVIRONMENT=production` — disables the dev-only payment confirm endpoint

## Database migrations

Migrations are managed by Alembic. The API container runs `alembic upgrade head`
on start (`backend/scripts/start.sh`). Manually:

```bash
cd backend
alembic upgrade head        # apply
alembic downgrade -1        # roll back one
alembic revision --autogenerate -m "describe change"   # after model edits
```

`alembic check` reports drift between the models and the latest migration; it is
clean for the committed schema. **Do not seed production** (`SEED_ON_START`
should be unset/false outside dev/staging).

## Release process

1. Merge to `main`. CI runs backend lint+tests and frontend lint+typecheck+build.
2. On green `main`, the `deploy-staging` job runs — wire it to your target
   (build & push images, then deploy). Migrations run automatically on boot.
3. Smoke-test staging: load home, browse, add to cart, checkout with a Stripe
   test card, confirm the webhook marks the order paid and the email sends.
4. Promote the same images to production and run the same smoke test.

Rollback: redeploy the previous image tag. If a migration must be reverted,
`alembic downgrade` to the prior revision **before** rolling back app code that
depends on the new schema.

## Payment gateway / webhooks

- Configure the Stripe webhook endpoint to `POST {API}/api/v1/payments/webhook`
  for `payment_intent.succeeded`, `payment_intent.payment_failed`,
  `payment_intent.canceled`, using `STRIPE_WEBHOOK_SECRET`.
- The webhook is the **only** path that marks an order paid; it is idempotent.
- Locally, test with the Stripe CLI: `stripe listen --forward-to
  localhost:8000/api/v1/payments/webhook`.

## Monitoring & observability

- **Errors:** set `SENTRY_DSN` to capture API exceptions (`app/main.py`).
  Add the Sentry SDK to the frontend similarly for client errors.
- **Health checks:** `GET /api/v1/health` (liveness) and `/api/v1/health/db`
  (readiness — verifies DB connectivity). Point your platform's probes here.
- **Logs:** structured app logs on stdout; ship to your log aggregator.
- **Metrics to watch:** 5xx rate, p95 latency on `/catalog/products`, checkout
  success rate, webhook failures, DB connections, Redis availability.

## Backups & data

- Enable automated daily snapshots + PITR on the managed Postgres.
- Redis holds only cache — safe to flush; it rebuilds on demand.

## Known follow-ups (post-V1)

- Scheduled job to expire abandoned pending orders and release reserved stock.
- Move rate-limit counters to Redis for correct multi-instance limiting.
- S3/CDN image upload pipeline in the admin UI.
- Upgrade search from ILIKE to Postgres full-text search or Algolia.
- Stripe Payment Element on the confirmation screen for live card capture.

## Common incidents

| Symptom                        | First checks                                              |
|--------------------------------|-----------------------------------------------------------|
| Orders stuck `pending`         | Webhook delivery in Stripe dashboard; `STRIPE_WEBHOOK_SECRET`; `/payments/webhook` logs |
| 401s after a while             | Token expiry/refresh flow; `SECRET_KEY` consistent across instances |
| CORS errors in browser         | `BACKEND_CORS_ORIGINS` matches the storefront origin exactly |
| `/health/db` failing           | Postgres reachable; connection limits; migrations applied |
| Stock oversold                 | Confirm reservations in `inventory.reserved`; check for webhook double-processing |

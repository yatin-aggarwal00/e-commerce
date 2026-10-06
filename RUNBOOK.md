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
- `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` — from the Stripe dashboard
- `BACKEND_CORS_ORIGINS` — the exact storefront origin(s)
- `FRONTEND_URL`, `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_API_URL`, `API_URL_INTERNAL`
- `STORAGE_BACKEND=s3` + `S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY_ID`,
  `S3_SECRET_ACCESS_KEY`, and `S3_PUBLIC_BASE_URL` (your CDN origin).
  `S3_ENDPOINT_URL` is only needed for non-AWS stores (MinIO/R2/Spaces).
- `EMAIL_BACKEND=smtp` + SMTP credentials (or swap `services/email.py` for SES/SendGrid)
- `SENTRY_DSN` (API) and `NEXT_PUBLIC_SENTRY_DSN` (storefront) — enable error tracking
- `ENVIRONMENT=production` — disables the dev-only payment confirm endpoint and
  activates the startup config check (`Settings.validate_runtime`), which refuses
  to boot on a weak `SECRET_KEY`, `DEBUG=true`, missing Stripe/S3 config, or empty CORS.

### GitHub Actions variables (for the deploy jobs)

Set these as **repository/Environment variables** (not secrets) so the web image
builds with the right public URLs: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SITE_URL`.
Images are pushed to `ghcr.io/<owner>/<repo>/{api,web}`; GHCR auth uses the
built-in `GITHUB_TOKEN` (no extra secret needed).

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

1. Open a PR to `main`. CI runs on every PR: backend lint+tests (coverage gate
   80%), frontend lint+typecheck+build, security scans, Playwright E2E and
   Lighthouse (both against a throwaway `docker compose` stack).
2. Merge to `main`. On green `main`, `deploy-staging` builds and pushes the API
   and web images to GHCR (tags `staging` and the commit SHA) and runs the
   rollout step — wire that step to your host. Migrations run automatically on
   boot (`start.sh`).
3. Smoke-test staging: load home, browse, add to cart, checkout with a Stripe
   test card (e.g. `4242 4242 4242 4242`), confirm the webhook marks the order
   paid and the confirmation email sends.
4. Tag a release (`git tag vX.Y.Z && git push --tags`) — `deploy-production`
   builds/pushes `latest` + the tag and runs the production rollout. Or trigger
   it manually via **workflow_dispatch**.

Rollback: redeploy the previous image tag (GHCR keeps every SHA/tag). If a
migration must be reverted, `alembic downgrade` to the prior revision **before**
rolling back app code that depends on the new schema.

### Quality gates

- **Coverage:** backend fails under 80% (currently ~85%).
- **Security:** `bandit` (our code) is a hard gate; `pip-audit` and `npm audit`
  report third-party CVEs without blocking — triage via the Dependabot PRs.
- **Lighthouse:** SEO and accessibility must score ≥0.90 on home, listing and
  product pages; performance (≥0.85) is a warning because scores vary with CI
  runner load. Budgets live in `.lighthouserc.json`.

## Payment gateway / webhooks

- Configure the Stripe webhook endpoint to `POST {API}/api/v1/payments/webhook`
  for `payment_intent.succeeded`, `payment_intent.payment_failed`,
  `payment_intent.canceled`, using `STRIPE_WEBHOOK_SECRET`.
- The webhook is the **only** path that marks an order paid; it is idempotent.
- Locally, test with the Stripe CLI: `stripe listen --forward-to
  localhost:8000/api/v1/payments/webhook`.

## Product images / object storage

- Admins upload images via `POST /api/v1/admin/uploads`; the response URL is
  attached to a product. The backend is pluggable (`app/services/storage.py`):
  - `STORAGE_BACKEND=local` (dev) writes under `MEDIA_ROOT` and serves at
    `/media`. Ephemeral — not for multi-instance production.
  - `STORAGE_BACKEND=s3` (staging/prod) uploads to any S3-compatible bucket and
    returns `S3_PUBLIC_BASE_URL/<key>` — point that at your CDN.
- Add your bucket/CDN host to `frontend/next.config.mjs` `images.remotePatterns`
  so `next/image` will optimise them (`**.amazonaws.com` is already allowed).

## Monitoring & observability

- **Errors:** set `SENTRY_DSN` (API, `app/main.py`) and `NEXT_PUBLIC_SENTRY_DSN`
  (storefront, `components/SentryInit.tsx`). Both are no-ops when unset.
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
- Upgrade search from ILIKE to Postgres full-text search or Algolia.
- Enable Sentry source-map upload (wrap `next.config` with `withSentryConfig`
  and set `SENTRY_AUTH_TOKEN`) for readable frontend stack traces.

## Common incidents

| Symptom                        | First checks                                              |
|--------------------------------|-----------------------------------------------------------|
| Orders stuck `pending`         | Webhook delivery in Stripe dashboard; `STRIPE_WEBHOOK_SECRET`; `/payments/webhook` logs |
| 401s after a while             | Token expiry/refresh flow; `SECRET_KEY` consistent across instances |
| CORS errors in browser         | `BACKEND_CORS_ORIGINS` matches the storefront origin exactly |
| `/health/db` failing           | Postgres reachable; connection limits; migrations applied |
| Stock oversold                 | Confirm reservations in `inventory.reserved`; check for webhook double-processing |

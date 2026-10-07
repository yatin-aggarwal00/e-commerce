# Haus&Home — Household Furniture E-commerce (V1)

A full-stack MVP storefront: a **Next.js** (App Router, TypeScript, Tailwind)
frontend backed by a **FastAPI** (Python 3.11) REST API, PostgreSQL, Redis and a
pluggable payment gateway.

> This is the V1 (MVP) foundation for the "Furniture E-commerce V1" epic. It is
> fully runnable end-to-end. See [Status vs. the epic](#status-vs-the-epic) for
> exactly what is implemented, and the [runbook](./RUNBOOK.md) for deployment.

---

## Architecture

```
┌──────────────┐        HTTPS/JSON        ┌───────────────┐
│  Next.js     │  ───────────────────▶    │   FastAPI     │
│  storefront  │   (SSR + client fetch)   │   REST API    │
│  (port 3000) │  ◀───────────────────    │  (port 8000)  │
└──────────────┘                          └───────┬───────┘
                                                   │ SQLAlchemy / Alembic
                                   ┌───────────────┼───────────────┐
                                   ▼               ▼               ▼
                            ┌───────────┐   ┌───────────┐   ┌──────────────┐
                            │ Postgres  │   │   Redis   │   │  Payment     │
                            │ (catalog, │   │  (cache)  │   │  gateway     │
                            │  orders)  │   │           │   │  (Stripe/…)  │
                            └───────────┘   └───────────┘   └──────────────┘
```

- **SEO-critical pages** (home, category, product detail) are server-rendered
  with ISR (`revalidate`). `products/[slug]` emits `Product` JSON-LD.
- **Money** is stored as integer minor units (cents) everywhere — never floats.
- **Payments** are isolated behind a `PaymentProvider` interface. A built-in
  `fake` provider lets the whole purchase flow run with no external keys; set
  `STRIPE_SECRET_KEY` to switch to real Stripe sandbox.
- **No card data** touches our servers (hosted payment element), minimising PCI
  scope.

## Tech stack

| Layer     | Choice                                                             |
|-----------|-------------------------------------------------------------------|
| Frontend  | Next.js 14 (App Router), TypeScript, Tailwind CSS, next/image     |
| Backend   | FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic                     |
| Database  | PostgreSQL 16 (SQLite for the test suite)                         |
| Cache     | Redis 7                                                           |
| Auth      | JWT access + refresh tokens, bcrypt password hashing              |
| Payments  | Stripe (sandbox) via a pluggable provider; `fake` for local/CI    |
| Infra     | Docker + docker-compose, GitHub Actions CI                        |

## Repository layout

```
.
├── backend/              FastAPI service
│   ├── app/
│   │   ├── api/v1/routes/ auth, catalog, cart, orders, payments, admin, …
│   │   ├── core/          config, db, security, redis
│   │   ├── models/        SQLAlchemy ORM models
│   │   ├── schemas/        Pydantic request/response models
│   │   ├── services/       payments, email, cart, pricing
│   │   └── seed.py         demo data + admin user
│   ├── alembic/           migrations (0001_initial)
│   └── tests/             pytest suite (85% coverage)
├── frontend/             Next.js storefront + admin
│   └── src/{app,components,context,lib}
├── docker-compose.yml    db + redis + api + web
├── .lighthouserc.json    Lighthouse CI budgets for key pages
└── .github/
    ├── workflows/ci.yml   lint, test, security, E2E, Lighthouse, deploy
    └── dependabot.yml      weekly dependency update PRs
```

## Quick start (Docker — recommended)

```bash
docker compose up --build
```

This starts Postgres, Redis, the API (which runs migrations and seeds demo
data), and the storefront. Then open:

- Storefront: <http://localhost:3000>
- API docs (Swagger): <http://localhost:8000/docs>
- OpenAPI schema: <http://localhost:8000/api/v1/openapi.json>

**Demo admin login:** `admin@furniture.example` / `admin12345`

By default `PAYMENT_PROVIDER=stripe` but with no `STRIPE_SECRET_KEY` the API
falls back to the `fake` provider, so you can complete a checkout and confirm a
"sandbox payment" from the order confirmation screen.

## Local development (without Docker)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements-dev.txt
cp .env.example .env            # edit SECRET_KEY etc.
# Point DATABASE_URL at a local Postgres, then:
alembic upgrade head
python -m app.seed              # demo catalog + admin user
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev                     # http://localhost:3000
```

## Testing

```bash
# Backend — in-memory SQLite + fake payments, no services needed
cd backend && pytest --cov=app --cov-report=term-missing

# Frontend — type safety, lint, production build
cd frontend && npm run typecheck && npm run lint && npm run build

# Frontend E2E (needs API + web running and seeded)
cd frontend && npm run test
```

The backend suite is at **85% coverage** and covers auth, catalog
filter/sort/search, cart stock rules, the full checkout → webhook → paid flow
(including idempotency and failed-payment stock release), and admin.

## Key API endpoints

| Area      | Endpoints                                                                 |
|-----------|---------------------------------------------------------------------------|
| Auth      | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `GET /auth/me`     |
| Catalog   | `GET /catalog/products` (filter/sort/paginate), `/catalog/products/{slug}`, `/catalog/autocomplete`, `/catalog/facets` |
| Cart      | `GET/POST/PATCH/DELETE /cart…` (guest via `X-Cart-Token`, or authed)      |
| Checkout  | `POST /checkout`, `GET /orders`, `GET /orders/{number}`                   |
| Auth      | `POST /auth/password-reset/request`, `/auth/password-reset/confirm`       |
| Payments  | `GET /payments/config` (provider + publishable key), `POST /payments/webhook` (idempotent, source of truth for paid state) |
| Admin     | `/admin/products`, `/admin/variants/{id}/inventory`, `/admin/orders`, `POST /admin/orders/expire-pending` (sweep abandoned orders), `/admin/stats`, `POST /admin/uploads` (image upload) |

Full, always-current docs are generated at `/docs`.

## Payments & order integrity

- Checkout creates a **pending** order and **reserves** stock. The cart is
  emptied on order creation so the same cart cannot be checked out twice
  (no duplicate orders).
- An order becomes **paid** only via the gateway **webhook**. The handler is
  idempotent (unique `provider_payment_id` + a paid-state short-circuit), so
  replayed events never double-apply or double-decrement stock.
- A **failed** payment releases the reservation and never flips the order to a
  paid state.
- **Abandoned** pending orders are swept by a scheduled job: once a pending
  order is older than `ORDER_PENDING_TTL_MINUTES` (default 60) it is cancelled
  and its reservation released, reusing the same release path as failed
  payments. The job is idempotent and race-safe (per-order transaction with an
  in-lock status re-check), runs in-process via APScheduler (single-flighted
  across instances by a Redis lock), and can be triggered on demand via
  `POST /admin/orders/expire-pending`. See the [runbook](./RUNBOOK.md).

## Status vs. the epic

**Implemented & verified**

- Catalog with categories, filters (price/material/color/room), sort, pagination
- Product detail with variants, gallery, live stock, dimensions
- Search + autocomplete (Postgres-portable ILIKE; FTS is the upgrade path)
- Guest & authenticated carts, persistence, merge-on-login
- Register / login / refresh / profile / saved addresses / **password reset UI**
- **Stripe Payment Element** checkout → webhook-confirmed paid → confirmation
  email; falls back to the `fake` provider (no keys) for local/CI
- Idempotent payment webhook; no duplicate/paid-on-failure orders
- Admin: product CRUD, inventory, order status, dashboard stats, **image upload**
  (local or S3-compatible storage behind a CDN)
- SEO: metadata, sitemap, robots, `Product` structured data
- **Error tracking**: Sentry on both API and storefront (enabled via DSN)
- OpenAPI docs; backend tests at ~85% coverage
- Dockerised; CI runs lint, tests, **security scans (bandit/pip-audit/npm audit),
  Playwright E2E, Lighthouse budgets**, and builds/pushes images for staging &
  (tag-gated) production

**Deliberate V1 choices / follow-ups**

- Search uses ILIKE; swap to Postgres FTS / Algolia when volume grows.
- Rate limiting is in-process; move the counter to Redis for multi-instance.
- Lighthouse **performance** is a CI warning (runner-dependent); SEO and
  accessibility budgets (≥0.90) are hard gates. See `.lighthouserc.json`.
- The `deploy-*` jobs push images to GHCR; wire the final rollout step to your
  host (see the runbook).

## Deployment

See **[RUNBOOK.md](./RUNBOOK.md)** for environments, secrets, migrations,
monitoring and release steps.

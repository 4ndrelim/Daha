# Person A — Backend & infra

**Mission:** the system of record: database, REST API (everything except discovery and AI), auth, transactions, chat, notifications, reputation, seed data, Docker, CI, and later the deploy. Contract: `PLAN.md` §6–§7. Your paths: `PLAN.md` §4.

## 🧑 Human TODOs (A)
- [ ] Install the prerequisites (`README.md` → How we work). Confirm `docker run hello-world` works.
- [ ] Once `backend/.env` exists, replace `JWT_SECRET` with the output of `openssl rand -hex 32`.
- [ ] After P0-A merges, post Claude's "Phase 0 backend merged ✅" message. C is waiting for it.
- [ ] At every ✅ checkpoint: merge the PR and paste the message into the chat.
- [ ] Phase 3: create hosting. Recommended: a small Ubuntu VM such as a DigitalOcean droplet, which is free with GitHub Student Pack credit. Also create a free Cloudflare account for the quick-tunnel demo.

## P0-A — Repo + backend skeleton + contract in code (target ≤ 2 h)
B builds `web/` in parallel and C runs the HarnessRouter spike. Don't touch `web/`.
1. **Repo root:**
   - the docs from the plan package (already present)
   - a root `.gitignore`: `.env`, `.env.local`, `*.env` (but not `*.env.example`), `backend/uploads/`, `.venv/`, `__pycache__/`, `node_modules/`, `.next/`, `.DS_Store`
   - `Makefile` (`PLAN.md` §5.5)
   - `docker-compose.yml`: service `db` = `pgvector/pgvector:pg16`; user, password, and db all `daha`; port 5432; named volume; healthcheck
   - `infra/db/init.sql`, which creates the database `daha_test`
   - `docs/decisions.md` with the header `date | person | decision | why`
2. **`backend/` with uv** (Python 3.12):
   - runtime deps: fastapi, uvicorn[standard], sqlalchemy, psycopg[binary], alembic, pgvector, pydantic, pydantic-settings, pyjwt, bcrypt, python-multipart, pillow, pillow-heif, httpx, fastembed, numpy, dateparser, anthropic
   - dev deps: pytest, pytest-asyncio, respx, ruff
   - this includes C's deps
3. **`app/core/`:**
   - `config.py`: a `Settings` class covering every variable in `PLAN.md` §5.3, read from `backend/.env`
   - `db.py`: engine, `SessionLocal(expire_on_commit=False)`, `Base`
   - `security.py`: bcrypt (the `bcrypt` package directly, not passlib); JWT HS256 with `sub` = user id and a 30-day expiry
   - `geo.py`: `PLAN.md` §7.9
   - `storage.py`: signatures only for now
4. **Models** for every table in `PLAN.md` §6 (with the model names from §7.1), plus the initial Alembic migration: extensions, generated `search_tsv` columns, GIN, trigram, and HNSW indexes.
5. **Pydantic schemas** for every type in `PLAN.md` §7.2, split into modules: `users`, `communities`, `items`, `requests`, `transactions`, `messaging`, `discovery`, `scans`.
6. **`app/api/deps.py`** and **`app/main.py`**: CORS from `CORS_ORIGINS`, a static mount of `UPLOAD_DIR` at `/uploads`, and inclusion of **every** router, including `app.ai.router.router` and `app.discovery.router.router`.
7. **Routers for every endpoint in `PLAN.md` §7.3** (A's in `app/routers/*.py`; C's in `app/ai/router.py` and `app/discovery/router.py`), each with the exact path, method, and request and response models. They all return `HTTPException(501, "not implemented")` for now, except `/api/health`. Use no trailing slashes.
8. **Stubs with the exact signatures from `PLAN.md` §7.10:** `app/services/{viewer,visibility,serializers,items,notifications,points,transactions}.py` and `app/discovery/hooks.py` (no-ops; `on_request_created` sets `matching_status='done'`). Create empty `__init__.py` files in `app/discovery/` and `app/ai/` (C owns everything in them from now on).
9. **Minimal seed** (`app/seed/seed.py --reset`): campus, dorms, and places (`PLAN.md` §8).
10. **Checks:** `make db migrate seed`, then `make api`. `curl localhost:8000/api/health` returns `{"ok":true}`, and `/docs` lists every endpoint. Run `uv run ruff check .` and `uv run pytest -q` (one health test).

Checkpoint message: *"Phase 0 backend merged ✅ — `make db migrate seed api` works; every endpoint exists as a 501 stub. C: start C1 in backend/app/ai + backend/app/discovery."*

## A1 — Auth, users, communities, places, uploads, visibility
- **Signup:**
  - Lowercase the email and check its domain against `ALLOWED_EMAIL_DOMAINS`. Password ≥ 8 characters.
  - Create memberships in campus plus the dorm (if `dorm_id`). Store `ref_user_id` as `referred_by`.
  - Return a JWT.
- **Login.** **Demo endpoints** only when `DEMO_MODE`.
- **Me** (`GET`/`PATCH`; changing the dorm swaps the dorm membership) and **users** (public profile, their visible items, reviews).
- **Communities:**
  - list with filters `kind`, `q` (ILIKE), `mine`
  - get by id or slug
  - create a group: unique slug from the name; private groups get a 6-character `join_code`
  - join, leave, members
  - counts are visibility-aware
- **Places**, with `distance_min`.
- **Uploads:**
  - Accept jpeg, png, webp, and heic, ≤ 15 MB.
  - Process with Pillow plus `pillow_heif.register_heif_opener()`: apply `ImageOps.exif_transpose`, **drop all metadata**, convert to RGB, cap the long side at 1600 px, save as JPEG q85 to `uploads/<uuid>.jpg`.
  - Store sha256, width, and height.
  - Implement `save_image_bytes` and `read_upload_bytes` with the same pipeline.
- **Real implementations** of `viewer.py`, `visibility.py` (`PLAN.md` §7.4), `serializers.py` (batched loads of owners, dorms, audiences, and first images), and `points.py` (levels and badges, `PLAN.md` §7.8).
- **Tests** (`tests/core/`):
  - signup domain rule
  - login
  - the visibility matrix: campus / dorm / groups × owner / member / non-member, for items and requests
  - private group join code
  - upload strips EXIF (create a JPEG with EXIF in the test)

Checkpoint: *"A1 ✅ live: auth, me, users, communities, places, uploads. B: remove auth,users,communities,places,uploads from NEXT_PUBLIC_MOCK."*

## A2 — Items + full seed
- **`services/items.create_item`:**
  - Validation: `services` can't be `lend`; `groups` needs `group_ids` the owner belongs to; ≤ 6 images, all owned by the user.
  - Write audiences and images.
  - Award +2 points (daily cap: 10 items) and check badges.
  - Schedule `hooks.on_item_saved`.
- **Item endpoints:** create, get (pickup-note privacy, `can_borrow`, `active_transaction_id`), patch (owner only; status limited to available ↔ unavailable; visibility changes rewrite audiences; reschedule the hook), delete (sets `archived`), and `/me/items`.
- **Full seed** (`PLAN.md` §8). Transactions, messages, and reviews are inserted directly, keeping ledger and badges consistent. The hero accounts must look alive. Finish by calling `reindex_all()`.
- **Tests:** item permissions, validation errors, pickup-note privacy, and that the seed runs twice cleanly.

Checkpoint: *"A2 ✅ items live + seed (`make seed`). Demo logins: maya@demo.daha, jordan@demo.daha, sam@demo.daha / daha-demo. B: unmock items. C: real data for search & matching."*

## A3 — Requests, offers, transactions, chat, notifications, reviews, events
- **Requests:**
  - Create: audiences like items, `matching_status='pending'`, schedule `on_request_created`.
  - Get with offers: the requester sees all offers; others see only their own.
  - Patch: requester only; cancel or fulfil; edits schedule `on_request_updated`.
  - `/me/requests`. Compute `expired` (`PLAN.md` §7.4).
- **Offers:** the viewer must be able to see the request and must not be the requester. Exactly one of `item_id` (must be your own available item) or `new_item` (created through `create_item(source="offer")`). Creates an `offered` transaction.
- **Borrow:** creates a `requested` transaction. An optional `request_id` must be the viewer's own open request.
- **`services/transactions.py`:** implement `PLAN.md` §7.7 exactly, with a single `apply_action()` and `allowed_actions()`. All side effects live here: item and request status, auto-declines, timeline, system messages, notifications, points, badges.
- **Conversations:**
  - A transaction thread is created together with its transaction.
  - Direct threads are get-or-create per pair of users.
  - Messages support `after_id` polling.
  - Unread counts come from `last_read_message_id`. `Me.unread_messages` is the sum.
- **Notifications** endpoints and the real `notify()`. **Reviews:** completed transactions only, one per party; +2 for ≥ 4★; badge check. **Events:** bulk insert, always 204.
- **Tests:**
  - the full lend lifecycle and the full give lifecycle
  - every illegal action → 409
  - auto-decline (same item; fulfilled request)
  - pickup-note reveal on accept
  - points and badges
  - unread counts
  - a non-party can't read a transaction → 404

Checkpoint: *"A3 ✅ requests/offers/transactions/chat/notifications/reviews/events live. B: unmock requests,transactions,conversations,notifications,events."*

## A4 — End-to-end API smoke script
`backend/scripts/smoke_api.py` (httpx, `API_URL` default `http://localhost:8000`), run with `make smoke`. Steps:
1. Sign up two fresh users in different dorms (random emails `@stanford.edu`).
2. User 1 uploads a generated JPEG with EXIF data and checks it was stripped.
3. User 1 creates a campus item and a dorm-only item. User 2 sees the campus item and gets 404 for the dorm-only one.
4. User 2 creates a request; user 1 offers; user 2 accepts. Then hand_off and mark_returned.
5. Both review. Check points, badges, notifications, and unread counts.

Print ✅/❌ per step; exit non-zero on any failure.

## A5 — Infra
- **`backend/Dockerfile`:** uv sync with frozen deps, a non-root user, uvicorn on 8000.
- **`web/Dockerfile`:** multi-stage Next.js standalone build. A owns this one file inside `web/`.
- **`docker-compose.yml` profile `full`:** db + api + web, with volumes for `uploads` and the fastembed cache (`FASTEMBED_CACHE_PATH`). `make up`.
- **`.github/workflows/ci.yml`:**
  - backend: ruff + pytest against a Postgres service, with `AI_PROVIDER=mock` and `EMBEDDINGS_PROVIDER=hash`
  - web: `pnpm install --frozen-lockfile`, lint, typecheck, build
- Update `README.md` → "How it's set up" if commands changed.

Checkpoint: *"A4+A5 ✅ `make smoke` green, CI on every PR, `make up` runs the whole stack in Docker. Phase 1 done (A)."*

## Phase 2 & 3 (A)
- **Integration:** fix issues labeled `A` (`plans/INTEGRATION.md`).
- **Deploy:** `plans/INTEGRATION.md` §3.3.

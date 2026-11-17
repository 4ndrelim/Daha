# DAHA — technical plan (agents read this)

Read this together with `AGENTS.md` (rules), `CONTRIBUTING.md` (git), `ARCHITECTURE.md` (diagrams), and your sub-plan in `plans/`. **§6 and §7 are the contract**: implement them exactly.

## 1. Documents
| Doc | Use |
|---|---|
| `docs/PRODUCT_BRIEF.md` | The full product vision, refined from the original brief, mapped to MVP vs later |
| `plans/A-backend.md` | Person A milestones P0-A, A1–A5 |
| `plans/B-frontend.md` | Person B milestones P0-B, B1–B6, plus the design system and screen specs |
| `plans/C-ai-discovery.md` | Person C milestones C0–C4: HarnessRouter, scans, search, matching, feeds, scan UI |
| `plans/INTEGRATION.md` | Phase 2 (integration, driven by C) and Phase 3 (demo, feedback, deploy) |
| `plans/EVALS.md` | Phase 3 evals (C) |
| `plans/ROADMAP.md` | Phase 4: future ML, RL, and agent work |

## 2. MVP scope
**P0: must work in the demo**
1. Accounts: `@stanford.edu` email + password + dorm; one-tap demo login when `DEMO_MODE=true`; invite links that pre-select a dorm.
2. "Show us what you have" onboarding: multiple photos → AI detection → one review screen (select, edit, remove, add) → batch publish with shared defaults. Skippable. Target: first items shared in under 60 s.
3. Listings:
   - Fields: images, name, description, category, quantity, condition, availability dates, pickup spot plus a private pickup note, type (lend / give / exchange), optional max lend days.
   - Visibility: campus, dorm, or selected groups.
   - Status: available, reserved, borrowed, or unavailable.
   - Single manual listings are supported too.
4. Requests: casual text → instant editable parse → post with a visibility → matching items shown (same dorm first) → owners of matching items notified → offers, either from inventory or as a new, previously unlisted item.
5. Transactions: requested/offered → accepted → handed_off → completed, plus decline and cancel. Direct borrow from the item page.
6. Search: natural language (the 5 example queries in §10 must work), filters (category, community, walking distance, availability, type, condition), ranking by relevance + availability + proximity.
7. Home feed: scan prompt, "You could help", "Requests near you", "New near you".
8. Communities: campus + dorms (seeded) + groups (create, join, private join code); chat-like channel feed and inventory tab.
9. Messaging: per-transaction and direct threads, polling.
10. Notifications (in-app); points, levels, badges, reviews, transaction history.
11. Share links for requests (`/r/{id}`).
12. Privacy rules in `ARCHITECTURE.md` §8.
13. Logging for future ML: events, search logs, and scan detections with the user's edits.

**P1: stretch.** Claim an item in the group chat first. The list is ordered from most to least valuable.
1. Reverse matching: notify an item's owner about open requests the item matches (C).
2. "Autofill from photo" on the manual listing form (C backend, B UI).
3. Background AI enrichment of requests (C).
4. Rate-limited "someone in your dorm needs X" notifications (C).
5. PWA manifest (B).
6. Playwright end-to-end smoke test (B).
7. Opt-in dorm leaderboard (A + B).
8. Overdue reminders (A + B).
9. Group-owned inventory (A + B).
10. Thumbnails cropped from bounding boxes (C).

**Out of scope.** Payments or selling, SSO, push or email notifications, websockets, native apps, moderation tools, multi-campus.

## 3. Phases, milestones, checkpoints
| Phase | Person A | Person B | Person C |
|---|---|---|---|
| **0** (parallel) | **P0-A**: repo, backend skeleton, all DB models, schemas, 501 stubs | **P0-B**: web skeleton, `types.ts`, API client, app shell | **C0**: HarnessRouter spike (no repo needed) |
| **1** (parallel) | A1 auth/communities/uploads/visibility → A2 items + seed → A3 requests/transactions/chat/notifications → A4 smoke script → A5 Docker + CI | B1 mocks + auth + home → B2 explore → B3 add/listing/request/item → B4 request detail/chat/transactions → B5 communities/profile/notifications → B6 polish + go live | C1 AI layer + scan API → C4 scan UI → C2 embeddings + search → C3 parsing + matching + feeds |
| **2** (together) | fixes A issues | fixes B issues | **drives integration** (`plans/INTEGRATION.md`) |
| **3** (sequential) | deploy | polish from feedback | **evals** (`plans/EVALS.md`) |

**Checkpoints.** Paste each message in the group chat when it lands.
| Checkpoint | Unblocks |
|---|---|
| P0-A merged | C starts C1. B can run the real backend (`/api/health`) |
| A1 | B: `NEXT_PUBLIC_MOCK` drops `auth,users,communities,places,uploads` |
| A2 | B drops `items`. C gets real seed data for search and matching |
| C1 | C4 can run against the live scan API |
| C2 | B drops `search` |
| A3 | B drops `requests,transactions,conversations,notifications,events`. C can test match notifications end to end |
| C3 | B drops `feed,matches,ai` → `NEXT_PUBLIC_MOCK=none` |

## 4. Repo layout & ownership
```
daha/
├── README.md CONTRIBUTING.md ARCHITECTURE.md AGENTS.md CLAUDE.md PLAN.md plans/   everyone (edit via PR)
├── docs/decisions.md                                   everyone (append-only)
├── docs/ai-spike.md                                    C
├── docs/ux-references/                                 B
├── Makefile · docker-compose.yml · infra/ · .github/   A
├── backend/                                            A, except:
│   ├── app/discovery/**                                C  (router.py, hooks.py, embeddings.py, query_parser.py,
│   │                                                       search.py, matching.py, feeds.py, reindex.py, config.py)
│   ├── app/ai/**                                       C  (router.py, providers/, prompts.py, vision.py, scans.py,
│   │                                                       request_parser.py, schemas.py)
│   ├── scripts/hr_spike.py · scripts/setup_harnessrouter.py   C
│   ├── tests/ai/** · tests/discovery/**                C
│   └── (A also owns) pyproject.toml, alembic/, app/{main.py,core,models,schemas,api,routers,services,seed},
│                     scripts/smoke_api.py, tests/core/**, .env.example, Dockerfile
├── web/                                                B, except:
│   ├── src/app/onboarding/** · src/app/(app)/add/scan/**      C
│   ├── src/components/scan/**                          C
│   ├── src/lib/api/endpoints/scans.ts · src/lib/api/mock/scans.ts · src/lib/queries/scans.ts   C
│   └── Dockerfile                                      A
└── evals/                                              C
```
Rules:
- In Phase 0, A creates C's backend files as stubs (§7.10) and B creates C's web pages as placeholders. From then on C owns them.
- Anyone may **add** a new shadcn primitive under `web/src/components/ui/`, but never edit an existing one (B owns those).
- A puts every backend dependency C needs into `pyproject.toml` during Phase 0, so C rarely has to edit it.

## 5. Local setup & conventions

### 5.1 Prerequisites
Git, GitHub CLI, Docker Desktop, Node.js ≥ 20 with pnpm (`corepack enable`), Python 3.12, uv, Claude Code. Windows users work inside WSL2.

### 5.2 First run
```bash
gh repo clone 4ndrelim/Daha && cd Daha
cp backend/.env.example backend/.env
cp web/.env.example web/.env.local
make db         # Postgres+pgvector in Docker
make migrate    # create tables
make seed       # demo data
make api        # terminal 1 → http://localhost:8000/docs
make web        # terminal 2 → http://localhost:3000
```
Phone on the same Wi-Fi: open `http://<laptop-ip>:3000`. `make lan` prints the IP. The photo picker uses `<input type="file" capture>`, which works over plain HTTP.

### 5.3 `backend/.env.example` (A creates it in P0-A, including C's variables)
```bash
# --- core (A) ---
DATABASE_URL=postgresql+psycopg://daha:daha@localhost:5432/daha
TEST_DATABASE_URL=postgresql+psycopg://daha:daha@localhost:5432/daha_test
JWT_SECRET=change-me                 # human: replace with output of `openssl rand -hex 32`
ALLOWED_EMAIL_DOMAINS=stanford.edu
DEMO_MODE=true
PUBLIC_BASE_URL=http://localhost:3000
UPLOAD_DIR=./uploads
CAMPUS_TZ=America/Los_Angeles
CORS_ORIGINS=http://localhost:3000
# --- AI & discovery (C) ---
AI_PROVIDER=mock                     # mock | harnessrouter | anthropic
AI_MOCK_LATENCY_MS=2500
AI_MAX_IMAGES_PER_SCAN=6
AI_DAILY_SCANS_PER_USER=20
AI_BUDGET_USD=40                     # hard stop for paid vision calls (keeps $10 of $50 for evals)
HARNESSROUTER_API_KEY=               # human (C): from app.harnessrouter.ai — never commit
HARNESSROUTER_BASE_URL=https://api.harnessrouter.ai
HARNESSROUTER_VISION_HARNESS_ID=     # printed by scripts/setup_harnessrouter.py
HARNESSROUTER_BASE=claude-code       # harness base chosen in the C0 spike
HARNESSROUTER_MODEL=                 # model id chosen in the C0 spike (from GET /v1/models)
HARNESSROUTER_MAX_CONCURRENCY=2
HARNESSROUTER_TIMEOUT_S=180
HARNESSROUTER_EST_COST_PER_IMAGE=0.10   # from the spike; used when the API reports no cost
ANTHROPIC_API_KEY=                   # optional fallback provider
ANTHROPIC_MODEL=claude-opus-5-5
ANTHROPIC_EFFORT=medium
EMBEDDINGS_PROVIDER=fastembed        # fastembed | hash (tests/CI)
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
MATCH_MIN_SCORE=0.55                 # calibrated by C on seed data
AI_ENRICH_REQUESTS=false
```

### 5.4 `web/.env.example` (B creates it in P0-B)
```bash
API_PROXY_TARGET=http://localhost:8000
NEXT_PUBLIC_MOCK=all    # all | none | comma list of mocked domains:
                        # auth,users,communities,places,uploads,items,requests,transactions,
                        # conversations,notifications,events,search,feed,matches,ai,scans
NEXT_PUBLIC_DEMO_MODE=true
```

### 5.5 Makefile targets (A)
`db` (start Postgres) · `migrate` · `seed` (`--reset`, deterministic) · `api` (uvicorn `--reload --host 0.0.0.0 --port 8000`) · `web` (`pnpm dev --hostname 0.0.0.0`) · `test` (backend pytest + ruff, web lint + typecheck) · `smoke` (A4) · `reindex` (C) · `lan` (print the LAN IP) · `up` (A5: full stack in Docker).

### 5.6 Conventions (both sides)
- JSON is **snake_case** both ways. TypeScript types use the same snake_case names, with no case conversion.
- `ISODateTime` = UTC ISO-8601 with `Z`. `ISODate` = `YYYY-MM-DD` in campus local time (`CAMPUS_TZ`).
- IDs are integers. Routes have **no trailing slashes**, and the web client never adds one.
- Responses always contain every field: optional values are `null`, never missing. In request bodies, optional fields may be omitted.
- Pagination: `offset` (default 0) and `limit` (default 20, max 50) → `Page<T> = {items, next_offset}`.
- Errors are FastAPI's `{"detail": "<message>"}` with these codes:
  - 400 bad input · 401 not logged in · 403 not allowed · 409 state conflict · 422 validation · 429 limit
  - 404 not found **or not visible**
- Auth: `Authorization: Bearer <token>`. The web app stores the token in `localStorage["daha_token"]`.
- Enums are stored as strings (`VARCHAR`), not native Postgres enums, and validated by Pydantic `Literal`s.
- Backend: thin routers; logic in services; type hints everywhere; `ruff` for format and lint. Frontend: TypeScript strict, no `any`, React Query for all server state.

## 6. Data model (A implements in P0-A; C reads and writes only the columns marked C)

Unless a table says otherwise:
- Every table has `id SERIAL PK` and `created_at TIMESTAMPTZ DEFAULT now()`.
- Enum columns are `VARCHAR(20)` validated in code.
- `seed_key TEXT UNIQUE NULL` exists on users, communities, items, and requests, so evals can reference seeded rows.

| Table | Columns | Notes |
|---|---|---|
| `users` | `email` (unique, lowercase), `password_hash`, `name`, `avatar_url` null, `bio` null, `walking_radius_min` int default 10, `onboarded` bool default false, `is_demo` bool default false, `referred_by` FK users null | Never store room numbers or addresses |
| `communities` | `kind` (campus\|dorm\|group), `slug` unique, `name`, `description` null, `emoji` null, `group_type` (club\|class\|research\|team\|org\|other) null, `is_private` bool default false, `join_code` null, `lat` null, `lng` null, `created_by` FK users null | Exactly one row with `kind='campus'` (slug `campus`). Dorms carry coordinates |
| `memberships` | PK(`user_id`, `community_id`), `role` (member\|admin) default member | Every user: campus + ≤ 1 dorm (enforced in the service) + groups |
| `places` | `name`, `lat`, `lng`, `description` null | Campus exchange points |
| `uploads` | `owner_id` FK, `path`, `url`, `width`, `height`, `sha256` | JPEG, metadata stripped |
| `items` | `owner_id` FK, `name`, `description` null, `category`, `quantity` int default 1, `condition` null, `transaction_type` (lend\|give\|exchange), `max_lend_days` null, `available_from` date null, `available_until` date null, `visibility` (campus\|dorm\|groups), `status` (available\|reserved\|borrowed\|unavailable) default available, `archived` bool default false, `pickup_place_id` FK places null, `pickup_note` null, `source` (manual\|scan\|offer), `scan_detection_id` FK null, **C:** `embedding VECTOR(384)` null, `search_tsv TSVECTOR GENERATED` (name weight A, description weight B), `updated_at` | GIN on `search_tsv`, trigram GIN on `name`, HNSW (`vector_cosine_ops`) on `embedding`, index on (`owner_id`), (`status`) where not archived |
| `item_images` | `item_id` FK, `upload_id` FK, `position` int | First image = thumbnail |
| `item_audiences` | PK(`item_id`, `community_id`) | Index on `community_id` |
| `requests` | `requester_id` FK, `raw_text`, `title`, `item_name` null, `category` null, `attributes` JSONB default `{}`, `quantity` default 1, `needed_from` date null, `needed_until` date null, `duration_days` null, `transaction_type` null, `visibility`, `status` (open\|in_progress\|fulfilled\|cancelled) default open, `pickup_place_id` null, **C:** `matching_status` (pending\|done) default pending, `ai_enriched` bool default false, `embedding VECTOR(384)` null, `search_tsv GENERATED` (title, item_name, raw_text), `updated_at`, `fulfilled_at` null | `expired` is computed, not stored (see §7.7) |
| `request_audiences` | PK(`request_id`, `community_id`) | |
| `request_matches` (C) | PK(`request_id`, `item_id`), `score` float, `reason` text, `notified` bool default false | Written by C's matching |
| `transactions` | `kind`, `status` (requested\|offered\|accepted\|handed_off\|completed\|declined\|cancelled), `item_id` FK, `request_id` FK null, `owner_id` FK, `borrower_id` FK, `initiated_by` (owner\|borrower), `message` null, `start_date` null, `due_date` null, `pickup_place_id` null, `pickup_note` null, `conversation_id` FK, `accepted_at`/`handed_off_at`/`completed_at`/`declined_at`/`cancelled_at` null, `updated_at` | Indexes on owner, borrower, item |
| `transaction_events` | `transaction_id` FK, `status`, `actor_id` null, `note` null | Timeline |
| `conversations` | `kind` (direct\|transaction), `transaction_id` FK unique null, `last_message_at` null | Direct = one per user pair |
| `conversation_participants` | PK(`conversation_id`, `user_id`), `last_read_message_id` null | Unread = messages with id > `last_read_message_id` from others |
| `messages` | `conversation_id` FK, `sender_id` FK null, `kind` (text\|system), `body` | Index (`conversation_id`, `id`) |
| `reviews` | `transaction_id` FK, `reviewer_id`, `reviewee_id`, `rating` smallint 1–5, `body` null; UNIQUE(`transaction_id`, `reviewer_id`) | |
| `points_ledger` | `user_id`, `delta` int, `reason`, `ref_type` null, `ref_id` null | Points = SUM(delta) |
| `user_badges` | PK(`user_id`, `code`), `earned_at` | |
| `notifications` | `user_id`, `type`, `title`, `body`, `link`, `actor_id` null, `data` JSONB default `{}`, `read_at` null | Index (`user_id`, `read_at`) |
| `scans` (C) | `user_id`, `status` (processing\|done\|failed), `provider`, `model` null, `prompt_version`, `finished_at` null | |
| `scan_images` (C) | `scan_id`, `upload_id`, `position`, `status` (pending\|processing\|done\|failed), `error` null, `latency_ms` null, `cost_usd` null, `raw_response` JSONB null | |
| `scan_detections` (C) | `scan_id`, `scan_image_id`, `image_index`, `name`, `category`, `description`, `quantity`, `condition_guess` null, `confidence` float, `bbox` JSONB null, `suggested_share` bool, `sensitive_reason` null, `suggested_transaction_type`, `status` (pending\|published\|discarded), `published_item_id` null, `edits` JSONB null | `edits` = what the user changed. This is future training data |
| `search_logs` (C) | `user_id`, `raw_query`, `parsed` JSONB, `filters` JSONB, `result_item_ids` INT[], `latency_ms` | |
| `events` | `user_id` null, `type`, `payload` JSONB | Product analytics |
| `ai_cache` (C) | `key` TEXT PK, `value` JSONB | Key = sha256(image) + prompt version + provider + model |

Migration notes:
- `CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;`
- Import `pgvector.sqlalchemy.Vector` in the migration.
- Generated columns use `Computed(..., persisted=True)`.
- Docker init SQL also creates the database `daha_test`.

## 7. API contract (source of truth)

### 7.1 Rules
- B copies §7.2 **verbatim** into `web/src/lib/api/types.ts`. A writes matching Pydantic models in `backend/app/schemas/`, with identical field names and nullability.
- TypeScript → Python mapping:
  - `T | null` → `T | None`
  - `field?:` (request bodies only) → default `None`
  - `Record<string,string>` → `dict[str, str]`
  - `ISODate` → `date`; `ISODateTime` → `datetime` (UTC)
  - unions of string literals → `Literal[...]`
  - `FeedEntry` → a discriminated union on `kind`
- Naming:
  - SQLAlchemy models: `User`, `Community`, `Membership`, `Place`, `Upload`, `Item`, `ItemImage`, `ItemAudience`, `ItemRequest` (table `requests`; named this way to avoid clashing with FastAPI's `Request`), `RequestAudience`, `RequestMatch`, `Transaction`, `TransactionEvent`, `Conversation`, `ConversationParticipant`, `Message`, `Review`, `PointsLedger`, `UserBadge`, `Notification`, `Scan`, `ScanImage`, `ScanDetection`, `SearchLog`, `Event`, `AICache`.
  - Pydantic schemas: the same names as the TypeScript types, always referenced module-qualified (`from app import schemas` → `schemas.Community`).

### 7.2 Types
```ts
// ---------- primitives ----------
export type ID = number;
export type ISODateTime = string;  // UTC, e.g. "2026-11-16T21:58:00Z"
export type ISODate = string;      // "2026-11-25" (campus local date)
export interface Page<T> { items: T[]; next_offset: number | null }

// ---------- enums ----------
export type Category = "academic" | "tech" | "clothing" | "dorm" | "consumables" | "sports" | "moving" | "events" | "services" | "other";
export type Condition = "new" | "like_new" | "good" | "fair" | "worn";
export type TransactionType = "lend" | "give" | "exchange";   // UI labels: Lend · Free · Swap
export type Visibility = "campus" | "dorm" | "groups";
export type ItemStatus = "available" | "reserved" | "borrowed" | "unavailable";
export type RequestStatus = "open" | "in_progress" | "fulfilled" | "cancelled" | "expired";
export type TxStatus = "requested" | "offered" | "accepted" | "handed_off" | "completed" | "declined" | "cancelled";
export type TxAction = "accept" | "decline" | "cancel" | "hand_off" | "mark_returned";
export type CommunityKind = "campus" | "dorm" | "group";
export type GroupType = "club" | "class" | "research" | "team" | "org" | "other";
export type NotificationType = "match" | "offer" | "borrow_request" | "tx_update" | "review" | "badge" | "system";
export type ItemSource = "manual" | "scan" | "offer";
export type Domain = "auth" | "users" | "communities" | "places" | "uploads" | "items" | "requests" | "transactions"
  | "conversations" | "notifications" | "events" | "search" | "feed" | "matches" | "ai" | "scans";

// ---------- users & auth ----------
export interface UserRef { id: ID; name: string; avatar_url: string | null; dorm_name: string | null; level_name: string; rating_avg: number | null }
export interface Badge { code: string; name: string; emoji: string; description: string; earned_at: ISODateTime }
export interface Level { name: string; min_points: number; next_level_name: string | null; next_level_points: number | null }
export interface UserPublic extends UserRef {
  bio: string | null; points: number; level: Level; badges: Badge[];
  rating_count: number; completed_count: number; items_shared_count: number; joined_at: ISODateTime;
}
export interface Me extends UserPublic {
  email: string; dorm: CommunityRef | null; groups: CommunityRef[]; walking_radius_min: number;
  onboarded: boolean; unread_notifications: number; unread_messages: number;
}
export interface AuthResponse { token: string; user: Me }
export interface SignupBody { email: string; password: string; name: string; dorm_id?: ID | null; ref_user_id?: ID | null }
export interface LoginBody { email: string; password: string }
export interface DemoLoginBody { user_id: ID }
export interface MeUpdate { name?: string; bio?: string | null; avatar_upload_id?: ID | null; dorm_id?: ID; walking_radius_min?: number; onboarded?: boolean }

// ---------- communities & places ----------
export interface CommunityRef { id: ID; slug: string; name: string; kind: CommunityKind; emoji: string | null }
export interface Community extends CommunityRef {
  description: string | null; group_type: GroupType | null; is_private: boolean;
  member_count: number; item_count: number; open_request_count: number;
  is_member: boolean; my_role: "member" | "admin" | null;
  join_code: string | null;             // only shown to admins, else null
  lat: number | null; lng: number | null; distance_min: number | null;
}
export interface CommunityCreate { name: string; description?: string | null; group_type: GroupType; is_private: boolean; emoji?: string | null }
export interface JoinBody { join_code?: string | null }
export interface Place { id: ID; name: string; lat: number; lng: number; description: string | null; distance_min: number | null }

// ---------- uploads ----------
export interface Upload { id: ID; url: string; width: number; height: number }

// ---------- items ----------
export interface ItemImage { id: ID; url: string; width: number; height: number }
export interface ItemCard {
  id: ID; name: string; category: Category; transaction_type: TransactionType; status: ItemStatus;
  condition: Condition | null; quantity: number; thumbnail_url: string | null; owner: UserRef;
  visibility: Visibility; community_label: string;      // "Campus" | dorm name | first group name (+N)
  distance_min: number | null; same_dorm: boolean; created_at: ISODateTime;
  match_score: number | null;    // only in search/match/fulfillable responses, else null
  match_reason: string | null;   // e.g. "Same dorm · 2 min walk"
}
export interface ItemDetail extends ItemCard {
  description: string | null; images: ItemImage[]; max_lend_days: number | null;
  available_from: ISODate | null; available_until: ISODate | null;
  pickup_place: Place | null;
  pickup_note: string | null;    // only for the owner, or the counterparty of an accepted/handed_off transaction
  group_ids: ID[];               // owner only, else []
  is_mine: boolean; can_borrow: boolean; active_transaction_id: ID | null;
  source: ItemSource; updated_at: ISODateTime;
}
export interface ItemCreate {
  name: string; description?: string | null; category: Category; quantity?: number; condition?: Condition | null;
  transaction_type: TransactionType; max_lend_days?: number | null;
  available_from?: ISODate | null; available_until?: ISODate | null;
  visibility: Visibility; group_ids?: ID[]; pickup_place_id?: ID | null; pickup_note?: string | null;
  image_upload_ids?: ID[];       // ≤ 6, first = thumbnail
}
export type ItemUpdate = Partial<ItemCreate> & { status?: "available" | "unavailable" };
export interface BorrowBody { message?: string | null; start_date?: ISODate | null; due_date?: ISODate | null; request_id?: ID | null }

// ---------- requests ----------
export interface ParsedRequest {
  kind: "request" | "offer" | "other"; title: string; item_name: string | null; category: Category | null;
  attributes: Record<string, string>; quantity: number; needed_from: ISODate | null; needed_until: ISODate | null;
  duration_days: number | null; transaction_type: TransactionType | null; confidence: number;
}
export interface ParseRequestBody { text: string }
export interface RequestCard {
  id: ID; title: string; raw_text: string; category: Category | null; status: RequestStatus; requester: UserRef;
  needed_from: ISODate | null; needed_until: ISODate | null; visibility: Visibility; community_label: string;
  distance_min: number | null; same_dorm: boolean; offer_count: number; match_count: number; created_at: ISODateTime;
}
export interface RequestDetail extends RequestCard {
  item_name: string | null; attributes: Record<string, string>; quantity: number; duration_days: number | null;
  transaction_type: TransactionType | null; pickup_place: Place | null; group_ids: ID[]; is_mine: boolean;
  matching_status: "pending" | "done";
  offers: Transaction[];         // requester sees all; others see only their own
  share_url: string;             // `${PUBLIC_BASE_URL}/r/${id}`
}
export interface RequestCreate {
  raw_text: string; title: string; item_name?: string | null; category?: Category | null; attributes?: Record<string, string>;
  quantity?: number; needed_from?: ISODate | null; needed_until?: ISODate | null; duration_days?: number | null;
  transaction_type?: TransactionType | null; visibility: Visibility; group_ids?: ID[]; pickup_place_id?: ID | null;
}
export type RequestUpdate = Partial<RequestCreate> & { status?: "cancelled" | "fulfilled" };
export interface OfferCreate { item_id?: ID | null; new_item?: ItemCreate | null; message?: string | null }  // exactly one of item_id / new_item
export interface MatchesResponse { matching_status: "pending" | "done"; items: ItemCard[] }

// ---------- transactions & reviews ----------
export interface TxTimelineEntry { status: TxStatus; at: ISODateTime; by: UserRef | null; note: string | null }
export interface Transaction {
  id: ID; kind: TransactionType; status: TxStatus; item: ItemCard; request_id: ID | null;
  owner: UserRef; borrower: UserRef; initiated_by: "owner" | "borrower"; my_role: "owner" | "borrower";
  message: string | null; start_date: ISODate | null; due_date: ISODate | null; is_overdue: boolean;
  pickup_place: Place | null; pickup_note: string | null; conversation_id: ID;
  allowed_actions: TxAction[]; can_review: boolean; timeline: TxTimelineEntry[];
  created_at: ISODateTime; updated_at: ISODateTime;
}
export interface TxActionBody { action: TxAction; note?: string | null; due_date?: ISODate | null; pickup_place_id?: ID | null }
export interface ReviewCreate { rating: 1 | 2 | 3 | 4 | 5; body?: string | null }
export interface Review { id: ID; transaction_id: ID; reviewer: UserRef; reviewee_id: ID; rating: number; body: string | null; created_at: ISODateTime }

// ---------- messaging, notifications, events ----------
export interface Message { id: ID; conversation_id: ID; sender: UserRef | null; kind: "text" | "system"; body: string; created_at: ISODateTime }
export interface ConversationSummary {
  id: ID; other_user: UserRef;
  transaction: { id: ID; status: TxStatus; kind: TransactionType; item_name: string } | null;
  last_message: Message | null; unread_count: number; updated_at: ISODateTime;
}
export interface DirectConversationBody { user_id: ID }
export interface SendMessageBody { body: string }
export interface Notification { id: ID; type: NotificationType; title: string; body: string; link: string; actor: UserRef | null; read: boolean; created_at: ISODateTime }
export interface UnreadCounts { notifications: number; messages: number }
export interface MarkReadBody { ids?: ID[]; all?: boolean }
export interface EventIn { type: string; payload?: Record<string, unknown>; ts?: ISODateTime }
export interface EventsBody { events: EventIn[] }

// ---------- discovery (C) ----------
export interface ParsedQuery {
  text: string; category: Category | null; scope: "campus" | "dorm" | null; near_me: boolean;
  available_from: ISODate | null; available_until: ISODate | null; transaction_type: TransactionType | null;
  chips: string[];               // human-readable, e.g. ["Tech", "Near you", "This weekend"]
}
export interface SearchResponse { parsed: ParsedQuery; items: ItemCard[]; requests: RequestCard[]; communities: Community[]; next_offset: number | null }
export interface FulfillableRequest { request: RequestCard; my_matching_items: ItemCard[] }
export interface HomeFeed {
  dorm: CommunityRef | null; my_item_count: number; show_scan_cta: boolean;   // show_scan_cta = my_item_count < 3
  you_can_help: FulfillableRequest[];  // ≤ 5
  requests_nearby: RequestCard[];      // ≤ 10
  new_nearby: ItemCard[];              // ≤ 12
  stats: { dorm_items: number; campus_items: number; open_requests: number };
}
export type FeedEntry =
  | { kind: "request"; created_at: ISODateTime; request: RequestCard }
  | { kind: "item"; created_at: ISODateTime; item: ItemCard };

// ---------- scans (C) ----------
export interface ScanImage { upload_id: ID; url: string; status: "pending" | "processing" | "done" | "failed"; error: string | null }
export interface Detection {
  id: ID; image_index: number; name: string; category: Category; description: string; quantity: number;
  condition_guess: Condition | null; confidence: number;
  bbox: [number, number, number, number] | null;   // normalized x, y, w, h (0..1), approximate
  suggested_share: boolean; sensitive_reason: string | null; suggested_transaction_type: TransactionType;
  status: "pending" | "published" | "discarded";
}
export interface Scan { id: ID; status: "processing" | "done" | "failed"; images: ScanImage[]; detections: Detection[]; provider: string; created_at: ISODateTime }
export interface ScanCreate { upload_ids: ID[] }
export interface ScanPublishItem extends ItemCreate { detection_id: ID | null }  // empty image_upload_ids → server uses the source photo (cropped to bbox if available)
export interface ScanPublishBody { items: ScanPublishItem[] }
export interface ScanPublishResponse { items: ItemDetail[]; points_awarded: number }
```

### 7.3 Endpoints (all under `/api`; all need auth except `health`, `auth/*`)
| Owner | Method & path | Body / query | Response | Notes |
|---|---|---|---|---|
| A | `GET /health` | | `{ok: true}` | |
| A | `POST /auth/signup` | `SignupBody` | `AuthResponse` 201 | 400 if the email domain isn't in `ALLOWED_EMAIL_DOMAINS`; 409 if the email exists |
| A | `POST /auth/login` | `LoginBody` | `AuthResponse` | 401 for bad credentials |
| A | `GET /auth/demo-users` | | `UserRef[]` | Only when `DEMO_MODE`, otherwise 404 |
| A | `POST /auth/demo-login` | `DemoLoginBody` | `AuthResponse` | Only when `DEMO_MODE`; only for `is_demo` users |
| A | `GET /me` · `PATCH /me` | `MeUpdate` | `Me` | Setting `dorm_id` switches the dorm membership |
| A | `GET /users/{id}` | | `UserPublic` | |
| A | `GET /users/{id}/items` | `offset, limit` | `Page<ItemCard>` | Only items visible to the viewer |
| A | `GET /users/{id}/reviews` | | `Review[]` | Newest first |
| A | `GET /communities` | `kind?, q?, mine?` | `Community[]` | |
| A | `POST /communities` | `CommunityCreate` | `Community` 201 | Group only; the creator becomes admin; a private group gets a 6-character `join_code` |
| A | `GET /communities/{id_or_slug}` | | `Community` | |
| A | `POST /communities/{id}/join` | `JoinBody` | `Community` | Private groups need the code; joining a dorm replaces the previous dorm |
| A | `POST /communities/{id}/leave` | | 204 | Not allowed for campus |
| A | `GET /communities/{id}/members` | `offset, limit` | `Page<UserRef>` | |
| A | `GET /places` | | `Place[]` | Exchange points, with `distance_min` |
| A | `POST /uploads` | multipart `file` | `Upload` 201 | jpeg/png/webp/heic, ≤ 15 MB; re-encoded as JPEG ≤ 1600 px with metadata stripped |
| A | `POST /items` | `ItemCreate` | `ItemDetail` 201 | Schedules `on_item_saved` |
| A | `GET /items/{id}` · `PATCH` · `DELETE` | `ItemUpdate` | `ItemDetail` / 204 | Owner-only writes; DELETE sets `archived=true` |
| A | `GET /me/items` | `status?` | `ItemCard[]` | All my non-archived items |
| A | `POST /items/{id}/borrow` | `BorrowBody` | `Transaction` 201 | 409 if the item isn't available or the viewer already has an open transaction on it |
| A | `POST /requests` | `RequestCreate` | `RequestDetail` 201 | Schedules `on_request_created` |
| A | `GET /requests/{id}` · `PATCH` | `RequestUpdate` | `RequestDetail` | Requester-only writes; edits schedule `on_request_updated` |
| A | `GET /me/requests` | | `RequestCard[]` | |
| A | `POST /requests/{id}/offers` | `OfferCreate` | `Transaction` 201 | Not your own request; `new_item` creates the item with `source='offer'` |
| A | `GET /transactions` | `role=owner\|borrower\|all`, `state=active\|past\|all` | `Transaction[]` | active = requested, offered, accepted, handed_off |
| A | `GET /transactions/{id}` | | `Transaction` | Parties only |
| A | `POST /transactions/{id}/actions` | `TxActionBody` | `Transaction` | Rules in §7.7; 409 if the action isn't allowed |
| A | `POST /transactions/{id}/review` | `ReviewCreate` | `Review` 201 | Only when completed; one review per party |
| A | `GET /conversations` | | `ConversationSummary[]` | Newest activity first |
| A | `POST /conversations` | `DirectConversationBody` | `ConversationSummary` | Gets or creates the direct thread |
| A | `GET /conversations/{id}` | | `ConversationSummary` | |
| A | `GET /conversations/{id}/messages` | `after_id?, limit=50` | `Message[]` | Ascending; `after_id` for polling |
| A | `POST /conversations/{id}/messages` | `SendMessageBody` | `Message` 201 | |
| A | `POST /conversations/{id}/read` | | 204 | |
| A | `GET /notifications` | `unread_only?, limit=50` | `Notification[]` | Newest first |
| A | `GET /notifications/unread-count` | | `UnreadCounts` | |
| A | `POST /notifications/read` | `MarkReadBody` | 204 | |
| A | `POST /events` | `EventsBody` | 204 | Never fails the client |
| C | `GET /search` | `q, kind=all\|items\|requests\|communities, category, community_id, scope=campus\|dorm, max_walk_min, transaction_type, condition, available_only=true, offset, limit` | `SearchResponse` | Explicit params override what was parsed from `q`; an empty `q` = browse |
| C | `GET /feed/home` | | `HomeFeed` | |
| C | `GET /communities/{id}/feed` | `kind=all\|items\|requests, offset, limit` | `Page<FeedEntry>` | Newest first |
| C | `GET /requests/{id}/matches` | | `MatchesResponse` | Only items visible to the viewer |
| C | `GET /me/fulfillable` | | `FulfillableRequest[]` | ≤ 20 |
| C | `POST /ai/parse-request` | `ParseRequestBody` | `ParsedRequest` | Rule-based, < 300 ms |
| C | `POST /scans` | `ScanCreate` | `Scan` 201 | 1..`AI_MAX_IMAGES_PER_SCAN` of your own uploads; 429 at the daily or budget limit |
| C | `GET /scans/{id}` | | `Scan` | Poll every 1.5 s while processing |
| C | `POST /scans/{id}/publish` | `ScanPublishBody` | `ScanPublishResponse` | Detections not included become `discarded` |

### 7.4 Visibility (one implementation, A's `services/visibility.py`)
- **viewer communities** = memberships (campus + dorm + groups).
- An item or request is **visible** if `owner == viewer` **or** one of its audiences is in the viewer's communities. Archived items are visible only to their owner (in `/me/items`).
- **Audiences on create/update:**
  - campus → {campus}
  - dorm → {owner's dorm} (400 if the owner has no dorm)
  - groups → `group_ids` (must be non-empty, and the owner must be a member of each)
- **Discovery** (search, feeds, matches) shows only items with status available, reserved, or borrowed. Unavailable and archived items are excluded.
- **Expired requests** are computed when read: `needed_until < today`, or no dates and older than 14 days. Expired requests are excluded from discovery.

### 7.5 Notifications (who gets what)
| Type | Recipient | Trigger | Link |
|---|---|---|---|
| `match` | owner of a matching item | C's matching (top 5 distinct owners per request) | `/requests/{id}` |
| `borrow_request` | item owner | `POST /items/{id}/borrow` | `/messages/{conversation_id}` |
| `offer` | requester | `POST /requests/{id}/offers` | `/requests/{id}` |
| `tx_update` | the other party | accept, decline, cancel, hand_off, mark_returned, plus completion (both parties: "leave a review") | `/messages/{conversation_id}` |
| `review` | reviewee | a review is created | `/profile` |
| `badge` | earner | a badge is awarded | `/profile` |

### 7.6 Standard event types (`POST /events`; B and C send them, A stores them)
`page_view`, `search_performed`, `search_result_clicked`, `item_viewed`, `scan_started`, `scan_review_shown`, `scan_published`, `onboarding_skipped`, `request_composer_opened`, `request_posted`, `offer_sent`, `share_clicked`, `invite_copied`, `feedback_submitted`. The payload is a small JSON object (ids, counts, seconds) and never contains free text from other people.

### 7.7 Transaction rules (A's `services/transactions.py`: one `apply_action()` and one `allowed_actions()` from this table)
| Status | Kind | Owner may | Borrower may |
|---|---|---|---|
| `requested` (initiated by borrower) | any | `accept`, `decline` | `cancel` |
| `offered` (initiated by owner) | any | `cancel` | `accept`, `decline` |
| `accepted` | any | `hand_off`, `cancel` | `hand_off`, `cancel` |
| `handed_off` | lend | `mark_returned` | (none) |
| `completed` / `declined` / `cancelled` | | (none) | (none) |

Transitions and side effects (all inside one DB transaction):
- **accept** → `accepted`.
  - The item must be `available`, otherwise 409.
  - Item becomes `reserved`. A linked request becomes `in_progress`.
  - Other `requested`/`offered` transactions on the **same item** are auto-declined, each with a system message.
  - `pickup_place_id` and `due_date` are copied from the body if given.
- **decline** → `declined`; **cancel** → `cancelled`. If this transaction had reserved the item, it goes back to `available`. If this was the in-progress transaction of a request, the request goes back to `open`.
- **hand_off**:
  - lend → `handed_off`; the item becomes `borrowed`.
  - give / exchange → `completed`; the item becomes `unavailable`.
- **mark_returned** (lend only) → `completed`; the item becomes `available`.
- **On completion:**
  - A linked request becomes `fulfilled` (`fulfilled_at` set), and its remaining `offered` transactions are auto-declined.
  - Points and badges are awarded (§7.8).
  - Both parties get a "leave a review" notification.
- Every transition writes a `transaction_events` row, a system message in the transaction's conversation, and a `tx_update` notification to the other party.
- `is_overdue` = `status == handed_off` and `due_date < today`.
- `pickup_note` is visible to both parties once the transaction is `accepted`.
- Creating a transaction (borrow or offer) creates its conversation. A non-empty `message` becomes the first text message.

### 7.8 Points, levels, badges (A's `services/points.py`)
| Event | Who | Points |
|---|---|---|
| Item published (first 10 per day) | owner | +2 |
| Lend completed | owner | +10 |
| Give completed | owner | +15 |
| Exchange completed | both | +10 |
| Transaction fulfilled a request | owner | +5 bonus |
| Borrow completed (item returned) | borrower | +2 |
| Review received with ≥ 4★ | reviewee | +2 |

**Levels:** New Neighbor 0 · Good Neighbor 20 · Helper 60 · Community Pillar 150 · Campus Legend 400.

**Badges** (re-checked after every relevant event):
| Badge | Rule |
|---|---|
| `first_share` 🌱 | ≥ 1 published item |
| `first_lend` 🤝 | ≥ 1 completed lend as owner |
| `generous` 🎁 | ≥ 3 completed gives |
| `request_hero` 🦸 | ≥ 5 fulfilled requests as owner |
| `trusted` ⭐ | ≥ 5 reviews with an average ≥ 4.5 |

`UserRef.rating_avg` is the average rating received, or `null` if there are none.

### 7.9 Geo (A's `core/geo.py`)
- `walking_minutes = max(1, round(haversine_m × 1.3 / 80))` (80 m/min, 1.3 detour factor).
- Item location = its pickup place if set, else the owner's dorm. Request location = its pickup place if set, else the requester's dorm. Viewer location = the viewer's dorm.
- If any of these is missing, `distance_min` is `null`.
- `same_dorm` = the owner's (or requester's) dorm is the viewer's dorm.

### 7.10 Cross-owner Python interfaces (the exact signatures A stubs in P0-A)
```python
# --- provided by A, used by C ---
# app/api/deps.py
def get_db() -> Iterator[Session]: ...
def get_current_user(...) -> User: ...                      # 401 if missing/invalid
def get_viewer(...) -> ViewerContext: ...

# app/services/viewer.py
@dataclass(frozen=True)
class ViewerContext:
    user_id: int
    dorm_id: int | None
    dorm_name: str | None
    lat: float | None
    lng: float | None
    community_ids: frozenset[int]        # campus + dorm + groups
    walking_radius_min: int
def build_viewer(db: Session, user: User) -> ViewerContext: ...

# app/services/visibility.py
def item_visible_clause(viewer: ViewerContext): ...        # SQLAlchemy boolean clause for .where(); owner OR audience match; excludes archived
def request_visible_clause(viewer: ViewerContext): ...
def user_can_view_request(db: Session, user_id: int, request_id: int) -> bool: ...

# app/services/serializers.py   (batched: never N+1)
def item_cards(db, items: list[Item], viewer, scores: dict[int, tuple[float, str]] | None = None) -> list[ItemCard]: ...
def item_detail(db, item: Item, viewer) -> ItemDetail: ...
def request_cards(db, reqs: list[ItemRequest], viewer) -> list[RequestCard]: ...
def community_out(db, c: Community, viewer) -> schemas.Community: ...
def user_ref(db, user: User) -> UserRef: ...

# app/services/items.py
def create_item(db, owner: User, data: ItemCreate, *, source: str = "manual",
                scan_detection_id: int | None = None, background: BackgroundTasks | None = None) -> Item: ...
    # validates, writes audiences + images, awards points/badges, schedules hooks.on_item_saved

# app/services/notifications.py
def notify(db, user_id: int, type: str, title: str, body: str, link: str,
           actor_id: int | None = None, data: dict | None = None) -> None: ...

# app/core/storage.py
def save_image_bytes(db, owner_id: int, data: bytes) -> Upload: ...     # same pipeline as POST /uploads
def read_upload_bytes(db, upload_id: int) -> bytes: ...

# --- provided by C, called by A (P0-A creates them as no-ops) ---
# app/discovery/hooks.py   (sync; each opens its own SessionLocal())
def on_item_saved(item_id: int) -> None: ...          # stub: pass
def on_request_created(request_id: int) -> None: ...  # stub: set matching_status='done'
def on_request_updated(request_id: int) -> None: ...  # stub: pass
def reindex_all() -> int: ...                         # stub: return 0
# app/ai/router.py and app/discovery/router.py each export `router = APIRouter()`; main.py includes both.
```

## 8. Seed data (A builds it in A2; P0-A seeds only communities and places)
- **Campus:** one community (`kind=campus`, slug `campus`, name "Stanford Campus").
- **Dorms:** one community each. Look up approximate coordinates once via OpenStreetMap Nominatim (1 request/s, generic User-Agent `daha-seed/0.1`) and commit them to `app/seed/data/dorms.json`. If a lookup fails, use a nearby point on campus and mark it `"approx": true`. The list:
  Wilbur Hall · Stern Hall · Florence Moore Hall (FloMo) · Lagunita Court · Roble Hall · Branner Hall · Toyon Hall · Crothers Hall · Governor's Corner · Manzanita Park · Mirrielees · Kimball Hall · Escondido Village · The Row · Off-campus (no coordinates).
- **Exchange points** (`places`): Tresidder Memorial Union · Cecil H. Green Library · Old Union · Main Quad · Arrillaga Family Dining Commons · Meyer Green.
- **Groups** (fictional): Robotics Club (club) · CS 106B Study Group (class) · Hiking & Outdoors (club) · Bio Lab 3rd Floor (research, private) · Hackathon Team Nova (team) · Film Society (org).
- **Users:** 30 fictional students spread across dorms. Emails are `<first>@demo.daha` (a non-routable domain, never `@stanford.edu`), password `daha-demo`, `is_demo=true`. Three hero accounts:
  - **maya@demo.daha**: Wilbur, 12 items, a lender with reviews and the `first_lend` + `trusted` badges.
  - **jordan@demo.daha**: FloMo, with an open request "Can I borrow a black binder next Wednesday?"
  - **sam@demo.daha**: Wilbur, 0 items, used for the onboarding demo.
- **Items:** about 150 realistic items across every category (Appendix §9), as names, descriptions, conditions, and types in `app/seed/data/items.json`.
  - Visibility mix: ~60% dorm, ~30% campus, ~10% groups.
  - Images: none. The web app shows an emoji tile per category.
  - Must include matches for the demo queries: several black binders, graphing calculators, two vacuums, a navy suit and a blazer, moving boxes available this weekend, and a "bike repair help" service.
- **Requests:** about 25 open requests in casual student phrasing, with dates relative to seed time, e.g. "Does anyone have a calculator?", "Anyone have a vacuum?", "Can I borrow a black binder next Wednesday?", "need a phone charger (usb-c) for tonight", "anyone have spices I could use? making curry".
- **History:** about 10 completed transactions with messages and reviews, plus 3 active ones for the hero accounts. The points ledger and badges must match that history.
- `make seed` is deterministic (fixed random seed). `--reset` truncates every table first. At the end it calls `discovery.hooks.reindex_all()`.

## 9. Categories
| Value | Label | Emoji | Examples | Default type |
|---|---|---|---|---|
| `academic` | Academic | 📚 | textbooks, calculators, notebooks, lab goggles | lend |
| `tech` | Tech | 💻 | chargers, adapters, monitors, keyboards, cameras | lend |
| `clothing` | Clothing | 👔 | suits, dresses, jackets, costumes, formalwear | lend |
| `dorm` | Dorm essentials | 🏠 | vacuums, fans, kettles, cookware, small appliances | lend |
| `consumables` | Consumables | 🧂 | spices, oil, packaged food, detergent, toiletries | give |
| `sports` | Sports & outdoors | 🚲 | bikes, helmets, rackets, camping gear | lend |
| `moving` | Moving | 📦 | boxes, carts, tools, storage bins | lend |
| `events` | Events | 🎉 | speakers, projectors, decorations, costumes | lend |
| `services` | Services | 🛠️ | tutoring, photography, bike repair, moving help | give (free) or exchange; **never** lend |
| `other` | Other | ✨ | anything else | lend |

## 10. MVP definition of done: the demo script
Run this on two phones plus a laptop, with `AI_PROVIDER=harnessrouter`, `NEXT_PUBLIC_MOCK=none`, and fresh seed data. Every step must work.
1. **Sam** signs up with a new `@stanford.edu` email in Wilbur → lands on "Show us what you have".
2. Sam takes 2 photos of a real desk or shelf. Items appear photo by photo, and the review screen shows at least 5 sensible items. Sam unticks one, renames one, chooses "My dorm · Lend", and taps **Share**. Under 60 s from the first photo, excluding AI wait time beyond 45 s per photo. Points appear.
3. Home shows "You could help", including at least one request that matches Sam's items.
4. **Jordan** (FloMo) posts "anyone have a black binder I can borrow next Wednesday?" The chips show *black binder · Academic · Wed <date> · Borrow*. Within about 10 s the request lists matching binders, and their owners get a `match` notification.
5. **Maya** opens the notification → "I can help" → offers her binder. Jordan accepts. They chat. Maya marks it handed off, then later "got it back". Both leave reviews. Points, badges, and the activity history update for both.
6. Search on the laptop:
   - "graphing calculator near me" → calculators, same dorm first, with walking minutes
   - "anyone have a vacuum in my dorm?" → only dorm-visible vacuums
   - "formal clothes for an interview" → suit/blazer
   - "moving boxes available this weekend" → boxes
   - "someone who can help repair my bike" → the bike repair service
7. In the Wilbur community channel, recent requests and shares appear like a chat feed. A new post from the composer appears at the top.
8. Privacy checks:
   - A dorm-only item from Wilbur is invisible to a FloMo user, both in search and by direct URL (404).
   - The pickup note is hidden until a transaction is accepted.
   - Downloaded photos have no EXIF data.
   - `grep -r "sk-hr" web/.next` finds nothing.

## 11. Solo mode and two-person mode
**Solo (one Claude does everything).** Skip B's mock layer and use `NEXT_PUBLIC_MOCK=none` throughout. Order:
1. P0-A, then P0-B
2. C0 (spike; the human gets the HarnessRouter key)
3. A1, then A2
4. B1 (auth, shell, home)
5. C1, then C4 (scan API + UI)
6. A3
7. C2, then C3
8. B2, then B3, then B4, then B5, then B6
9. A4, then A5
10. `plans/INTEGRATION.md`

Print the end-of-milestone block after each step.

**Two people.** Person 1 = A + C1–C3 (the whole backend). Person 2 = B + C4 (all the screens) + C0 (the spike; needs the key).

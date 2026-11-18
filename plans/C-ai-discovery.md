# Person C — AI, discovery & scan flow (later: integration + evals lead)

**Mission:**
- photo → items through HarnessRouter (scan API + scan screens)
- search, request parsing, request ↔ item matching, home and community feeds
- after Phase 1: drive integration (`plans/INTEGRATION.md`) and evals (`plans/EVALS.md`)

Contract: `PLAN.md` §6–§7. Your paths: `backend/app/ai/**`, `backend/app/discovery/**`, the C scripts and tests, `web` scan files, `evals/` (`PLAN.md` §4).

**Order:** C0 → C1 → C4 → C2 → C3 → C5. B uses mocks for search, feed, and matches until C2 and C3 land.

**⏰ Hackathon targets** (`PLAN.md` §0): C0 Tue 11:00 · C1 Tue 15:00 · C4 Tue 21:00 · C2 Wed 10:00 · C3 Wed 15:00 · C5 Wed 18:00 · integration Wed 18:00–22:00 · mini-eval and submission Thu.

## Status (2026-11-17): C1–C5 and the evals are merged; C0 is waiting for the key
| Milestone | Where | Notes |
|---|---|---|
| ⏸ C0 HarnessRouter spike | `docs/ai-spike.md` | the provider, setup and spike scripts are built and tested against a mocked stream. The latency/cost table needs one real run with the key (≈ $0.30) |
| ✅ C1 AI provider layer + scan API | `596372b` | mock / harnessrouter / anthropic |
| ✅ C4 scan flow UI (+ C5's web parts: Private option, "Tick what you have") | `baf1983` | |
| ✅ C2 embeddings, indexing, hybrid search | `2fe6978` | |
| ✅ C3 parsing, matching, fulfillable, feeds | `57908fc`, `a5bccfa`, `b361925` | |
| ✅ C5 private haves + anonymous pings | `57908fc`, `cd24366` | |
| ✅ Evals: parse, search, match suites + reports | `8f9e15b`, `evals/reports/` | parse: every field 1.00 · search: demo queries 5/5 in the top 3, nDCG@10 0.94, p95 66 ms · match: recall@5 1.00, precision@5 0.96. The scan suite waits for labeled eval photos |

C's work went straight to `main` without PRs, at the C human's explicit request (logged in `docs/decisions.md`).

**Behaviour that differs from, or adds to, the text below** (each line is in `docs/decisions.md`):
- **Vision output is re-validated on the server** (`app/ai/normalize.py`): IDs, cards, keys, cash, documents, meds, and "person"/"pet" names are dropped; hygiene items, underwear, cosmetics, and valuables are force-unticked with a reason; every field is clamped to the contract.
- **Scan publish** locks the scan row: a second publish → 409, and a failed publish rolls back fully. With no photo given, it crops to the bbox (which covers P1 #10).
- **Search:** a parsed category or borrow/swap is a soft boost. Only an explicit filter, "in my dorm", dates, and "free" filter hard. A semantic-only hit is kept only if it's ≥ 0.62 and within 0.07 of the best hit; trigram needs `word_similarity` ≥ 0.6.
- **Matching:** relevance = (0.65·semantic + 0.15·keyword) / 0.8 must reach 0.60 before proximity counts; `MATCH_MIN_SCORE` stays 0.55. Notifications go to the top 5 owners per request, at most 10 `match` notifications per owner per 24 h. Seeded requests get matches but no notifications.
- **Reverse matching** (P1 #1, without notifications): `on_item_saved` scores the item against open requests, and "You could help" reads `request_matches`.
- **`private_pinged_count`** is shown only to the requester, and counts the `private_match` notifications actually sent.
- **Community feed** shows open, in-progress, and fulfilled requests. Private groups → 404 to non-members.
- **HarnessRouter concurrency** is per API process, so run one API worker on the free plan.
- **Not done:** `AI_ENRICH_REQUESTS` (P1 #3) is only a flag; no code uses it yet.

**If behind, cut** (in this order):
1. C5 as a whole, if it hasn't started by Wed 14:00 (defer it to after the hackathon)
2. `on_request_updated` re-matching
3. the community feed's `kind` filter
4. every P1 and LLM extra

## 🧑 Human TODOs (C)
- [ ] **HarnessRouter key:**
  1. Sign in at https://app.harnessrouter.ai with the account that holds our $50 credit. If that isn't your account, ask its owner in the group chat to create the key and share it with you privately.
  2. Create a **Workspace API key** (`sk-hr-…`). Discovery endpoints need a Workspace key.
  3. Tell Claude *"the key is in my clipboard"* and paste it **only** into `backend/.env` (and the spike's `.env`) as `HARNESSROUTER_API_KEY=`.
  4. Never paste it in chat, Discord, screenshots, or code.
- [ ] **Photos:** take 20–30 photos of real spaces (desk, open drawer, closet, shelf, kitchen or pantry, common room). **No people, no documents, IDs, or screens with personal info.**
  - Put 3 of them in `~/daha-spike/photos/` for the spike.
  - Ask A and B for about 10 each. Together they become the eval set later.
- [ ] **Decide the model with the team** after the spike: Claude prints a cost and latency table. Cost is the humans' call.
- [ ] **Watch spend** on the HarnessRouter dashboard. Tell the team when $25 is spent. Claude enforces a $40 hard stop (`AI_BUDGET_USD`).
- [ ] Optional fallback: if HarnessRouter vision is too slow or unreliable, get an Anthropic API key and set `AI_PROVIDER=anthropic`.
- [ ] At every ✅ checkpoint: merge the PR and paste the message.
- [ ] **Phase 2:** host the integration session on your laptop, which has the key. **Phase 3:** label the eval photos (about 1 hour; Claude prepares a labeling sheet).

## Design points (go through these with the human in *involved* mode; in hands-off mode use the defaults as written)
- **Model:** which HarnessRouter base and model to use, after the C0 spike's cost and latency table. Cost is the human's call.
- **Sensitive items:** what the AI should never pre-tick for sharing.
- **Scan review:** how much to pre-fill, plus the default visibility and default type.
- **Ranking:** closeness vs. best match vs. newest.
- **Match notifications:** how eager to be (how many owners get pinged per request).
- **Anonymous pings for private haves (C5):** the daily cap per person (default 3) and the wording.

## Research & proposals (async)
Research these in small slices, after a milestone or while CI runs. **Never let research block a milestone.** Write each finding as a proposal (`AGENTS.md` §6, template in `docs/proposals/README.md`) and present it at the start of the next session.

- **Web search.** Andre has a web search API key. When you need it, print a 🧑 TODO: *"Tag Andre in the group chat for the web search API key."* Promising uses:
  - pin down the exact product from a scan (e.g. "TI-84 Plus CE") and add its specs and typical retail price. That powers "you saved ~$X by borrowing" impact stats (`plans/ROADMAP.md` #9);
  - "nobody has it yet" fallback: find campus resources that lend the item (libraries, tool libraries, rentals nearby) and show them on the request;
  - autofill descriptions for manual listings.
  Keep calls server-side, cached, and rate-limited. Never send personal text or photos of people.
- A better embedding model or a reranker (hosted vs. local). Only worth it if the evals show search quality is the bottleneck.
- Other vision providers (e.g. the direct Claude API) vs. HarnessRouter, compared on the spike's cost and latency numbers.
- An image and text moderation API for inappropriate photos or posts.
- LLM request enrichment (P1): which model, and the cost per request.

## ⏸ C0 — HarnessRouter spike (do this now: no repo needed, ≤ 1 h)
**What HarnessRouter is.** It runs full **agent harnesses** (Claude Code, Codex, Pi, …) behind one API. It does **not** give plain single-shot model calls. A "task" is: upload files → run the harness → get the final answer text, or files the agent wrote. Tasks can take tens of seconds to minutes.

What we know from the docs (re-check https://harnessrouter.ai/docs first, especially its quickstart prompt for coding agents):
- **Base URL:** `https://api.harnessrouter.ai`. All paths are `/v1/...`.
- **Auth header:** `Authorization: Bearer $HARNESSROUTER_API_KEY`.
- **Discovery:**
  - `GET /v1/bases`: each base and its allowed models and budget defaults.
  - `GET /v1/models`: the model catalog. Note: base `claude-code` appears under the backend key `claude`.
- **Create a harness:** `POST /v1/harnesses` with `{"name", "base", "default_model", "system_prompt", "mcp_servers": [], "skills": []}`. Optional per-turn budgets: `"max_step"`, `"timeout_seconds"`, `"max_cost_usd"` (the default is $10, so **set it low**). Optional `"disabled_tools"`.
- **Upload a file:** `POST /v1/files`, multipart with `file` (≤ 25 MiB) and `purpose=user_data`. Returns an `id`.
- **Run a task:** `POST /{harness_id}/v1/responses`. (One docs page instead shows `POST /v1/responses` with `metadata.harness_id`; try the path form first.)
  - Headers: `Idempotency-Key: <uuid4>`, `Content-Type: application/json`.
  - Body: `{"input":[{"role":"user","content":[{"type":"input_file","file_id":"<id>"},{"type":"input_text","text":"<task>"}]}],"stream":true}`.
- **Stream:** OpenAI Responses-style `data:` frames whose `type` is one of:
  - `response.created`: save `response.id` and `response.metadata.session_id`
  - `response.output_text.delta`: append the text
  - `response.output_item.added`: progress
  - exactly one terminal event: `response.completed`, `response.incomplete`, or `response.failed`
  - Polling alternative: `GET /v1/responses/{id}`. Continue a session with `previous_response_id`. Files the agent wrote: `GET /v1/sessions/{session_id}/files`.
- **Pricing:** model tokens at provider rates plus "agent work" of about $0.014–0.02 per active minute. Waiting is free. The free plan allows 2 concurrent tasks.

**Spike steps:**
1. Create `~/daha-spike/hr_spike.py` (httpx; reads `.env`). Copy it to `backend/scripts/hr_spike.py` once the repo exists.
2. Print `GET /v1/bases` and `GET /v1/models`. Pick ≤ 2 candidate configs: `claude-code` with the best Claude model listed, and one minimal base (`pi` or `codex`) with a vision-capable model.
3. Create one harness per config:
   - `system_prompt` = `VISION_SYSTEM` (§C1.3)
   - `max_step: 6`, `timeout_seconds: 180`, `max_cost_usd: 0.5`
   - disable write and exec tools if the base supports it
4. For each of the 3 photos × each config:
   - upload the photo
   - run the task with `VISION_TASK`
   - record time to `response.created`, time to the first delta, and total time
   - parse the final text as JSON (strip code fences; take the outermost `{…}`) and validate it against `DetectionPayload`
   - record the cost, if the response or dashboard shows it
5. Save raw outputs to `~/daha-spike/out/`. Print a table: config, p50 and max latency, JSON valid (n/3), item count, estimated $ per photo.
6. **Recommend** the cheapest config with valid JSON on 3/3 photos, sensible items, and p50 ≤ 45 s. If none qualifies, print a **🧑 Human TODO (blocking)** with these options:
   - (a) keep HarnessRouter with a slower async UX
   - (b) `AI_PROVIDER=anthropic` (needs a key; a few seconds and a few cents per photo)
   - (c) mock-only for now
7. Later, in the repo, write `docs/ai-spike.md`: the table, the chosen base and model, and the exact working endpoint and payload shapes.

Checkpoint: *"C0 ✅ HarnessRouter vision works: <base>/<model>, ~<s>s and ~$<x> per photo. $50 ≈ <n> photos. Need team OK on model."*

## ✅ C1 — AI provider layer + scan API (after P0-A is merged)
### C1.1 Files
`app/ai/schemas.py` (`DetectedItemRaw`, `DetectionPayload {items: list[DetectedItemRaw]}`) · `app/ai/prompts.py` (`PROMPT_VERSION="vision-v1"`, `VISION_SYSTEM`, `VISION_TASK`) · `app/ai/providers/{base,mock,harnessrouter,anthropic}.py` · `app/ai/vision.py` · `app/ai/scans.py` · `app/ai/router.py` (replaces A's 501 stubs for `/scans*`; `/ai/parse-request` comes in C3) · `scripts/setup_harnessrouter.py` (creates the harness and prints `HARNESSROUTER_VISION_HARNESS_ID`).

### C1.2 Provider interface
```python
class VisionProvider(Protocol):
    name: str; model: str
    async def detect(self, image_jpeg: bytes, filename: str) -> ProviderResult: ...
    # ProviderResult: items: list[DetectedItemRaw], latency_ms: int, cost_usd: float | None, raw: dict
def get_vision_provider() -> VisionProvider   # by settings.AI_PROVIDER
```
- **mock:**
  - deterministic by image sha256: 4–9 items picked from a pool of about 60 realistic dorm items across categories
  - about 30% of the time it includes one sensitive item (e.g. a toothbrush with `suggested_share=false`)
  - sleeps for `AI_MOCK_LATENCY_MS`
- **harnessrouter:** exactly as proven in the spike.
  - Run: upload → run (stream) → collect text → extract JSON → validate.
  - If the JSON is invalid: make one repair turn (`previous_response_id` + "Return only the JSON object."), otherwise raise.
  - Limits: concurrency via `asyncio.Semaphore(HARNESSROUTER_MAX_CONCURRENCY)`; timeout `HARNESSROUTER_TIMEOUT_S`; 1 retry on network or 5xx errors.
  - Cost: from usage if reported, otherwise `HARNESSROUTER_EST_COST_PER_IMAGE`.
- **anthropic** (optional): load the `claude-api` skill before writing it.
  - Use the official `anthropic` SDK: `AsyncAnthropic()`, model `ANTHROPIC_MODEL` (default `claude-opus-5-5`).
  - Call `messages.parse(..., output_format=DetectionPayload)` with a base64 image block plus `VISION_TASK`, and `output_config={"effort": ANTHROPIC_EFFORT}`.
  - Check `stop_reason == "refusal"`, and enable server-side refusal fallbacks as the skill recommends.
  - Cost = usage × the model's price.

### C1.3 Vision prompt v1 (tune it later with evals)
`VISION_SYSTEM`: "You are DAHA's inventory scanner for a college campus sharing app. You look at one photo of a student's space and list the distinct physical items a student could reasonably lend, give away, or swap. Reply with only a JSON object — no prose, no code fences."

`VISION_TASK`: "Open the image file `{filename}` in your working directory. Return JSON:

`{"items":[{"name","category","description","quantity","condition_guess","confidence","bbox","suggested_share","sensitive_reason","suggested_transaction_type"}]}`

Field values:
- `category` ∈ academic | tech | clothing | dorm | consumables | sports | moving | events | services | other
- `condition_guess` ∈ new | like_new | good | fair | worn, or null
- `confidence` is between 0 and 1
- `bbox` is [x, y, w, h] normalized to 0..1, or null
- `suggested_transaction_type` ∈ lend | give | exchange

Rules:
- One entry per distinct item. Identical items become one entry with a quantity.
- Names are short, specific, and generic ("Graphing calculator (TI-84)", "Black 3-ring binder", "Desk lamp"). Include a brand only if it's clearly visible.
- The description is one friendly sentence of at most 140 characters: color, size, notable features.
- Skip tiny clutter, trash, and university-provided fixed furniture (bed, built-in desk, dresser, wardrobe).
- **Never** list people, pets, ID or bank cards, keys, cash, documents or papers with text, prescription medication, or anything that reveals identity or location. Never transcribe personal text.
- Set `suggested_share=false` with a `sensitive_reason` for personal-hygiene items, underwear, opened cosmetics, and valuables such as jewelry.
- Food, spices, and toiletries → consumables, give. Most other things → lend.
- List at most 20 items, most useful first. If nothing is shareable, return `{"items":[]}`."

### C1.4 Scan pipeline (`app/ai/scans.py`)
- **`POST /api/scans`:**
  - Check 1..`AI_MAX_IMAGES_PER_SCAN` uploads owned by the viewer, the daily limit, and the budget (sum of `scan_images.cost_usd` + estimates ≥ `AI_BUDGET_USD` → 429 "AI scanning paused — list items manually").
  - Create `scans` and `scan_images` rows (status pending). Schedule the async `process_scan(scan_id)`.
  - Return `Scan`.
- **`process_scan`** (opens its own session):
  - For each image concurrently:
    1. mark it processing
    2. `read_upload_bytes` → downscale to ≤ 1568 px
    3. `vision.detect`: check `ai_cache` first; normalize (clamp confidence, map unknown categories to `other`, dedupe by name within the photo, cap at 20)
    4. insert `scan_detections`, setting `suggested_share` = provider value AND confidence ≥ 0.35
    5. mark it done with latency, cost, and raw response
  - On error, mark the image failed with a short, user-safe message.
  - Finally: the scan is `done` if any image succeeded, otherwise `failed`.
  - A `GET` on a scan stuck in processing for more than 10 minutes marks it failed.
- **`POST /api/scans/{id}/publish`:**
  - The scan must be the viewer's and `done`.
  - For each item, call `items.create_item(..., source="scan", scan_detection_id=…)`.
  - Images: if `image_upload_ids` is empty, crop to the bbox (8% padding, via `save_image_bytes`) when there is one, otherwise use the source photo.
  - Mark each detection published, storing `edits` = the fields the user changed (name, category, quantity, transaction type, description, condition). Every other detection becomes discarded.
  - Set `me.onboarded=true` and return `ScanPublishResponse`.
- **Tests** (`tests/ai/`):
  - the mock pipeline end to end: create → poll → publish → items exist; detection statuses and edits are recorded
  - JSON extraction (fenced, wrapped in prose, invalid)
  - the HarnessRouter client against a respx-mocked SSE stream
  - the 429 limits

Checkpoint: *"C1 ✅ scan API live (mock + harnessrouter). Scans + publish create real items."*

## ✅ C4 — Scan flow UI (`/onboarding` and `/add/scan`)
- Files:
  - `web/src/lib/api/endpoints/scans.ts`
  - `web/src/lib/api/mock/scans.ts`: progressive. Images finish one by one about every 1.5 s with 3–7 detections each
  - `web/src/lib/queries/scans.ts`
  - `web/src/components/scan/*`
- **Capture:**
  - "Take photos": `<input type="file" accept="image/*" capture="environment" multiple>`
  - "Choose from library": the same input without `capture`; drag and drop on desktop
  - thumbnails with remove; at most 6
  - tip: "One area per photo — open the drawer or closet"
  - `downscale.ts`: `createImageBitmap(file, {imageOrientation: "from-image"})` → canvas, ≤ 1600 px → JPEG 0.85
- **Processing:**
  - upload each photo, then `POST /api/scans`, then poll every 1.5 s
  - per photo, show a shimmer and then "Found 4 items"
  - the user can start reviewing as soon as the first photo is done
- **Review:**
  - grouped by photo
  - each row: checkbox (pre-ticked if `suggested_share`), editable name, category select, quantity stepper, Lend / Free / Swap toggle, and an expandable section for description and condition
  - sensitive rows start unticked and show their reason
  - "Add something we missed" adds a manual row (`detection_id: null`)
  - **Defaults bar:** share with My dorm (default) / Campus / Groups; default type; pickup spot (`places`)
  - sticky footer: **Share N items**
- **Success:** "🎉 6 items shared with Wilbur · +12 points". Links: "See requests you can help with" → `/home`, plus "Invite your roommates" (copy the invite link).
- **`/onboarding`:**
  - same flow under a hero, "Show us what you have"
  - "Skip for now" → `PATCH /me {onboarded:true}` → `/home`, plus the `onboarding_skipped` event
- **Events:** `scan_started`, `scan_review_shown` (n detections, seconds), `scan_published` (published, edited, discarded, total seconds).
- **Target:** with 2 photos on mock, the whole flow takes ≤ 60 s.
- **Mobile:** this flow is mostly used on phones. Follow the mobile checklist in `plans/B-frontend.md` §1 (safe areas, ≥ 16 px inputs, the sticky Share bar stays above the keyboard), and test on a real iPhone and Android.

Checkpoint: *"C4 ✅ scan flow live at /onboarding and /add/scan."*

## ✅ C2 — Embeddings, indexing, search
- **`app/discovery/embeddings.py`:**
  - `embed_passages(texts)`, `embed_query(text)`
  - `fastembed`: `TextEmbedding(EMBEDDING_MODEL)` as a lazy singleton; use `passage_embed` and `query_embed`
  - `hash`: deterministic feature hashing into 384 dimensions, L2-normalized; used in tests and CI
- **Text recipes:**
  - item: `"{name}. {category label}. {description}"`
  - request: `"{title}. {item_name}. {attributes}. {raw_text}"`
- **Hooks:** `on_item_saved` (embed + store); the embedding part of `on_request_*`; `reindex_all` (batches of 64; also `make reindex`).
- **`query_parser.py`** (rules only, no LLM; < 5 ms) → `ParsedQuery`:
  - "near me" → `near_me`
  - "in my dorm" / "my dorm" → `scope=dorm`
  - "today" / "tonight" / "tomorrow" / "this weekend" / weekday names → dates in `CAMPUS_TZ`
  - "free" / "giveaway" → give; "borrow" → lend; "swap" / "trade" → exchange
  - "someone who can" / "help with" / "repair" / "tutor" / "lesson" → services
  - a keyword → category map (calculator → academic, vacuum → dorm, suit / interview / formal → clothing, boxes / moving → moving, charger → tech, …)
  - strip filler words ("anyone have", "available", "near me", …) from `text`
  - `chips` in plain English
- **`search.py`:**
  - **Candidates:** the union of pgvector top 200, FTS top 100, and trigram top 100. All are filtered by `item_visible_clause`, discovery statuses (`PLAN.md` §7.4), and the explicit and parsed filters. `max_walk_min` defaults to the viewer's radius when `near_me` is set.
  - **Score** = 0.55·semantic + 0.25·keyword + 0.15·proximity + 0.05·freshness:
    - semantic = 1 − cosine distance
    - keyword = max(normalized `ts_rank_cd`, trigram similarity)
    - proximity: 1.0 in the same dorm, else e^(−walk/12)
    - freshness = e^(−age_days/30)
    - multiply the total by an availability factor: available 1.0, reserved 0.5, borrowed 0.3
    - `near_me` raises the proximity weight to 0.35 and renormalizes
  - The weights live in `discovery/config.py`.
  - `match_reason`, e.g. "Same dorm · 2 min walk · Available".
  - **Requests:** the same pipeline over open, visible, non-expired requests. **Communities:** ILIKE on name.
  - **Empty `q`:** browse mode (same dorm first, then distance, then newest).
  - Log every search to `search_logs`. Target p95 < 300 ms on seed data.
- **Tests:**
  - parser table (≥ 25 cases, including the 5 demo queries)
  - visibility leaks: dorm-only and group items never leak, in search or feeds
  - filters
  - a `@pytest.mark.slow` quality test with fastembed on seed data: each demo query's top 3 contains its expected seed item

Checkpoint: *"C2 ✅ search live. B: unmock search."*

## ✅ C3 — Request parsing, matching, feeds
- **`app/ai/request_parser.py` → `POST /api/ai/parse-request`** (rules; < 300 ms):
  - `kind`:
    - request: "anyone have", "can I borrow", "looking for", "need", "?"
    - offer: "does anyone want", "giving away", "free", "up for grabs"
    - otherwise: other
  - `item_name` + `attributes`: strip request phrases to get the noun phrase; colors and sizes go into attributes
  - `category`: keyword map, falling back to the nearest category-description embedding
  - dates (`dateparser` + custom rules, `CAMPUS_TZ`):
    - "<weekday>" or "this <weekday>" = the next occurrence
    - "next <weekday>" = that weekday in next calendar week
    - "tonight" / "today" / "tomorrow" / "this weekend" (Sat–Sun)
    - "for N days" / "for a week" / "overnight" → `duration_days`
  - quantity: "2 chairs", "a couple" → 2
  - type: borrow → lend; keep / have → give; swap / trade → exchange
  - `title` = the item name, capitalized; `confidence` = a heuristic
  - Tests: ≥ 30 table cases, including the four dorm-chat examples from the brief.
  - P1: background LLM enrichment behind `AI_ENRICH_REQUESTS`.
- **`app/discovery/matching.py`:**
  - `on_request_created(id)`:
    1. embed the request
    2. candidates: items visible to the requester **and** whose owner can view the request (`user_can_view_request`); status available or reserved; owner ≠ requester; not archived
    3. score = 0.65·semantic + 0.15·keyword + 0.20·proximity; keep scores ≥ `MATCH_MIN_SCORE`
    4. write the top 10 to `request_matches` with a reason
    5. `notify` the top 5 distinct owners with type `match` and copy like "Jordan in FloMo needs a black binder — you have one"; mark `notified`
    6. set `matching_status='done'`
  - `on_request_updated`: recompute, and notify only owners who weren't notified before.
  - **Calibrate** `MATCH_MIN_SCORE` on seed data: keep the true demo matches, drop obvious non-matches. Log the decision.
- **Endpoints:**
  - `GET /requests/{id}/matches`
  - `GET /me/fulfillable`: open, visible, non-expired requests by others from the last 21 days; for each, my available items scoring above the threshold; ≤ 20 results by score
  - `GET /feed/home` (`PLAN.md` §7.2 `HomeFeed`):
    - `requests_nearby`: same dorm first, then distance, then newest
    - `new_nearby`: visible available items that aren't mine, same dorm first, within the walking radius, newest first; fall back to campus if fewer than 6
    - `you_can_help` = the top 5 fulfillable
  - `GET /communities/{id}/feed`: entries whose audiences include the community, **plus** campus-visible entries by its members; visible to the viewer; newest first; `kind` filter
- **Tests:**
  - matching on seed data ("black binder" finds seeded binders, same dorm first)
  - no match notifications to owners who can't see the request
  - fulfillable correctness
  - community feed visibility

Checkpoint: *"C3 ✅ parse-request, matches, fulfillable, home + community feeds live. B: NEXT_PUBLIC_MOCK=none."*

## ✅ C5 — Private "I have this" + anonymous pings (from user feedback)
**Why:** many people won't post a public listing, but they're happy to help when asked. They tick what they own ("bike pump", "tool kit"). Nobody sees the list, and DAHA quietly pings them when someone nearby needs one.

- **Matching** (`on_request_created` / `on_request_updated`):
  - Also score **private** items with `pings_enabled=true` whose owner can view the request and isn't the requester. Use the same score and threshold as public matches.
  - Store these matches in `request_matches` with `anonymous=true`.
  - **Never** return them in match lists, search, or feeds.
- **Pings:** send `private_match` to the top 5 distinct private owners.
  - Wording: "Someone in FloMo needs a bike pump. You said you have one — want to help? They won't know it's you unless you offer."
  - Link: `/requests/{id}?offer_item={item_id}`.
  - At most 3 pings per person per day (count the last 24 h). Never ping the same person twice for one request.
- **`GET /requests/{id}/matches`** returns `private_pinged_count`: how many anonymous pings were sent for this request. It's a number only, never who.
- **"You could help"** (`/me/fulfillable` and the home feed) includes **my own** private items. They're mine, so that's allowed.
- **Quick checklist: "Tick what you have"**, shown in `/onboarding` next to the photo scan and on the scan success screen.
  - About 30 common lendables with emoji, listed in `web/src/components/scan/commonHaves.ts`: bike pump, tool kit, HDMI cable, extension cord, iron, umbrella, calculator, phone charger…
  - Ticked items become private items through `POST /api/items/batch`.
- **Scan review (C4):** each detection, and the defaults bar, gets a **Private: ping me only** choice next to My dorm / Campus / Groups.
- **Tests:**
  - private items never appear to others: search, feeds, profiles, match lists, direct URL → 404
  - one ping per owner per request, and the cap of 3 per day
  - the requester's view shows only the count
  - offering with a private item works, and reveals the owner only through the offer
- **Depends on:**
  - A2: private items and `POST /items/batch`
  - B3–B5: the Private option, the "quietly asked N people" line, and the notification's Help anonymously button

Checkpoint: *"C5 ✅ private haves + anonymous pings live. B: show the Private option, the 'quietly asked N people' line, and private_match notifications. Phase 1 done (C)."*

## Follow-ups after the MVP (from user feedback; build after `v0.1-mvp`, proposal first)
These build on C5's private inventory. Start each one as a proposal (`AGENTS.md` §6) so the team can prioritise it after the demo feedback.

- **F1 · Personal inventory keeper.** "My stuff" becomes a searchable list of everything you own, shared and private, grouped by area (desk, closet, kitchen…; the area comes from the scan photo).
  - **"You already have this":** when you write a request, DAHA first checks your own inventory ("You may already have one: HDMI cable, desk drawer"). That saves asking, or buying, for nothing.
  - **Find my stuff:** search your own things.
  - Needs: an optional `storage_spot` field on items (A, additive); the "My stuff" view (B); the own-inventory check in the request composer (C, same embeddings).
- **F2 · Declutter mode ("Marie Kondo").** Swipe through your inventory: **Keep · Share · Give away**.
  - Give-away items are posted as Free with a pickup window ("come grab it by Sunday"), and neighbors come and take them. No throwing things out, no trip to a donation center.
  - A feel-good summary at the end: "You rehomed 12 items."
  - Pairs well with a **move-out week** campaign, when a lot of stuff gets thrown away on campus.
  - Needs: the swipe flow (B); bulk visibility and type changes (A, additive); give-away boosts in feeds (C).
- **F3 · Gentle nudges.** For example "You haven't lent your tent in 6 months — share it or give it away?", or seasonal prompts like "finals: share your calculator". Opt-in and rate-limited. Ties into `plans/ROADMAP.md` #3–#5.

## After Phase 1 (C)
Drive integration with `plans/INTEGRATION.md`, then evals with `plans/EVALS.md`.

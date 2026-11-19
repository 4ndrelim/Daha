# Plan: AI-powered mutual matching ("You two can help each other")

- Status: **hackathon version built 2026-11-18** (H0–H5, behind `MUTUAL_MATCHING`, default `off`) · full version not started · proposal: `docs/proposals/A-mutual-matching.md` · results in §13
- Owners by path: **C** (`backend/app/discovery/**`, `backend/app/ai/**`, `evals/`) · **A** (models, migration, schemas, config, seed, `.env.example`) · **B** (`web/` Home card, settings, types, mocks). Built by A with B's and C's scope approval; every PR that touches B's or C's files waits for their 👍.
- Effort: hackathon version about **9 h** of building (§9a) · full version about **2 weeks** across A, B and C (§9b)
- Depends on: C3 matching and C5 anonymous pings (merged), A3 notifications and events (merged), the HarnessRouter keys and harness setup (working since 2026-11-18), and **C's OK for each paid run** (`AGENTS.md` §3)

## 1. The rule
"Mutual matching" can mean three different things. They are not exclusive, but the plan needs one definition.

| Option | What it means | Good | Bad |
|---|---|---|---|
| **a. Reciprocal** | A has something B needs **and** B has something A needs | Easy to explain; a fair trade feels better than a favor; fully checkable with data we already store | Rare when few people have posted requests |
| **b. Both opt in** | Nobody is introduced unless both people agreed to be matched | Safest for privacy | Says nothing about *who* to match |
| **c. Habit-based** | An agent learns what each person tends to lend and borrow and recommends people | Works before someone posts a request | Guesses can be wrong or feel creepy; costs money |

**Recommended definition (a + b, with c only filling gaps):**

> A **mutual match** is a pair of students who have **both turned matching on**, where **each has an available item the other needs**. Both see the same pair. Nothing is sent or shared until one of them taps.

- A **need** is, strongest first: (1) an open request, (2) a recent search that found nothing useful, (3) a need the agent predicted from the person's habits. Kinds 2 and 3 are always worded as a guess ("might need").
- A **have** is an available item the other person is allowed to see. Private "I have this" items never appear on someone else's screen (§6).
- The pair must pass the existing visibility rules **in both directions** (`PLAN.md` §7.4): each person can see the other's item, and each request is visible to the item's owner.
- One-way help is not new. It stays where it is: "You could help", match notifications, anonymous pings.

## 2. Where we are today
- **One-way matching exists and is good.** `backend/app/discovery/matching.py`: `match_request()` scores a request against items (`score_items()`, weights in `backend/app/discovery/config.py` → `MATCH_WEIGHTS`), stores up to 50 rows per request in `request_matches`, and notifies the top 5 owners. `reverse_match_item()` does the same when an item is added. Evals: recall@5 1.00, precision@5 0.96 (`evals/reports/2026-11-17-match.md`).
- **`request_matches` already holds half of every mutual match.** A reciprocal pair is two rows pointing in opposite directions: (A's request → B's item) and (B's request → A's item). Nothing reads the table that way yet.
- **Anonymous pings (C5)** live in the same function: private items are scored, stored with `anonymous=true`, and pinged at most 3 times per person per day (`PRIVATE_PINGS_PER_DAY`).
- **Caps that exist:** 5 owners per request (`MATCH_NOTIFY_OWNERS`), 10 `match` notifications per owner per 24 h (`MATCH_NOTIFY_PER_OWNER_PER_DAY`), no notifications for seeded requests.
- **Hooks:** `backend/app/discovery/hooks.py` (`on_item_saved`, `on_request_created`, `on_request_updated`) run as FastAPI background tasks. There is no scheduler or cron anywhere in the repo.
- **Notifications:** `backend/app/services/notifications.py` → `notify()`; types in `PLAN.md` §7.5.
- **Habit data we already log, and nobody reads yet:**
  - `search_logs` (C): `user_id`, `raw_query`, `parsed`, `result_item_ids`. A search with no results is a need nobody posted.
  - `events` (A stores, B and C send): `search_result_clicked`, `item_viewed`, `request_posted`, `offer_sent` and more (`PLAN.md` §7.6).
  - `transactions`, `transaction_events`, `reviews` (A): who lent what to whom, how fast they answered, how it went.
  - `items` and `requests` themselves: what someone lists and asks for, by category.
- **HarnessRouter today:** one harness per key for photo scans (`backend/app/ai/providers/harnessrouter.py`, `backend/scripts/setup_harnessrouter.py`), with a key pool, a budget check, a cache (`ai_cache`), server-side validation (`backend/app/ai/normalize.py`) and one repair turn. A text-only task has never been run. The generic task runner in `docs/research/harnessrouter-workflows.md` §4 is designed but not built.
- **Home feed:** `backend/app/discovery/feeds.py` → `home_feed()` builds "You could help" from `fulfillable()`.
- **Not measured yet:** how many reciprocal pairs the demo data contains. It is the first step of the build (H0).

## 3. Architecture
The agent does one job: turn a person's own activity into a short **habit profile** with a few **predicted needs**. Finding, scoring, checking and showing pairs stays local, rule-based and free.

```
 user activity (already stored)                       HarnessRouter (paid, slow, background)
 items · requests · search_logs · events · transactions
        │
        ▼
 ┌─ profile builder (local, free) ────────┐   compact, anonymous JSON     ┌──────────────────────┐
 │ counts per category, own item names,   │ ────────────────────────────▶ │ "daha-profile"       │
 │ own request titles, cleaned searches   │   (no name, id, dorm, email)  │ harness: no tools,   │
 │ → signal count, input hash             │ ◀──────────────────────────── │ JSON out, cost cap   │
 └───────────────┬────────────────────────┘   habit profile + ≤ 5         └──────────────────────┘
                 │                            predicted needs (validated)
   < 3 signals   │   ≥ 3 signals, opted in, changed since last run
   rules only    ▼
 ┌─ user_profiles · user_needs (Postgres) ─┐
 │ needs: request | search | predicted     │
 └───────────────┬─────────────────────────┘
                 ▼
 ┌─ mutual matcher (local, free) ─────────────────────────────────────────┐
 │ direction A→B: score_items() from C3 (semantic + keyword + proximity)  │
 │ pair = both directions pass · both opted in · visibility both ways     │
 │ → mutual_matches (full version) or computed on read (hackathon)        │
 └───────────────┬────────────────────────────────────────────────────────┘
                 ▼
 GET /api/me/mutual-matches → Home card "You two can help each other"
 notify() → at most 1 `mutual_match` per person per day
```

**Where each part runs**
| Part | When | Where |
|---|---|---|
| Strict pairs (request ↔ request) | at request time, on `GET /me/mutual-matches` | one SQL self-join on `request_matches`; target p95 < 300 ms |
| Profile builder (rules) | when the person opens Home, if their activity changed | local, a few milliseconds |
| Profile agent | background task after the response is sent; never blocks a page | HarnessRouter, about 15–20 s per task |
| Predicted-need scoring | when a profile changes, and in `on_item_saved` (next to `reverse_match_item`) | local embeddings (fastembed), same scorer as C3 |
| Notifications | after scoring, inside the caps in §5 | `notify()` |

**What HarnessRouter does, and what it never does**
- Does: read one compact JSON about one person (or a small batch of anonymous people) and return a profile: 1 summary line, the categories they lend, the categories they borrow, and up to 5 things they will probably need soon, each with a confidence.
- Never: sees who the person is, picks or ranks partners, reads other people's text, uses tools, the web or files, or writes anything. Its output is data that we validate; nothing in it is executed or shown without the checks in §6.

**Triggers.** There is no scheduler, so the refresh is lazy: opening Home checks the profile. If it is older than 24 h **and** the input hash changed, a background task refreshes it. The full version adds `make match-profiles` for a nightly cron on the hosted VM (A).

**Caching.** `user_profiles.input_hash` = sha256 of the compact JSON plus the prompt version and model. Same hash → no call. `ai_cache` keeps the validated answer under that hash, so a re-run after a crash is free.

**Sharing the key pool with scans.** The free plan runs 2 tasks at a time per organization (`docs/research/harnessrouter-workflows.md` §5). Profile tasks run one at a time and only when no scan is in flight, so photo scans (demo step 2) never wait for them.

## 4. Data model and contract changes
Everything here is **additive**. Nothing is renamed, removed or retyped.

### 4.1 Data model (`PLAN.md` §6 style; A writes the migration, C reads and writes the rows)
| Table | Columns | Notes |
|---|---|---|
| `users` (changed) | + `match_suggestions` bool default false | The opt-in. Demo users are seeded with `true` |
| `user_profiles` (C) | PK `user_id` FK, `summary` text null, `lends` JSONB default `[]` (categories), `borrows` JSONB default `[]`, `signal_count` int, `source` (rules\|ai), `model` null, `prompt_version` null, `input_hash` null, `cost_usd` float null, `latency_ms` null, `updated_at` | One row per opted-in person. Deleted when they opt out |
| `user_needs` (C) | `user_id` FK, `name`, `category` null, `source` (search\|predicted), `confidence` float, `embedding VECTOR(384)` null, `expires_at` | Needs that are not open requests. ≤ 8 per person; search needs expire after 14 days, predicted needs after 7. Index on (`user_id`), HNSW on `embedding` |
| `mutual_matches` (C) | PK(`user_a_id`, `user_b_id`) with `user_a_id < user_b_id`, `score` float, `a_gives` JSONB, `b_gives` JSONB (each a list of `{item_id, need_kind, request_id, need_name, score}`), `reason` text, `uses_prediction` bool, `a_state` / `b_state` (new\|seen\|dismissed\|contacted), `notified_at` null, `updated_at` | Full version only. The hackathon version computes pairs on read and stores nothing |

The hackathon version needs **only the first row** (`users.match_suggestions`), and can ship without it by treating demo users as opted in (§9a, cut list).

### 4.2 Contract changes (`PLAN.md` §7) — ⚠ contract change, additive
New and changed types (§7.2):
```ts
export type NotificationType = /* existing */ | "mutual_match";          // CHANGED (additive, full version)
export interface Me { /* existing */ match_suggestions: boolean }         // CHANGED (additive)
export interface MeUpdate { /* existing */ match_suggestions?: boolean }  // CHANGED (additive)

// ---------- mutual matching ----------
export interface MutualNeed {
  kind: "request" | "search" | "predicted";  // "search" and "predicted" are guesses: word them as "might need"
  name: string;                    // e.g. "tripod"
  request: RequestCard | null;     // set when kind = "request"
}
export interface MutualLink { item: ItemCard; need: MutualNeed; score: number }  // this item answers that need
export interface MutualMatch {
  user: UserRef;                   // the other person
  you_give: MutualLink[];          // my items they need (≥ 1, ≤ 3)
  you_get: MutualLink[];           // their items I need (≥ 1, ≤ 3)
  score: number;                   // 0..1
  reason: string;                  // e.g. "Same dorm · you both asked this week"
  uses_prediction: boolean;        // true if any link is a guess
}
export interface MutualMatchesResponse { enabled: boolean; matches: MutualMatch[] }   // ≤ 10; enabled = my opt-in
export interface MatchProfile {    // what DAHA has learned about me (shown only to me)
  enabled: boolean; summary: string | null;
  lends: Category[]; borrows: Category[];
  likely_needs: { name: string; category: Category | null; source: "search" | "predicted" }[];
  source: "rules" | "ai" | "none"; updated_at: ISODateTime | null;
}
```
New endpoints (§7.3):
| Owner | Method & path | Body / query | Response | Notes |
|---|---|---|---|---|
| C | `GET /me/mutual-matches` | | `MutualMatchesResponse` | 404 when `MUTUAL_MATCHING=off` (the web hides the card). Only pairs where both people opted in and both directions are visible |
| C | `POST /me/mutual-matches/{user_id}/dismiss` | | 204 | Full version. That pair is never shown or notified to me again |
| C | `GET /me/match-profile` | | `MatchProfile` | Full version. Transparency: exactly what was inferred |
| C | `DELETE /me/match-profile` | | 204 | Full version. Deletes the profile and predicted needs, and turns `match_suggestions` off |

Notifications (§7.5), full version:
| Type | Recipient | Trigger | Link |
|---|---|---|---|
| `mutual_match` | both people in a new pair | the mutual matcher; ≤ 1 per person per 24 h, ≤ 3 per 7 days, never twice for the same pair | `/requests/{id}` when there is a request to answer, else `/u/{user_id}` |

Events (§7.6): `mutual_match_shown` (`{count, uses_prediction}`), `mutual_match_clicked` (`{rank, action}`), `mutual_match_dismissed`, `match_suggestions_changed` (`{enabled}`). Counts and kinds only, no free text.

New settings (`backend/.env.example`, `PLAN.md` §5.3): `MUTUAL_MATCHING=off` (off \| rules \| ai), `MUTUAL_BUDGET_USD=3`, `HARNESSROUTER_PROFILE_HARNESS_ID=`, `MUTUAL_EST_COST_PER_PROFILE=0.05`.

## 5. Matching logic
**Signals**
| Signal | Source | Used as | Weight |
|---|---|---|---|
| Open request | `requests` + `request_matches` | need | 1.0 |
| Search with 0 results, or results and no click, in the last 14 days | `search_logs` + `search_result_clicked` events | need (a guess) | 0.6 |
| Predicted need | profile agent | need (a guess) | 0.4 × the agent's confidence |
| Available item the other person can see | `items` | have | — |
| Same dorm, walking minutes | `scoring.proximity()` (dorm-level) | boost | as in C3 |
| Lender reliability: completed loans, rating | `transactions`, `reviews` | boost, full version | small |
| Dismissed pair, or the pair already has an open transaction | `mutual_matches`, `transactions` | exclude | — |

**Scoring**
1. **Direction score** `d(A→B)` = the best of (need weight × the C3 relevance of A's item for B's need), using `score_items()` and `MATCH_MIN_SCORE` unchanged.
2. **Pair score** = √(`d(A→B)` × `d(B→A)`) × (0.8 + 0.2 × proximity). A geometric mean, so one strong side can't carry a weak one.
3. Keep a pair only if **both** directions pass the threshold.

**Ranking:** request ↔ request pairs first, then pairs with one guess, then pairs with two guesses (full version only); inside each group by pair score, same dorm first. At most 3 pairs on Home, 10 in the list, 3 links per side.

**Cold start (most users today)**
| Tier | Who | What they get | AI |
|---|---|---|---|
| 0 | no items and no requests | nothing mutual is possible. The card says "List 3 things to get matched" and links to the scan and to "Tick what you have" (C5) | none |
| 1 | fewer than 3 signals | strict pairs from requests and searches only | none |
| 2 | 3 or more signals, opted in | the above plus predicted needs from the profile agent | 1 task when activity changes |
| Fallback | no pair found | the existing "You could help" list. No empty card | none |

A "signal" is one listed item, request, search, or completed transaction. The seed gives every demo user enough signals for tier 2; a new real user starts at tier 0 or 1.

**How often it runs**
- Strict pairs: on every read (cheap).
- Profile agent: at most once per person per 24 h, only if the input hash changed, only for tier 2. The full version batches 8 anonymous people per task.
- Predicted-need scoring: when a profile changes and when a new item is saved.

**Notification caps**
- `mutual_match`: ≤ 1 per person per 24 h, ≤ 3 per 7 days, once per pair, and only for pairs with at least one real request.
- Guess-only pairs are never notified; they only appear on Home.
- A mutual notification replaces the plain `match` notification for the same request, so nobody gets two for one event.
- Seeded requests stay silent, as today.

## 6. Privacy and safety
**What is inferred and stored**
- Per opted-in person: the categories they lend and borrow, one summary line, up to 5 predicted needs, and bookkeeping (hash, cost, time). No raw searches are copied; `search_logs` stays as it is.
- Shown only to that person, in `GET /me/match-profile`. Another person sees a predicted need only as one item-level line ("Sam might need a tripod") inside a pair, never the profile.

**Opt-in and opt-out**
- Off by default for real users. A Home card asks once: "Get matched with neighbors you can trade favors with? DAHA looks at what you list, ask for and search." Demo users are on.
- A pair needs **both** people on. Turning it off deletes the profile and predicted needs and removes the person from every pair at once.
- Per pair: "Not interested" (dismiss).

**Keeping the dorm-level promise**
- Only dorm coordinates and walking minutes, exactly as C3 does. The phone location from `plans/LOCATION.md` is for store search only and is not used here.
- Visibility is checked in both directions with A's `item_visible_clause` and `user_can_view_request`. A pair never reveals an item or request the viewer couldn't already open.
- **Private "I have this" items** (C5): they count only on their owner's own screen ("you have a bike pump Jordan needs"). The other person sees that pair only if it is still mutual without the private item. Otherwise they see nothing until the owner offers. The hackathon version uses public items only.

**What never leaves the server**
- Names, emails, user ids, dorm names, group names, photos, messages, reviews, pickup notes, other people's text, private item names, and who is matched with whom.

**What HarnessRouter receives**
- One JSON per person, labeled with a random token for that run: counts per category (listed, lent, borrowed, requested), the names of their own public items, their own request titles, and their own recent search words after the C6 cleaner (`commercial.search_words()` strips emails, phone numbers and links).
- The harness has no tools, no web, no files, `max_step` 3, and a per-task cost cap of a few cents.
- The answer is treated as untrusted: parsed, clamped to our categories, run through the sensitive-item rules in `normalize.py` (no IDs, cards, keys, cash, documents, meds or hygiene items as "needs"), cut to 5 needs, and dropped entirely if it doesn't validate after one repair turn.
- Predicted needs are never shown as facts, never posted as requests, and never notified on their own.

## 7. Cost
**Sources for every number**
| Number | Value | Source |
|---|---|---|
| Team credit | $50 | `AGENTS.md` §7 |
| Hard stop for photo scans | $40 (`AI_BUDGET_USD`), which "keeps $10 of $50 for evals" | `backend/.env.example` |
| Thursday mini-eval | ≤ $3 | `plans/EVALS.md` |
| One photo scan | $0.10, an **estimate**: the API returns no cost | `docs/ai-spike.md`; confirmed on 2026-11-18 (2 scans, 13.3 s and 19.2 s, cost recorded from the estimate) |
| Agent time | $0.020 per active minute with no plan | `docs/research/harnessrouter-workflows.md` §5 (pricing page, 2026-11-17) |
| Model tokens | claude-sonnet-5.5 at $2 / $10 per million input / output tokens, no markup | same |
| A short task with no tools | about $0.01–0.05 (planning range, unverified) | same |
| Tasks at once | 2 per organization on the free plan | same |

**Estimate for one profile task (to be measured in H0, not a fact):** about 15 s of agent time ≈ $0.005; about 15,000 input tokens (the base's own instructions plus ours and the JSON) ≈ $0.03; about 400 output tokens ≈ $0.004. Total **≈ $0.04**; plan with **$0.05**.

**Per user per day**
| Case | Cost per opted-in user per day |
|---|---|
| Tier 0–1 (most real users now) | **$0** |
| Tier 2, worst case: activity changes every day | $0.05 |
| Tier 2, expected: 2 changes a week | about $0.015 |
| Tier 2, full version, 8 people per task | about $0.002–0.006 |

**Against the budget**
- Hackathon: 30 demo users + up to 10 testers, one profile each, refreshed at most once more before the demo → at most 80 tasks × $0.05 = **$4 worst case**. The plan caps it at **`MUTUAL_BUDGET_USD=3`**, taken out of the $40 (scans keep $37 ≈ 370 photos).
- After the hackathon, 100 daily users unbatched and at the worst case would cost $5 a day, which the credit can't carry. Batching, change-only refreshes and a weekly floor bring it to about $0.20–0.60 a day.

**How we stay under it**
1. Rules first: strict pairs and tiers 0–1 never call the agent.
2. Hash check: no change, no call. One call per person per 24 h at most.
3. Its own budget line, summed from `user_profiles.cost_usd`, with in-flight tasks counted, as scans do.
4. A per-task cost cap on the harness (`max_cost_usd` 0.05) and `max_step` 3.
5. When the budget is reached, or `MUTUAL_MATCHING=rules`, the feature keeps working without predictions.
6. Real spend is only visible on the HarnessRouter dashboard, because the API reports no cost. A human checks it after H0 and after H4.

## 8. 🧑 Human TODOs and design points
**Human TODOs**
- [ ] **C:** say OK for the H0 measurement (3 tasks, about $0.15) and for the demo run (≤ $3). `AGENTS.md` allows paid runs only with C's OK.
- [ ] **Key holder:** after H0, open the HarnessRouter dashboard and read the real cost of the 3 tasks. Tell A's agent, so `MUTUAL_EST_COST_PER_PROFILE` is a measured number.
- [ ] **Key holder:** check how much credit each of the two organizations has left. The $50 is in one of them.
- [ ] **Whoever registered the harness ids with the hackathon organizers:** add the new profile harness ids, so its usage is counted.
- [ ] **B and C:** 👍 on each PR that touches your files.
- [ ] **Everyone, Thu 08:30:** a two-phone pass of the new Home card.
- [ ] **After the hackathon:** agree on the consent wording with all three humans before real students see it.

**Design points (involved mode; the defaults are what gets built in hands-off mode)**
| Point | Default | Alternative |
|---|---|---|
| Definition | reciprocal + both opted in (§1) | habit recommendations without reciprocity |
| Opt-in | off for real users, asked once on Home | on by default with an opt-out |
| Guess-only pairs | shown on Home, never notified, full version only | never shown |
| Notification cap | 1 a day, 3 a week | 1 a week |
| Private items | owner's side only | left out completely |
| Where it shows | a card on Home above "You could help" | its own tab |
| Card title | "You two can help each other" | "Trade favors" |
| Agent model | the harness default (claude-code base), measured in H0 | a cheaper base for strict JSON, after a comparison |

## 9. Milestones

### (a) Hackathon version — demo-ready by **Thu 09:30**, 2 hours before the 11:30 freeze
It is Wed 20:30 now. That leaves about 13 hours on the clock for about 9 hours of building; the agent can build overnight, but reviews and phone checks need awake humans.

**What the demo shows:** Maya opens Home and sees "You and Jordan can help each other: you have the tripod Jordan asked for, and Jordan has the steamer you need", plus one AI line: "Looks like you often borrow kitchen things. You might need a blender soon; Sam lends one."

| Id | What | Owner (path) | Hours | Done by |
|---|---|---|---|---|
| **H0** | Measure before building: count reciprocal pairs in the seed (one SQL query, free); run 3 profile tasks with a draft prompt and read latency, validity and cost (about $0.15, needs C's OK) | C | 0.5 | Wed 21:30 |
| **H1** | `MUTUAL_MATCHING` flag (default `off`); new `backend/app/discovery/mutual.py` with strict pairs from `request_matches`; `GET /me/mutual-matches`; tests; types added to `PLAN.md` §7 | C + A (schemas, config) | 2 | Wed 23:30 |
| **H2** | Seed: 3 reciprocal demo pairs (requests on both sides) and `match_suggestions=true` for demo users; migration for `users.match_suggestions` | A | 1 | Thu 00:30 |
| **H3** | Home card (≤ 3 pairs, "Offer" and "Message" buttons that use the existing flows), hidden on 404 or an empty list; opt-in card; `types.ts`; mock; events | B | 2.5 | Thu 03:00 |
| **H4** | Profile agent: prompt, harness created by `setup_harnessrouter.py`, validation, cache, budget line; profiles for the demo users generated **once, ahead of the demo**; predicted needs kept in `ai_cache` (no new tables); one "might need" line on the card | C | 2.5 | Thu 06:00 |
| **H5** | Mini-eval and safety net: the checks in §10 on the seed, the full test suites, a flag-off run of `make smoke`, and a new optional step in the demo script | C + A | 0.5 | Thu 07:00 |
| — | Buffer, reviews, two-phone pass, deploy | all | 2.5 | **Thu 09:30** |

Checkpoint messages:
- H1 + H2: *"Mutual matching, server part ✅ behind MUTUAL_MATCHING (off by default). GET /api/me/mutual-matches is live when it's on. B and C: please 👍 the PR."*
- H3: *"Mutual matching card ✅ on Home. Set MUTUAL_MATCHING=rules in backend/.env and re-seed (make seed) to see 3 demo pairs."*
- H4: *"Mutual matching AI profiles ✅ (MUTUAL_MATCHING=ai). Demo profiles are cached, so the demo makes no paid calls. Spent so far: $X of the $3 line."*

**Keeping the demo safe**
- **One switch:** `MUTUAL_MATCHING=off` makes the endpoint answer 404 and the web hide the card. The code default is `off`, so tests, CI and anyone who hasn't changed `backend/.env` see no difference.
- **Nothing live is edited.** H1–H4 add new files and one new endpoint. `matching.py`, `feeds.py` and `hooks.py` are read, not changed, and `request_matches` is only read. The one place that would touch live matching code is the `mutual_match` notification inside `matching.py::_match`; it is **not** in the hackathon version.
- **No paid call during the demo:** profiles are generated ahead and cached. If HarnessRouter is slow or down, the card still shows the strict pairs.
- **The migration is one nullable-safe column** with a default. If it worries anyone, H2 can skip it (cut list).
- **Go / no-go at Thu 08:30:** if the card isn't solid on two phones, set the flag to `off` for the demo and mention the feature as "built, behind a flag".

**If behind, cut** (in this order):
1. H4's AI line on the card (keep the profile task as a recorded result in the write-up).
2. H4 entirely: ship `MUTUAL_MATCHING=rules`, with search-based needs as the "habit" part.
3. The opt-in card and the migration: demo users count as opted in, real users see nothing.
4. The "Message" button (keep "Offer").
5. H3: show the pairs through the endpoint only and describe it in the pitch.
Never cut: H0, the flag, the tests in H1.

### (b) Full version — after the hackathon
| Id | What | Owner | Effort | Checkpoint message |
|---|---|---|---|---|
| **F1** | Tables `user_profiles`, `user_needs`, `mutual_matches`; pairs stored, with states and dismiss; `GET`/`DELETE /me/match-profile`; settings screen "What DAHA learned about you" | A (migration, schemas), C (logic), B (screens) | 3 days | *"F1 ✅ mutual matches are stored; dismiss and 'what DAHA learned' are live."* |
| **F2** | The generic task runner (`app/ai/harness_tasks.py`, `docs/research/harnessrouter-workflows.md` §4): vision and profile on one runner; 8 people per task; `make match-profiles` + a nightly cron on the VM | C, A (cron) | 3 days | *"F2 ✅ one HarnessRouter runner for scans and profiles; profiles refresh nightly."* |
| **F3** | Needs from searches; predicted-need scoring in `on_item_saved`; `mutual_match` notifications with the caps in §5 (this is the change inside `matching.py`) | C, B (notification row) | 2 days | *"F3 ✅ mutual_match notifications live (≤ 1 a day). B: new notification type."* |
| **F4** | Private items on the owner's side; reliability boost from transactions and reviews | C | 2 days | *"F4 ✅ private haves count for their owner; reliable lenders rank higher."* |
| **F5** | Evals suite `mutual` and the online metrics in §10; consent wording agreed by all three humans | C, all | 2 days | *"F5 ✅ mutual eval suite + report committed."* |
| **F6** | Learn the weights from outcomes (`plans/ROADMAP.md` #2), choose whom to notify with a bandit (#3), prompt "you probably have this" from predicted haves (#4) | C | after 4 weeks of real usage | — |

**If behind, cut** (full version): F4, then batching in F2, then guess-only pairs.

## 10. Testing and evals
**Automated tests** (`backend/tests/discovery/test_mutual.py`, no paid calls; HarnessRouter mocked with respx as in `tests/ai/test_harnessrouter.py`)
- A pair appears only when both directions pass; a one-way match never does.
- Both people must be opted in; turning it off removes the pair for both.
- Visibility in both directions: a dorm-only item or request never creates a pair across dorms; private items never appear to the other person.
- Flag `off` → 404; flag `rules` → no HarnessRouter call is attempted.
- What leaves the server: the profile payload contains no name, email, id, dorm name or private item name.
- Bad agent output (not JSON, unknown category, a sensitive "need", 20 needs) is repaired once, then dropped.
- Budget reached → no call, and the endpoint still answers.
- Web: `pnpm lint && pnpm typecheck && pnpm build`; the Playwright smoke test stays green with the flag off.

**Evals** (`plans/EVALS.md` style; new suite `evals.run mutual`, on the seeded database)
```
evals/data/mutual/pairs.jsonl     {"user_seed_key","expected_partner_seed_keys":[...]}
evals/data/mutual/profiles.jsonl  {"user_seed_key","expected_needs":[...],"must_not":[...]}   (full version)
```
| Suite | How it's scored | Target |
|---|---|---|
| **Mutual pairs** | precision@3 and recall@3 against the expected partners | precision ≥ 0.80, recall ≥ 0.80 |
| **Validity** | share of shown pairs where both directions pass the threshold and both visibility checks | 1.00 |
| **Privacy** | pairs that include a person who is opted out, or that show another person's private item | 0 |
| **Profile agent** | valid JSON rate; sensitive needs after validation; p50 seconds; $ per profile | valid ≥ 0.95, sensitive 0, p50 ≤ 30 s, ≤ $0.05 |
| **Predicted needs** (full version) | share of predicted needs the person later searched or asked for within 14 days | ≥ 0.20 to keep the feature on |
| **Speed** | p95 of `GET /me/mutual-matches` | < 300 ms |

**Online metrics** (from `events`, added to `evals/online_metrics.sql`)
- opt-in rate, and opt-out rate after the first notification
- card click-through; pairs that lead to an offer or a message within 48 h
- completed transactions that started from a mutual pair, compared with one-way matches
- notifications per completed exchange
- dismiss rate, split by strict pairs and pairs with a guess

**Success for the hackathon:** the demo pair shows on two phones, validity 1.00, privacy 0, and a measured cost per profile in the write-up.

## 11. Done when
**Hackathon version**
1. With `MUTUAL_MATCHING=rules` or `ai`, Maya's Home shows a pair where each side has something the other asked for, and tapping "Offer" lands in the existing offer flow.
2. A person who hasn't turned matching on appears in nobody's pairs.
3. No pair shows an item or request its viewer couldn't already open, and no private item of another person.
4. With `MUTUAL_MATCHING=off`, the app behaves exactly as before: all tests and `make smoke` pass.
5. The profile agent has run on the demo users, the cost per profile is measured, and the total is under `MUTUAL_BUDGET_USD`.
6. The demo makes no paid call.
7. The checks pass: `uv run ruff check . && uv run pytest -q` and `pnpm lint && pnpm typecheck && pnpm build`.

**Full version**
8. People can see and delete what DAHA learned about them, and dismiss a pair.
9. `mutual_match` notifications respect the caps, and nobody gets two notifications for one request.
10. The `mutual` eval report is committed and meets the targets in §10.
11. Daily HarnessRouter spend for profiles stays under its budget line with 100 active users.

## 12. Risks and later
**Risks**
| Risk | Why it matters | What we do |
|---|---|---|
| **Too few pairs** | Reciprocal matches are rare with little data; most real users are at tier 0–1 | H0 measures it first; needs from searches and predictions widen it; seeded demo pairs; an honest empty state that points to "You could help" |
| **Privacy and trust** | Inferring habits and sending activity to an outside service can feel creepy, and it is new for DAHA | Off by default, both sides opt in, a "what DAHA learned" page with delete, anonymous payload, no names or other people's text, guesses always worded as guesses |
| **Deadline and demo safety** | About 13 hours to the 09:30 target, the night included; a regression would hurt the core demo | New files only, flag off by default, a go / no-go at 08:30, a cut list |
| **Unknown real cost** | The API reports no cost; every figure is an estimate | Measure in H0, a separate $3 line, a per-task cap, a dashboard check by a human |
| **Slow or busy HarnessRouter** | 15–20 s per task, 2 tasks at a time, shared with scans | Background only, scans first, cached profiles, the rules path as a fallback |
| **Wrong or unsafe predictions** | The agent may invent needs or suggest sensitive items | Validation, sensitive-item rules, low weight, never notified alone |
| **Instructions hidden in text** | A person's item name or search could say "ignore your rules" | No tools, strict output validation, and the output only ever becomes a weak, labeled suggestion |
| **Notification fatigue** | A new notification type adds noise | Not in the hackathon version; strict caps; replaces the plain match notification |

**Deviations from existing plans**
- `plans/ROADMAP.md` says to wait for 4 weeks of real usage before ML work. This starts earlier, so the learning part is deliberately thin (a summary and a few guesses) and the matching stays rule-based.
- `docs/decisions.md` (2026-11-16): "HarnessRouter for vision only" and "paid AI reserved for photos". This adds a second paid use, which is why it has a proposal and its own budget line.
- `AGENTS.md` §3: only C runs real HarnessRouter calls. Here A's agent runs them, with C's OK per run.

**Later (not in this plan)**
- **An agent with DAHA tools over MCP** (`plans/ROADMAP.md` #7, `docs/research/harnessrouter-workflows.md` §3.6): the agent proposes an exchange spot and time and drafts the first message. It needs a hosted `/mcp` endpoint and per-user tokens.
- **Three-way swaps** (A helps B, B helps C, C helps A).
- **Learning-to-rank and bandits** for pairs (`plans/ROADMAP.md` #2 and #3), once there are outcomes to learn from.
- **Group and class matching** ("your lab group has 4 things you need").
- **A cheaper or local model** for profiles, if the evals show the summary doesn't need a large one.

## 13. What was built and measured (2026-11-18)
**H0, measured before building**
- The seed had **0 reciprocal pairs** (14 match rows, 12 one-way pairs, 0 search logs). So the seed now has 3 two-way demo pairs and one pair that uses a guess.
- Profile tasks: **30 run, 30 valid** on the first answer, **8–12 s each** (median about 9 s). The API reported **no cost** for any of them, so the $0.05 per profile is still the estimate; by that estimate $1.50 of the $3 line is used. The real figure is on the HarnessRouter dashboard.

**Built** (new files; `matching.py`, `feeds.py` and `hooks.py` are unchanged)
- `backend/app/discovery/mutual.py`, `GET /api/me/mutual-matches` (404 when off), `users.match_suggestions` (migration 0002), `Me` / `MeUpdate`.
- `backend/app/ai/profile.py`, `scripts/setup_harnessrouter.py --profile`, `scripts/mutual_profiles.py`.
- Web: `web/src/components/daha/mutual-matches.tsx` on Home (opt-in card, pair cards, "what DAHA noticed" line, Turn off).
- Evals: `evals.run mutual` with `evals/data/mutual/pairs.jsonl`.

**Results on the seed** (`evals/reports/2026-11-18-mutual.md`): precision@3 1.00, recall@3 1.00, validity 1.00, privacy leaks 0, p95 53 ms. The expected pairs were written by the same person who seeded them, so this is a regression check, not an independent quality measure. Match and search evals are unchanged (recall@5 1.00, nDCG@10 0.94).

**Deviations from the plan above**
- `MutualMatchesResponse` also carries `summary` and `likely_needs` (the person's own profile, shown only to them). The separate `GET /me/match-profile` stays in the full version.
- Demo profiles are saved in `backend/app/seed/data/mutual_profiles.json` and loaded by the seed, so a reseed costs nothing and the demo makes no paid call. Demo users' profiles are never re-bought.
- A person gets at most 2 paid profile runs per 24 h, so turning matching off and on can't burn credit.
- The profile harness's per-task cap is $0.15, not $0.05, because the real cost per task isn't known yet.
- Needs from searches (weight 0.6 in §5) are sent to the profile agent but are not yet matched directly; that stays in F3.
- Predicted needs live in `ai_cache` and paid runs are counted from `mutual_profile_run` events (no new tables, as planned for this version). **A reseed with `--reset` clears that counter**, so the dashboard is the only durable record of spend.
- No "Message" button: the card has "Offer yours" (the existing offer flow) and "Ask for theirs" (the item page).

# Research: more HarnessRouter workflows for DAHA

- Date: 2026-11-17 · Author: Andre (with Claude) · Status: research, nothing here is built yet
- Sources: HarnessRouter's docs (`harnessrouter.ai/docs/*`, read in their raw Markdown form), the live OpenAPI document and `GET /v1/uhp`, the pricing pages, the Terms (v1.1, 2026-07-31), HarnessRouter's official coding-agent Skill, and the community site. Links are in the appendix. Facts marked *(docs)* are quoted or closely paraphrased from those pages; everything else is our design.

## TL;DR: what to do next
| # | Workflow | Value for students | Effort | Cost per use (est.) | When |
|---|---|---|---|---|---|
| 1 | **Finish the C0 spike as an Arena run**: 3 real photos × 2–3 base/model configs side by side | Picks the scan model with real numbers; unblocks `AI_PROVIDER=harnessrouter` | 1–2 h | ~$0.30–1 total | Now |
| 2 | **Autofill a manual listing from one photo** (P1 #2) | "List one item" becomes snap → check → post | ½ day | ≈ one scan photo | Now / week 1 |
| 3 | **Safety review of new listings and requests** (photo + text) | Keeps weapons, drugs, IDs and faces off a school-wide app | 1 day | ≈ one short task per listing; skip text-only items that pass rules | Week 1 |
| 4 | **Course booklist → borrow before you buy** (document reading) | Upload a syllabus or booklist PDF; DAHA lists the books and calculators on it, shows who on campus has them, and drafts requests for the rest | 1–2 days | one short task per document | Week 1–2 (before next quarter) |
| 5 | **Request enrichment** (P1 #3, `AI_ENRICH_REQUESTS`) | Better matches for messy requests ("thing for my hair, the hot one") | 1 day | small task, only when the rule parser is unsure | Week 1–2 |
| 6 | **"Nobody has it yet" concierge** | A dead-end request gets a plan: widen the audience, similar items, campus resources, and C6 store prices | 1–2 days | one task per unmatched request | Week 2 |
| 7 | **Campus assistant over MCP** (`plans/ROADMAP.md` #7), started from the Harness Bot starter kit | "Ask DAHA" in the app, later in dorm group chats | 1–2 weeks | per conversation turn | After real usage |

Quick win for the submission: the **Slides** and **Videos** starter kits can draft the pitch deck and a short demo clip (§3.13).

The common thread is one reusable **harness task runner** (§4) built from what the vision scan already does: background job, key pool, budget, cache, JSON validation, repair turn. Every new workflow becomes a prompt, a schema and a trigger.

## 1. What HarnessRouter is, in one paragraph
HarnessRouter runs full **agent harnesses** (Claude Code, Codex, Gemini CLI, OpenCode, Pi and more; 16 bases are served today *(docs)*, and the live list is per organization via `GET /v1/bases`) behind one OpenAI-Responses-style API. It is not a single-shot model API: a task gets its own sandbox, can read the files you upload, use tools and MCP servers, and write files back. Tasks take tens of seconds to minutes, so every DAHA workflow on it must be **asynchronous**: start the task in the background, show progress, poll, then let the user confirm.

## 2. Capabilities that matter for DAHA
| Capability | What the docs say | How DAHA could use it |
|---|---|---|
| Files in | `POST /v1/files`, up to 25 MiB per file; the file lands in the agent's working directory. **A file id belongs to the key that uploaded it** (*"Any other key that names it gets 404"*) | Photos for scans, autofill and safety review; CSV exports for offline analysis |
| Files out | The task's working folder is listed by `GET /v1/sessions/{id}/files`, downloadable as a zip | An agent writes `result.json`, `prompt_v2.md` or a labeling sheet instead of answering in chat |
| Sessions | Continue with `previous_response_id`; `branch: true` to fork; import up to 20 earlier messages | Repair turns (as today); multi-step concierge; an assistant conversation |
| Run modes | Stream, `background: true` (returns at once, then poll `GET /v1/responses/{id}`), or blocking | Background for anything user-facing; streaming only for the assistant chat |
| Budgets | Per-turn `max_step`, `timeout_seconds`, `max_cost_usd` (defaults 400 steps, 7200 s, **$10**), on the harness or per request | Set them low on every harness: a runaway task must cost cents, not $10 |
| MCP servers | `{"name", "url", "auth": "<ref from PUT /v1/mcp-secrets>"}`, Streamable HTTP or SSE. Per-user headers: `"headers": {"x-user": "$headers.X-End-User"}`, declared in `additional_headers`. An unreachable server must not fail the task | Expose DAHA's own API to an agent, acting as one user at a time (§3.6) |
| Skills and plugins | A skill is a folder with `SKILL.md`; plugins bundle skills and MCP config (up to 16 MiB). claude-code preloads document skills (docx, pdf, pptx, xlsx) | Ship DAHA's rules (categories, safety list, tone) as one skill reused by every harness |
| Tool control | `disabled_tools`, with per-base enforcement: `hard` (denied by the runtime) or `instruction` (*"An instruction is not a boundary"*) | Untrusted input (user photos and text) only goes to harnesses where risky tools are hard-disabled |
| Env and secrets | `env` up to 64 variables; secret references; *"Values do not reach the model"* | Pass an MCP token or a feature flag without putting it in the prompt |
| Environments | A read-only project folder with pip, npm and apt packages, built in up to 30 min | A Python environment with our categories and validators for offline jobs |
| Browser and tools | Cloud browser at $0.02 per browser hour; on-demand scrapers, search and enrichment tools priced per run; media generation (images, video, speech) | Campus resource lookups for the concierge; not needed for core flows |
| Publish to chat | A harness can be published to Telegram, Slack or WhatsApp (*"Two turns per chat and five per bot"*) | Later: a DAHA bot in dorm group chats (opt-in, mention-only) |
| Arena | Groups up to 10 tasks for side-by-side comparison | The C0 spike and every prompt change: same photo, several configs |
| Observability | Traces API (beta, add-on below the Scale plan); `GET /v1/balance` for remaining credit; workspace event stream (`GET /v1/events`) with task start/end frames; session `spend_usd` and response `usage` | Budget dashboard, cost per workflow, alerts before credit runs out |

### 2.1 HarnessRouter's six headline uses, mapped to DAHA
| What HarnessRouter offers *(docs)* | DAHA idea | Section |
|---|---|---|
| **Read documents and pull out information**: upload a file (up to 25 MB) and ask for key fields, a summary, or a checklist ([upload-files](https://harnessrouter.ai/docs/upload-files)) | Course booklist / syllabus → the books and calculators needed → campus matches + requests for the rest. Also: a dorm's move-out checklist → giveaway listings | §3.12 |
| **Starter kits**: ready-made agent + web app combos you launch and edit: Slides, Sheets, Dashboards, Videos, Platform game, Harness Bot ([starter-kits](https://harnessrouter.ai/docs/starter-kits)) | Harness Bot as the starting point for the campus assistant; Dashboards for an ops view (AI spend, moderation queue, dorm activity); Slides and Videos for the hackathon pitch deck and demo clip | §3.13 |
| **Research and use websites**: web search, or a cloud browser that opens pages and clicks around, at $0.02 per browser hour ([browser](https://harnessrouter.ai/docs/browser)) | Find campus lending desks (libraries, tool libraries, rec center rentals) for the "nobody has it" concierge; double-check a store page's price and stock behind a C6 offer | §3.5 |
| **Work with your other apps**: connectors such as GitHub, Microsoft 365, Stripe, with actions you allow ([connectors](https://harnessrouter.ai/docs/connectors)) | Internal first: turn in-app feedback into labeled GitHub issues, and triage CI failures. Stripe stays out (no payments in DAHA, `PLAN.md` §2) | §3.14 |
| **Generate media**: images, 1–15 s video clips, speech, music, a short film up to 10 min ([media-tools](https://harnessrouter.ai/docs/media-tools)) | Move-out week posters, 10-second "how to scan your desk" clips for onboarding, the demo video. Never fake product photos on listings (§3.11) | §3.15 |
| **Run custom workflows**: an agent with its own instructions, skills, tools and limits ([harnesses-api](https://harnessrouter.ai/docs/harnesses-api)) | Every workflow here is one harness: vision, autofill, reviewer, enricher, concierge, assistant, each with its own prompt, tool list and cost cap, run by one task runner | §4 |

**What it doesn't have** *(docs)*: no JSON-schema / structured-output parameter (put the output contract in the prompt and validate, as `app/ai/normalize.py` does; the official Skill suggests the `dsh` base with `claude-sonnet-5.5` for strict-JSON jobs), no webhooks (poll, or listen to `GET /v1/events`), no built-in scheduling or cron, and the public roadmap is empty (*"Nothing on the roadmap yet."*).

## 3. Workflow catalog
Each entry: what students get, how it runs on HarnessRouter, where it plugs into DAHA, cost and effort, and the risks.

### 3.1 Finish the C0 spike as an Arena (now)
- **Why:** `docs/ai-spike.md` still says *"numbers pending the API key"*. Scans run on `mock` until a base/model is chosen.
- **How:** create one harness per candidate config (e.g. `claude-code` + the best Claude model listed, and one minimal base like `dsh` or `pi` with a vision model) with `scripts/setup_harnessrouter.py`, then run the same 3 photos through each. Arena groups the tasks so you can compare them in the console; `scripts/hr_spike.py` prints latency, JSON validity, item count and cost.
- **Pick:** the cheapest config with 3/3 valid JSON, sensible items and p50 ≤ 45 s (`plans/C-ai-discovery.md` → C0).
- **Cost:** a few tasks; the pricing page's worked example is $0.07–0.14 per task.

### 3.2 Autofill a listing from one photo (P1 #2)
- **Students get:** on `/add/item`, "Autofill from photo" fills name, category, description, condition and type from one picture; they fix and post.
- **How:** reuse the vision harness with a single-item task text ("the main item in this photo"), and return one `DetectedItemRaw`. Same upload → run → repair → `normalize.py` path as scans.
- **DAHA:** `POST /api/ai/autofill {upload_id}` → background job + poll (or a short blocking call with a spinner if p50 is low enough). C backend, B button.
- **Cost:** about one scan photo. Cached by image hash like scans (`ai_cache`).

### 3.3 Safety review of listings and requests
- **Students get:** a school-wide app without weapons, drugs, alcohol, prescription meds, IDs, or photos of people or documents.
- **How:** a background task after `POST /items`, scan publish and `POST /requests`. A "reviewer" harness gets the photo(s) plus the text and returns `{"verdict": "ok" | "hide" | "review", "reasons": [...]}`. `hide` → the item becomes `unavailable` and the owner gets a friendly note; `review` → a moderator queue.
- **Keep it cheap:** run rules first (a keyword list and the existing `normalize.py` drops); only send items with photos, or text that trips a rule, to the agent.
- **DAHA:** a hook next to `on_item_saved` / `on_request_created` (C), a `moderation` field or table (A, additive), a small admin view (B).
- **Risk:** false positives hide real listings, so use "review" for borderline cases, never silent deletion.

### 3.4 Request enrichment (P1 #3)
- **Students get:** messy requests still match: "the hot thing for my hair" → `item_name: "hair straightener"`, category `dorm`.
- **How:** only when `request_parser.py` reports low confidence (or no category), a background task returns a corrected `ParsedRequest` as JSON; we update the request (`ai_enriched=true`) and call `on_request_updated` to re-match. The flag `AI_ENRICH_REQUESTS` already exists but no code uses it yet.
- **Harness:** no tools, strict JSON, a small fast model; per-request `max_cost_usd` of a few cents.
- **Risk:** the request text is the student's own words. Send only the request text, never their name or dorm.

### 3.5 "Nobody has it yet" concierge
- **Students get:** instead of a dead end, a short plan under their request: *"No binders nearby yet. 2 people in Branner have similar ones (a 1.5" binder). Want to ask the whole campus? Green Library lends binders at the desk. Or buy one from $4 at the bookstore."*
- **How:** when matching finishes with 0 public matches, a background task gets the request plus a small JSON context we prepare (near-miss items from search with lower scores, the request's visibility, C6 store offers if any) and returns 1–3 suggestions with actions (`widen_to_campus`, `show_item`, `open_store_offer`). Optional: the browser or on-demand search tools to find campus lending desks, with results cached per item type.
- **DAHA:** C (hook after `on_request_created`), B (a suggestion card on `/requests/[id]` for the requester only).
- **Pairs with:** C6 "Buy or rent nearby" (Exa), whose offers are already cheapest-first and privacy-scrubbed.

### 3.6 Campus assistant over MCP (`plans/ROADMAP.md` #7)
- **Students get:** "Ask DAHA" in the app: *"I need a suit for an interview Thursday"* → it searches, shows options, offers to post a request, and drafts the message to a lender, asking before it does anything.
- **How:**
  1. We run an **MCP server** inside the API (Streamable HTTP, e.g. `/mcp`) exposing DAHA tools. Read-only first: `search_items`, `get_request`, `my_items`, `my_requests`. Writes later, each needing the user's tap in the UI: `create_request`, `offer_item`.
  2. The harness lists it: `mcp_servers: [{"name": "daha", "url": "https://<host>/mcp", "auth": "<secret ref>", "headers": {"x-user": "$headers.X-End-User"}}]`, with `additional_headers: ["X-End-User"]`.
  3. For each turn, our backend sends `X-End-User: <a 5-minute token signed for that user, scope "mcp">`. Our MCP server checks it and runs every tool through the normal visibility rules (`item_visible_clause`), so the agent can never see more than the student can.
- **UI:** a chat sheet with streaming text (the one place streaming helps). Sessions continue with `previous_response_id`.
- **Later:** publish the same harness to WhatsApp/Telegram for dorm group chats, mention-only and opt-in per dorm. Group messages aren't sent to the agent unless someone tags it.
- **Effort:** 1–2 weeks across A (tokens, MCP mount), C (tools, harness, prompts) and B (chat UI).
- **Risks:** prompt injection through listing text (an agent reading "ignore your rules"), so: read-only tools by default, every write confirmed by the user in our UI, and outputs validated. Our `/mcp` must be reachable by HarnessRouter (hosted, not localhost).

### 3.7 Declutter and move-out helper (`plans/C-ai-discovery.md` F2)
- **Students get:** at move-out, "Here are 14 things from your scans you haven't lent in 3 months: keep, share or give away?" plus ready-to-post giveaway listings with a pickup window.
- **How:** a background task gets the student's own item list (names, categories, last lent dates; no photos needed) and returns grouped suggestions plus drafted descriptions. One task per student per campaign.
- **DAHA:** needs F2's swipe flow (B) and bulk updates (A).

### 3.8 Evals and prompt improvement (`plans/EVALS.md`, `plans/ROADMAP.md` #1)
- **Draft eval labels:** an agent pre-labels the 20–30 eval photos (items, categories, quantities, sensitive flags) into `labels.csv` as a session file; a human only corrects. That cuts the ~1 hour labeling job.
- **Prompt v2 from real edits:** export `scan_detections.edits` (no photos, no names) as a CSV file, run one session that clusters the corrections ("users rename 'cup' to 'mug'", "chargers are often mis-tagged as other"), and write `prompt_v2.md` with new rules and few-shot examples. A human reviews, bumps `PROMPT_VERSION`, re-runs `evals.run scan`.
- **Judge for search:** grade the top-10 results of new queries for relevance, to grow `evals/data/search/queries.jsonl` faster. Use it as a draft, with humans checking a sample.
- **Cost:** a few tasks per run; nothing user-facing.

### 3.9 Savings and impact estimates (`plans/ROADMAP.md` #9)
- **Students get:** "You saved about $35 by borrowing this calculator", and dorm leaderboards of money saved.
- **How:** cheapest first: reuse C6's cheapest store price when a search already fetched one. Otherwise run a nightly batch task per *category + item name* (not per user) that estimates a typical new price from the agent's search tools, cached for months.

### 3.10 Weekly dorm digest
- **Students get:** one friendly post per dorm channel each week: what was shared, which requests are still open, who helped most (opt-in).
- **How:** our own scheduler (HarnessRouter has no cron) prepares the week's numbers as JSON; one short task per dorm writes the post. Pure text, no tools.

### 3.12 Course booklist → borrow before you buy (document reading)
- **Students get:** before a quarter starts, they upload a syllabus or bookstore booklist (PDF, photo or screenshot). DAHA answers: *"You need 4 things. On campus now: the TI-84 (2 in Wilbur) and 'Linear Algebra Done Right' (FloMo). Not listed yet: 2 books, want us to ask your dorm? Cheapest in stores: $38 (C6)."* One tap posts the requests.
- **How:** a "booklist reader" harness reads the uploaded file (HarnessRouter puts it in the agent's working directory) and returns `{"items": [{"title", "author", "edition", "isbn", "kind": "book" | "calculator" | "lab" | "other", "required": bool}]}`. We validate it, run each item through our own search (free) and C6 (cached), then show one review screen like the scan review: tick what to request, edit, post.
- **DAHA:** `POST /api/ai/booklist {upload_id}` → background job + poll (C); a "Got a booklist?" card on Home and `/add` (B). The upload endpoint accepts images today; PDFs need A to allow `application/pdf` (up to 25 MB on HarnessRouter's side).
- **Privacy:** syllabi can include instructor emails, office hours and student names in examples. Keep only the item fields, delete the uploaded file and session afterwards (`DELETE /v1/files/{id}`, `DELETE /v1/sessions/{id}`), and never show other students the document.
- **Cost:** one short task per document; it's worth more than a scan because it fills the most expensive academic gap.

### 3.13 Starter kits
- **Harness Bot** → the quickest path to the campus assistant (§3.6): launch it into our account, then swap its tools for DAHA's MCP server and our safety skill.
- **Dashboards** → a small ops page for the team: AI spend per workflow (from our run logs and `GET /v1/balance`), the moderation queue (§3.3), and weekly activity per dorm. Internal only.
- **Slides** and **Videos** → the hackathon pitch deck and a 15-second teaser from our screenshots and demo script (`plans/INTEGRATION.md` §3.2). Media renders on HarnessRouter's key are capped at $25 per task *(docs)*, so set a budget before generating video.
- Kits are launched into the account and edited there; anything that becomes part of DAHA still goes through a normal PR.

### 3.14 Connectors (internal tooling first)
- **GitHub:** a weekly task reads the `feedback_submitted` events (counts and our own categories, no free text from other students unless they agreed) and opens or updates labeled issues (`feedback` + `A`/`B`/`C`), matching the weekly loop in `plans/INTEGRATION.md`. Another task can explain a failing CI run on a PR.
- **Microsoft 365:** possible later for dorm staff (a weekly digest by email), only if a dorm asks.
- **Stripe:** not for DAHA. Payments and deposits are out of scope (`PLAN.md` §2).
- Connector actions must be ones we explicitly allow, and each connection stays inside its workspace *(docs)*.

### 3.15 Media for campaigns, not listings
- **Good uses:** posters and 10-second clips for move-out week ("give it away, don't throw it away"), onboarding clips that show how to scan a desk, the demo video.
- **Not:** generated photos of items people are lending (§3.11).

### 3.16 Not recommended (for now)
- **AI-written notification text per ping:** costs a task per notification for little gain; templates are fine.
- **Generated product images for text-only listings:** they look real but aren't, which is misleading on a lending app. Keep the category emoji tiles (media generation is fine for campaigns, §3.15).
- **An agent in dorm chats that reads every message:** a privacy problem. Only mention-triggered, opt-in versions (§3.6).
- **Using several HarnessRouter accounts to multiply free credit:** see §6.

## 4. One runner for every workflow
Today `app/ai/providers/harnessrouter.py` does upload → run (SSE) → JSON → repair for scans, with a load-balanced key pool. Generalize it once:

```text
app/ai/harness_tasks.py
  HARNESSES = {
    "vision":     HarnessSpec(prompt=VISION_SYSTEM, schema=DetectionPayload, max_cost_usd=0.5, ...),
    "autofill":   HarnessSpec(...), "review": HarnessSpec(...), "enrich": HarnessSpec(...),
  }
  async def run_task(name, *, text, files=(), schema, user_id=None) -> RunResult
      # key pool (several keys) → upload files with that key → run (background or stream)
      # → collect text → extract JSON → validate with the Pydantic schema → one repair turn
      # → budget check and cost logging → cache by (inputs hash, prompt version, model)
scripts/setup_harnessrouter.py  → creates/updates every harness in HARNESSES, per key
                                  (GET + If-Match/ETag; PUT is a full replace, so send every field)
```

Rules for every workflow:
- **Background by default.** Write a row (status `processing`), schedule the task, let the UI poll, mark stuck rows failed after a timeout, like `scans`.
- **A budget line per workflow** (e.g. `AI_BUDGET_USD_REVIEW`), summed from logged costs, next to the existing `AI_BUDGET_USD`. Read `GET /v1/balance` in a small admin view to see what's left.
- **Log every run** (workflow, response id, session id, key number, latency, cost, status): today that's `scan_images`, later a generic `ai_runs` table (A, additive). It's also the training data for `plans/ROADMAP.md`.
- **Idempotency:** a fresh `Idempotency-Key` per task, and the same key on transport retries (as the vision provider now does).
- **Clean up:** delete uploaded files and finished sessions we don't need (`DELETE /v1/files/{id}`, `DELETE /v1/sessions/{id}`). Free-plan records are kept 7 days; paid plans keep them for the life of the workspace *(docs)*.
- **Never send:** names, emails, dorm names with a person, free text from other people, photos with faces or documents (the scan prompt and `normalize.py` already enforce part of this).

## 5. Costs
*(docs, pricing pages, 2026-11-17)*
- **Agent work:** $0.020 per active minute with no plan; $0.014 on Developer ($20/month, includes $20 of usage); $0.010 on Production ($200/month); $0.006 on Scale. *"Waiting for a model response, waiting for you, waiting in a queue, and platform retries are Free wait time."*
- **Model tokens:** billed at the provider's price with no markup, e.g. claude-sonnet-5.5 at $2 / $10 per million input / output tokens.
- **Free plan:** one workspace and **two tasks at a time** during the 7-day trial; top-up credit removes the limit. A single task can run 30 minutes (1 hour after a top-up). Top-ups are $10 minimum plus a 5.5% fee.
- **Per-task cap:** $10 unless the harness or request sets `max_cost_usd`. Always set it.
- **Credit and limits are per organization**, so keys in one organization share both.

Rough per-use costs for planning (verify with the spike and the first week's logs): a photo scan or autofill ~$0.05–0.15; safety review or enrichment (short, no tools) ~$0.01–0.05; concierge ~$0.05–0.20 (more if it browses); one assistant turn ~$0.02–0.10. Our $50 credit with `AI_BUDGET_USD=40` covers roughly 300–800 scans, so the new workflows need their own budget lines before they ship.

## 6. Risks and rules
- **Several keys:** DAHA now load-balances across comma-separated keys (`HARNESSROUTER_API_KEY=a,b,c`). Keys in **one organization** share its credit and its task limit, so there they add failover, not capacity. The Terms (4.4(g)) forbid *"duplicate accounts"* and *"coordinated signups"* used to stretch free credit, trials or limits, so only use keys from accounts that are legitimately separate. `setup_harnessrouter.py --check` shows which organization each key belongs to.
- **Keys stay on the server** (Terms 3.4: *"API Keys must be kept server-side"*), as they already do.
- **Untrusted input:** listing text and photos can contain instructions. Hard-disable risky tools for those harnesses, give agents read-only tools, confirm every write in our UI, validate every output.
- **Latency:** tens of seconds per task. Only async UX; never block a page on a task.
- **Platform churn:** the OpenAPI document omits some documented routes (e.g. `/{harness_id}/v1/responses`); our client already falls back to `POST /v1/responses` with `metadata.harness_id`. Consider sending `UHP-Version: 2026-10-19` to pin the protocol version.
- **Hackathon accounting:** the Big Hack Game counts usage per Harness ID (*"Once it runs, add its Harness ID so its use is counted"*). With one harness per key, register every id in `HARNESSROUTER_VISION_HARNESS_ID`.

## 7. Phased plan
| Phase | Work | Owner |
|---|---|---|
| **Now (before the Thu 11:30 freeze)** | Run the C0 spike (Arena or `hr_spike.py`) with 3 real photos; pick a base/model; set `AI_PROVIDER=harnessrouter` for the demo; register the harness ids for the hackathon. Optional: draft the pitch deck and a teaser with the Slides/Videos starter kits (§3.13) | C + key holder; B for the video |
| **Week 1** | The task runner (§4) with the vision harness moved onto it; autofill from photo (§3.2); safety review on scans and listings (§3.3) | C (backend), B (button, notices), A (moderation field) |
| **Week 2** | Course booklist → borrow before you buy (§3.12), timed for the start of next quarter; request enrichment (§3.4); the "nobody has it" concierge using C6 offers and the browser (§3.5); per-workflow budgets and an ops dashboard (§3.13) | C, B, A (PDF uploads) |
| **After 4 weeks of real usage** | Prompt v2 from edits and eval auto-labels (§3.8); savings estimates (§3.9); weekly digest (§3.10); feedback → GitHub issues (§3.14) | C |
| **Later** | Campus assistant over MCP from the Harness Bot kit (§3.6), then opt-in chat bridges; move-out campaign media (§3.15) | A + B + C |

Each item starts as a proposal in `docs/proposals/` (`AGENTS.md` §6) with its own cost line before it's built.

## Appendix A: API cheat sheet *(docs)*
| Need | Call |
|---|---|
| Who is this key? | `GET /v1/me` → organization, workspace, member |
| What can we run? | `GET /v1/bases` (availability per organization), `GET /v1/models` (labels) |
| Make or update an agent | `POST /v1/harnesses`; `GET` (ETag) + `PUT` with `If-Match` (a full replace); pause with `PUT /v1/harnesses/{id}/pause` |
| Upload | `POST /v1/files` (25 MiB); `DELETE /v1/files/{id}` |
| Run | `POST /{harness_id}/v1/responses` or `POST /v1/responses` with `metadata.harness_id`; `stream` or `background`; `Idempotency-Key` header |
| Follow up | `previous_response_id` (+ `branch: true`) |
| Check or stop | `GET /v1/responses/{id}`; `POST /v1/responses/{id}/cancel` |
| Files the agent wrote | `GET /v1/sessions/{id}/files[?changed=true]`, `…/files/archive` |
| Money | `GET /v1/balance`; session `spend_usd`; response `usage` |
| Errors | 401 bad key · 402 no credit · 403 scope · 409 busy/paused/conflict · 429 rate-limited (`Retry-After`) · retry only network, 429, 502, 503, 504 |

## Appendix B: sources
- Docs: https://harnessrouter.ai/docs (pages read: workspace, api-keys, authentication, base-url, discovery-and-versions, harnesses-api, models, run-a-task, request-options, streaming-events, workspace-events, continue-a-session, branch-a-session, upload-files, sessions-and-files, read-a-response, errors-and-idempotency, deletion-and-retention, traces, plans-and-limits, usage, auto-top-up-and-receipts, files-and-artifacts, multi-tenant-authorization, environments, plugins, browser, media-tools, connectors, on-demand-tools, templates-and-snippets, harness-memory, publish-to-chat, arena, server-side-proxy-pattern, production-checklist, and more)
- API: https://api.harnessrouter.ai/v1/openapi.json · https://api.harnessrouter.ai/v1/uhp
- Pricing: https://harnessrouter.ai/pricing · Terms: https://harnessrouter.ai/legal/terms
- Official Skill and templates: https://github.com/HarnessRouter/plugins · protocol: https://github.com/HarnessRouter/harnessrouter, https://unifiedharnessprotocol.org/spec/security
- Community: https://community.harnessrouter.ai/roadmap · https://community.harnessrouter.ai/events/the-big-hack-game

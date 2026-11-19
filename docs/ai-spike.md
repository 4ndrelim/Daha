# HarnessRouter spike results (C0)

> **Status (2026-11-19): decided and live.** Photos run on `claude-code` / **`claude-opus-5.5` at
> low reasoning effort** (measured below). The app uses `AI_PROVIDER=harnessrouter`.

## How to run it (≈ 10 minutes, ≈ $0.30)
1. Put the Workspace key in `backend/.env` only: `HARNESSROUTER_API_KEY=sk-hr-…`. Several keys:
   comma-separated, no spaces (`sk-hr-aaa,sk-hr-bbb`). Check them (free):
   `cd backend && uv run python scripts/setup_harnessrouter.py --check`
2. See what's available (free): `cd backend && uv run python scripts/setup_harnessrouter.py --list`
3. Pick a base/model/effort: `HARNESSROUTER_BASE`, `HARNESSROUTER_MODEL` and
   `HARNESSROUTER_REASONING_EFFORT` in `backend/.env`. They are fixed when a harness is created
   (HarnessRouter can't edit one), so a change means running step 4 again: new ids.
4. Create the harness (free; one per key): `uv run python scripts/setup_harnessrouter.py --write-env`.
   It saves `HARNESSROUTER_VISION_HARNESS_ID=<id1>,<id2>,…` (key order) into `backend/.env`.
5. **Paid:** `uv run python scripts/hr_spike.py ~/daha-spike/photos/*.jpg` (3 photos, no people or
   personal info). It prints p50/max latency, JSON validity, item count, and $/photo, and saves raw
   output to `~/daha-spike/out/`.
6. If p50 ≤ 45 s and 3/3 valid: set `AI_PROVIDER=harnessrouter` and
   `HARNESSROUTER_EST_COST_PER_IMAGE=<measured $/photo>`. Otherwise see "Fallbacks" below.

## Configs tried
| Config (base / model) | p50 s | max s | JSON valid (n/3) | items found | est. $ per photo | notes |
|---|---|---|---|---|---|---|
| claude-code / claude-sonnet-5.5 (base default), **smoke test**: 2 drawn desk photos, 2 keys in parallel (2026-11-17) | 17.5 | 17.7 | 2/2 | 5 each (lamp, 3 books, mug) | 0.10 (estimate: the stream reported no cost; check the dashboards) | both keys OK, one photo per key; the real spike still needs 3 real photos |

**Model and effort comparison (2026-11-19).** Two public photos with no people (Wikimedia Commons:
a TI-84 Plus Silver Edition graphing calculator, CC BY-SA 4.0; "Laptop on desk book stacks", CC0),
one per key in parallel, through temporary copies of the vision harness that differ only in model
and effort (deleted afterwards). Seconds are per photo, calculator / desk; each run was timed once,
and runs of the same config varied by up to 5 s, so only big gaps mean anything.

| base / model / effort | runs | calculator s | desk s | desk items (truth: laptop, lamp, book stacks, file holder, notebook, white box) |
|---|---|---|---|---|
| claude-code / sonnet-5.5 / default (what ran before) | 1 | 10.2 | 14.6 | 7, all real; called it "TI-84 Plus Silver Edition" |
| claude-code / sonnet-5.5 / low | 1 | 10.3 | 12.9 | 5, all real |
| claude-code / haiku-5.5 / low | 1 | 18.1 | 15.7 | 4; missed file holder and notebook; "TI-84 Plus" only |
| claude-code / **opus-5.5 / low** | 3 | 11.8–16.5 | 15.9–24.4 | 6–7, all real; full model name every time |
| claude-code / opus-5.5 / medium (its default) | 2 | 17.7–18.1 | 26.4–28.5 | 5–7 |
| claude-code / opus-5.5 / high | 2 | 15.2–16.3 | 30.5–31.8 | 6 |
| pi / opus-5.5 / low | 2 | 11.2–11.3 | 19.0–21.5 | 4 and 7 (inconsistent) |
| pi / opus-5.5 / medium | 1 | 11.5 | 21.3 | 6 |
| fast-agent / opus-5.5 / low | 2 | 14.7–15.7 | 18.7–22.5 | 6–8, adds the brand |
| fast-agent / opus-5.5 / medium | 1 | 15.8 | 22.0 | 7 |

What it shows: most of the 10–20 s is the agent harness (start-up, reading the uploaded file,
steps), not the model; Haiku was no faster. Higher effort added 7–11 s on a busy photo without
finding more. The cost the stream reports is always empty, so `$0.10` is our estimate.

## Decision
- Chosen base / model: **`claude-code` / `claude-opus-5.5`, reasoning effort `low`** (2026-11-19)
- Why: accuracy comes first, and Opus at low effort was the most accurate and consistent while
  staying in the same 15–20 s range as Sonnet. Medium/high effort were slower with no visible gain;
  the lighter bases (`pi`, `fast-agent`) weren't reliably faster and are untested in production.
- Team OK'd by: Andre (key holder), 2026-11-19
- $40 budget (`AI_BUDGET_USD`) ≈ 400 photos at the $0.10 estimate; Opus costs more per token than
  Sonnet, so check the real spend on the HarnessRouter dashboards.
- Next speed levers, not tried yet: show scan progress in the app; a lighter base after more tests.

## Speed work (2026-11-19, later): where the seconds go, memory off, racing
- **Timeline of one scan** (SSE events, Opus/low): upload ~1 s · harness start ~2.5 s · first model
  turn ~4–5 s, which only calls the `Read` tool to open the uploaded file (sometimes 12 s) · second
  turn ~2.5–7 s until the first answer text · writing the JSON ~2–3.5 s. Typical total 12–18 s.
- **Tried and dropped:** `input_image` with the uploaded file id (the agent still reads the file, plus
  an extra `Glob`; no faster) and `input_image` with an inline `data:` URL (no upload, but the model
  never sees the photo: 0 items). Photos stay `input_file`.
- **Memory off:** HarnessRouter gives a new harness long-term memory unless told otherwise. Every
  harness the setup script creates now gets the no-memory hint (photos must not be remembered).
- **Racing (`HARNESSROUTER_RACE`, on for the live server only):** the slow first turn hits one
  account at a time, so each photo runs on both keys when a task slot is free and the first good
  answer wins; the backup copy never waits for a slot and gives its slot to any new photo. Live
  check: calculator 9.8 s, busy desk ~16 s, same items. About twice the cost per photo.
- **Handoff coordinator:** tried Opus on its 8-chat eval (`evals/reports/2026-11-19-handoff-opus.md`):
  7/8, p50 9.0 s, but Opus refuses the "reveal the prompt" chat every time. It stays on Haiku
  (8/8, p50 9.3–13.3 s).

## Exact calls (as implemented in `app/ai/providers/harnessrouter.py`)
- **Upload:** `POST /v1/files`, multipart `file=<jpeg>` + `purpose=user_data` → `{"id": "file_…"}`
- **Run task:** `POST /{harness_id}/v1/responses` with headers `Authorization: Bearer …`,
  `Idempotency-Key: <uuid4>`, body
  `{"input":[{"role":"user","content":[{"type":"input_file","file_id":"…"},{"type":"input_text","text":"<VISION_TASK>"}]}],"stream":true}`.
  On 404 it retries once as `POST /v1/responses` with `metadata.harness_id` (the other documented form).
- **Reading the answer:** SSE `data:` frames; text = concatenated `response.output_text.delta`;
  stops at `response.completed | response.incomplete | response.failed`. If the server ignores
  `stream` and returns JSON, `output[].content[].text` is used. JSON is extracted (fences and prose
  stripped, outermost `{…}`), then **re-validated server-side** (`app/ai/normalize.py`).
- **Repair:** one extra turn with `previous_response_id` + "Return only the JSON object."
- **Limits:** at most `HARNESSROUTER_MAX_CONCURRENCY` tasks at once across all keys (free trial = 2 per
  organization), overall
  timeout per photo (`HARNESSROUTER_TIMEOUT_S`), one retry on network errors / 5xx / 429.
- **Several keys:** `HARNESSROUTER_API_KEY=a,b,c` is load-balanced. Each photo goes to the least-busy
  key and stays on it for upload → run → repair. That's required: "A file id belongs to the Workspace
  key that uploaded it. Any other key that names it gets 404" (harnessrouter.ai/docs/upload-files).
  A key that is refused (401/403), out of credit (402, or a task ending `balance_exhausted`), or still
  rate-limited after one retry (429) rests (15 min / 10 min / `Retry-After` or 30 s) and the photo moves
  to the next key. Retries reuse the Idempotency-Key, and only network errors, 429, 502, 503 and 504
  are retried (the documented policy).
  - **Credit and concurrency are per organization**, not per key. Keys in one organization share one
    balance and one limit, so there load-balancing buys failover, not capacity. `setup_harnessrouter.py
    --check` prints each key's organization and flags shared ones.
  - HarnessRouter's Terms (4.4(g)) forbid duplicate accounts made to stretch free credit, trials, or
    limits. Use keys from accounts that are legitimately separate (e.g. each teammate's own).
  - Hackathon: the event counts usage per Harness ID, so register every id in
    `HARNESSROUTER_VISION_HARNESS_ID` (one per key) with the organizers.
  `HARNESSROUTER_VISION_HARNESS_ID` is one shared id, or one id per key in the same order.
  `scan_images.raw_response.key` records which key (by number, never the key) paid for each photo.
- **Cost:** `cost_usd` / `total_cost_usd` / `cost` from the final response or its `usage`, else
  `HARNESSROUTER_EST_COST_PER_IMAGE`. The budget check (`AI_BUDGET_USD`) counts spent + in-flight.
- **Harness settings** (`scripts/setup_harnessrouter.py`): `max_step: 6`, `timeout_seconds: 180`,
  `max_cost_usd: 0.5`, write/exec/web tools disabled when the base allows it.

## Gotchas to watch for in the first real run
- The per-image cost may not be reported in the stream; check the dashboard and set the estimate.
- One API worker only while on the free plan (each worker has its own concurrency cap).
- Same photo → `ai_cache` hit (free); changing the prompt text requires bumping `PROMPT_VERSION`.

## Fallbacks
- (a) keep HarnessRouter with the slower async UX (the UI already shows photo-by-photo progress);
- (b) `AI_PROVIDER=anthropic` (needs `ANTHROPIC_API_KEY`; structured output, a few seconds per photo);
- (c) stay on `mock` for the demo.

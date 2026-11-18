# HarnessRouter spike results (C0)

> **Status (2026-11-17): code ready, numbers pending the API key.** The provider, setup script,
> and spike script are built and tested against a mocked HarnessRouter SSE stream
> (`backend/tests/ai/test_harnessrouter.py`). The table below gets filled in the first time the
> spike runs with a real key. Until then the app runs on `AI_PROVIDER=mock`.

## How to run it (≈ 10 minutes, ≈ $0.30)
1. Put the Workspace key in `backend/.env` only: `HARNESSROUTER_API_KEY=sk-hr-…`. Several keys:
   comma-separated, no spaces (`sk-hr-aaa,sk-hr-bbb`). Check them (free):
   `cd backend && uv run python scripts/setup_harnessrouter.py --check`
2. See what's available (free): `cd backend && uv run python scripts/setup_harnessrouter.py --list`
3. Pick a base/model, set `HARNESSROUTER_BASE` and `HARNESSROUTER_MODEL` in `backend/.env`.
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

## Decision
- Chosen base / model: _pending_ (default in `.env.example`: `claude-code`)
- Why:
- Team OK'd by:
- $40 budget (`AI_BUDGET_USD`) ≈ ___ photos at this cost

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

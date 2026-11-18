# HarnessRouter spike results (C0)

> **Status (2026-11-17): code ready, numbers pending the API key.** The provider, setup script,
> and spike script are built and tested against a mocked HarnessRouter SSE stream
> (`backend/tests/ai/test_harnessrouter.py`). The table below gets filled in the first time the
> spike runs with a real key. Until then the app runs on `AI_PROVIDER=mock`.

## How to run it (≈ 10 minutes, ≈ $0.30)
1. Put the Workspace key in `backend/.env` only: `HARNESSROUTER_API_KEY=sk-hr-…`
2. See what's available (free): `cd backend && uv run python scripts/setup_harnessrouter.py --list`
3. Pick a base/model, set `HARNESSROUTER_BASE` and `HARNESSROUTER_MODEL` in `backend/.env`.
4. Create the harness (free): `uv run python scripts/setup_harnessrouter.py`, then paste the printed
   `HARNESSROUTER_VISION_HARNESS_ID=…` into `backend/.env`.
5. **Paid:** `uv run python scripts/hr_spike.py ~/daha-spike/photos/*.jpg` (3 photos, no people or
   personal info). It prints p50/max latency, JSON validity, item count, and $/photo, and saves raw
   output to `~/daha-spike/out/`.
6. If p50 ≤ 45 s and 3/3 valid: set `AI_PROVIDER=harnessrouter` and
   `HARNESSROUTER_EST_COST_PER_IMAGE=<measured $/photo>`. Otherwise see "Fallbacks" below.

## Configs tried
| Config (base / model) | p50 s | max s | JSON valid (n/3) | items found | est. $ per photo | notes |
|---|---|---|---|---|---|---|
| _pending key_ | | | | | | |

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
- **Limits:** process-wide semaphore (`HARNESSROUTER_MAX_CONCURRENCY`, free plan = 2), overall
  timeout per photo (`HARNESSROUTER_TIMEOUT_S`), one retry on network errors / 5xx / 429.
- **Cost:** `cost_usd` / `total_cost_usd` / `cost` from the final response or its `usage`, else
  `HARNESSROUTER_EST_COST_PER_IMAGE`. The budget check (`AI_BUDGET_USD`) counts spent + in-flight.
- **Harness settings** (`scripts/setup_harnessrouter.py`): `max_step: 6`, `timeout_seconds: 180`,
  `max_cost_usd: 0.5`, write/exec/web tools disabled when the base allows it.

## Gotchas to watch for in the first real run
- The per-image cost may not be reported in the stream; check the dashboard and set the estimate.
- One API worker only while on the free plan (each worker has its own semaphore).
- Same photo → `ai_cache` hit (free); changing the prompt text requires bumping `PROMPT_VERSION`.

## Fallbacks
- (a) keep HarnessRouter with the slower async UX (the UI already shows photo-by-photo progress);
- (b) `AI_PROVIDER=anthropic` (needs `ANTHROPIC_API_KEY`; structured output, a few seconds per photo);
- (c) stay on `mock` for the demo.

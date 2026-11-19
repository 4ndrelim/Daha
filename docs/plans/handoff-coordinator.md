# Implementation plan: handoff coordinator (HarnessRouter agent)

- Status: **built (2026-11-19)**, behind `HANDOFF_COORDINATOR_ENABLED` + `NEXT_PUBLIC_HANDOFF_COORDINATOR` (both default false); results at the end. A's human asked for plan-then-build without a separate "go"; B and C approved the scope, so the PR merges when checks pass.
- Owners by path: **A** (migration, models, schemas, `services/handoff.py`, `routers/handoff.py`, config, `.env.example`) · **C** (`backend/app/ai/handoff.py`, `scripts/setup_harnessrouter.py`, `tests/ai/`, `evals/`) · **B** (`web/` chat card, types, endpoints). Built by A.
- Related: `docs/research/harnessrouter-workflows.md` §3.6 (the larger "campus assistant" idea; this is a small, tool-less slice of it) and the condition check (#35), whose agent pattern this follows.

## Goal
In a transaction's chat, a "Suggest a time & place" button asks an agent to read the recent messages and propose a handoff time and exchange spot.
One person sends the suggestion with a tap, the other accepts with a tap, and the transaction gets its pickup place and time.

## Files to touch
| File | Owner | Change |
|---|---|---|
| `backend/alembic/versions/0004_transaction_handoff.py` | A | `transactions.pickup_at` (timestamptz, null) and `transactions.handoff_suggestion` (JSONB, null). Additive |
| `backend/app/models/__init__.py`, `backend/app/schemas/transactions.py`, `schemas/__init__.py` | A | the two columns; `Transaction.pickup_at`, `Transaction.handoff`, `HandoffState`, `HandoffSuggestion`, `HandoffSendBody` |
| `backend/app/services/handoff.py` (new), `backend/app/routers/handoff.py` (new), `app/main.py`, `services/transactions.py` | A | rules, limits, budget, endpoints, the serializer hook |
| `backend/app/core/config.py`, `backend/.env.example` | A | `HANDOFF_COORDINATOR_ENABLED`, `HANDOFF_BUDGET_USD`, `HANDOFF_EST_COST_PER_RUN`, `HARNESSROUTER_HANDOFF_HARNESS_ID`, `HARNESSROUTER_HANDOFF_MODEL` |
| `backend/app/ai/handoff.py` (new) | C | prompt, what is sent, validation, the HarnessRouter call, the labeled sample |
| `backend/scripts/setup_harnessrouter.py` | C | `--handoff`: the `handoff-coordinator` harness (dsh base, no tools, `max_cost_usd` 0.05) |
| `backend/tests/ai/test_handoff.py`, `backend/tests/core/test_handoff_coordinator.py` (new) | C / A | no paid calls; HarnessRouter mocked |
| `evals/run.py`, `evals/data/handoff/chats.jsonl` (new) | C | 8 sample chats, latency p50, real cost |
| `web/src/components/daha/handoff-coordinator.tsx` (new), `messages/[id]/page.tsx`, `lib/handoff.ts`, `lib/api/types.ts`, `lib/api/endpoints/transactions.ts`, `web/.env.example` | B | the button, the suggestion card, `NEXT_PUBLIC_HANDOFF_COORDINATOR` |
| `PLAN.md` §5.3, §6, §7 · `docs/decisions.md` | shared | additive contract changes |

## Steps, in order
1. **Measure the model.** List `GET /v1/models` for the dsh base, try the small fast candidates on 2 sample chats, keep the fastest one that returns valid JSON.
2. **Backend.** Migration and types; `app/ai/handoff.py`; `services/handoff.py`; endpoints:
   - `POST /transactions/{id}/handoff/suggest` runs the agent in the background (only on this tap). 429 after 3 runs per transaction per 24 h.
   - `POST /transactions/{id}/handoff/send` sends the draft as it is, or with a changed time or place ("Change").
   - `POST /transactions/{id}/handoff/accept` is the other person's one tap: sets `pickup_place_id` and `pickup_at`, adds a timeline row and a system message.
   - `DELETE /transactions/{id}/handoff` drops a draft.
3. **Harness.** Create `handoff-coordinator` per key, save the ids in `backend/.env`.
4. **Web.** Button and card in the chat, behind `NEXT_PUBLIC_HANDOFF_COORDINATOR`; 360 px and screen-reader checks.
5. **Eval** on 8 chats (paid, inside the $1 line), report p50 latency and the real cost from the HarnessRouter balance.
6. **Checks**, PR, merge, then the phone steps for the human.

## What the agent gets, and what it returns
- **In:** the last 10 text messages of that transaction's chat with senders named `lender` / `borrower` and both people's names replaced inside the text; emails, phone numbers and links removed; the exchange places (id, name); both dorms; the item's pickup place if set; the date and time in `America/Los_Angeles`. Nothing else: no emails, ids, item name, or other chats.
- **Out:** `{"start_time": ISO, "place_id": int, "reason": one short line, "confidence": 0..1}`.
- **Validation:** the place must exist; the time must be in the future and within 7 days; the reason is cut to one line with links removed. One repair turn if invalid, then "Couldn't find a good time — suggest one yourself" (the person can still pick a time and place by hand).
- The chat text is untrusted. The harness has no tools, and nothing from the reply is used except those four checked fields.

## Tests
- Unit: what is sent (roles, no names, no emails, at most 10 messages), validation (bad place, past time, more than 7 days, junk), repair then fallback, the labeled sample with `AI_PROVIDER=mock`.
- API: flag off → 404; only the two people in the transaction; the 3-per-day limit; the budget stop; a draft is visible only to the person who asked; accept fills place and time and posts one system message; "Change" then accept.
- Eval: clear time, vague "after class", conflicting times, no time mentioned, two prompt-injection attempts, a past time, a place named in the chat.
- Web: lint, typecheck, build, the existing end-to-end test; the card at 360 px.
- `make smoke` and the scripted demo flow with the flag on.

## Risks and open questions
- **Real cost is unknown until measured.** Earlier agents reported no cost; this plan reads the account balance before and after the eval instead.
- **A wrong but valid suggestion** (e.g. the wrong day). Nothing is set until a person sends it and the other accepts, and both can change it.
- **Speed.** A task takes several seconds; the button shows progress and the chat stays usable.
- **Prompt injection** through chat text: covered by no tools, strict validation and the eval cases.
- **Time zones:** the agent works in campus time; a reply without a zone is read as campus time.

## Out of scope
- Running by itself, reminders, calendar invites, notifications beyond the chat's own system message.
- Reading anything outside the one transaction chat; tools or web access for the agent.
- Rescheduling after the handoff, and return scheduling.

## Deviations from existing plans
- A third paid HarnessRouter use (after scans, habit profiles and the condition check), with its own budget line `HANDOFF_BUDGET_USD=1`.
- Contract: `Transaction.pickup_at` and `Transaction.handoff` are new, additive fields (`PLAN.md` §7).
- The harness uses the `dsh` base with its own model setting, not `HARNESSROUTER_BASE` / `HARNESSROUTER_MODEL`.

## What was built and measured (2026-11-19)
- **Model:** a trial of 2 chats on three small models on the dsh base: `claude-haiku-5.5` 9.3 s, `deepseek-v4.1-flash` 9.4 s, `gemini-3.5-flash-lite` 17.9 s (p50; all answers valid and correct). The harness uses **`claude-haiku-5.5`**. Most of the time is the harness starting up, not the model.
- **Harness `handoff-coordinator`:** dsh base, all 13 of the base's tools switched off, no MCP servers, `max_step` 2, `max_cost_usd` 0.05, **no memory**. One harness per key; the ids are in `HARNESSROUTER_HANDOFF_HARNESS_ID`.
- **Eval, 8 chats** (`evals/reports/2026-11-18-handoff.md`): 8/8 valid, 8/8 as expected, including both prompt-injection chats. Latency p50 9.3 s on the first full run and 13.3 s on the second (p95 16.5 s).
- **Cost:** the tasks report no cost. The account balance moved by $0.0019 over the first 8 tasks and $0.0002 over the second 8, so well under 1 cent per suggestion by that reading; the balance may lag, so the dashboard is the final word. The budget counts $0.02 per run until a real figure is set (`HANDOFF_EST_COST_PER_RUN`).
- **Through the app:** the real agent answered in 10.5 s end to end; send, accept, the system messages and the pickup time were checked in a 360 px browser. axe found 0 accessibility violations on the card and the change form.

**Found on the way: HarnessRouter gives new harnesses a long-term memory by default.** It "observes" every task and keeps facts per person. The handoff harness is created with a no-memory hint and its trial harnesses and their memories were deleted. `setup_harnessrouter.py --profile` now does the same for new profile harnesses. The existing vision and profile harnesses on the two team keys still have memory on; switching it off there is the team's call, because recreating a harness changes the id registered with the hackathon organizers (it can also be switched off per harness in the HarnessRouter console, under Settings → Memory).

**Deviations from the plan above**
- A person can also pick a time and place by hand without running the agent ("Pick a time myself"), so the feature still works when the agent is off, paused or out of runs.
- The other person can answer with "Change" (a counter-suggestion) instead of accepting.
- Agreeing on a time does not change the transaction's status; accepting the exchange itself stays a separate tap, as before.

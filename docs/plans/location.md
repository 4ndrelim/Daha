# Implementation plan: phone location for "Buy or rent nearby"

- Status: waiting for go · Implementer: **A** (with B's and C's agreement) · Date: 2026-11-18
- **The design is `plans/LOCATION.md`.** This file does not repeat it; it records who owns what, the build order, and where the build differs. Background: `plans/C-ai-discovery.md` → C6 and `docs/proposals/C-exa-buy-nearby.md`.

## Goal
Store search uses the phone's current location when DAHA is allowed to use it, and Stanford campus otherwise; a typed town or ZIP overrides both.
The dorm stops being the default, and the location prompt only ever appears right after a tap.

## Files to touch
| File | Owner | Change |
|---|---|---|
| `backend/app/discovery/commercial.py` | C | `resolve_near()`: typed place → device → campus; campus label |
| `backend/tests/discovery/test_commercial.py` | C | rewrite the order test; add "dorm, no coordinates → campus"; fix `test_api_mock_offers_near_the_dorm` |
| `backend/app/schemas/discovery.py` | A | comment only: `"dorm"` stays in `near_source` but is no longer returned |
| `backend/app/core/config.py`, `backend/.env.example` | A | new `COMMERCIAL_DEFAULT_LABEL=Stanford campus` |
| `web/src/lib/near.ts` | B | `locationPermission()`, choice becomes `auto` / `campus` / place, 5 s timeout, migrate old saved values |
| `web/src/components/daha/buy-nearby.tsx` | B | `openedBy`, the four permission cases, chips, labels, `NearSheet`, "Turn on location" how-to, `location_permission` event |
| `web/src/app/(app)/explore/explore-screen.tsx` | B | only if the panel needs to be told how it was opened |
| `web/src/lib/api/types.ts`, `web/src/lib/api/mock/search.ts` | B | comment on `near_source`; mock returns campus instead of dorm |
| `PLAN.md` §2 item 12, §5.3, §7.2 · `ARCHITECTURE.md` §8 | shared | the one stated exception to "dorm-level only"; new env var; `"dorm"` note |
| `plans/C-ai-discovery.md` → C6 | C | new location order |
| `plans/LOCATION.md` | B + C | status line → built |
| `docs/decisions.md` | shared | one line for the new default |
| `.gitignore` | A | add `CLAUDE.local.md` |

## Steps, in order
1. **Server (`LOCATION.md` §5.1).** Change `resolve_near()`, add the label setting, update the tests. Run `uv run ruff check . && uv run pytest -q`.
2. **Web (§5.2).** `near.ts` first, then `BuyNearby`, then `NearSheet` and the how-to sheet, then the event. Run `pnpm lint && pnpm typecheck && pnpm build`.
3. **Docs (§5.3).** The files in the table above.
4. **PR** `A: phone location for store search [LOCATION]`, with this plan in it. It touches B's and C's files, so it waits for both 👍 and is not auto-merged.
5. **Phone test.** Start the app and the cloudflared https tunnel, hand over the §6 table to fill in, and report against the §7 "Done when" list.

## Tests
- Backend: typed place beats coordinates; coordinates beat campus; a user with a dorm and no coordinates gets campus; coordinates are rounded on the server; nothing about location is stored (existing test kept).
- Web: lint, typecheck, build. There is no Playwright test yet, so the permission cases are checked by hand (laptop Chrome with DevTools location, then phones).
- By hand: the §6 table over the https link, including "no coordinates in the URL, the API log, or the `events` / `ai_cache` tables".
- No paid calls in tests: Exa stays mocked. Phone testing with `COMMERCIAL_PROVIDER=exa` costs about $0.017 per new lookup (capped at $9 a month).

## Risks and open questions
- **iPhone Safari cannot report permission state reliably.** Where the browser can't tell, the plan says treat it as "not asked yet", so an iPhone that already allowed location may still need one tap. "Done when" #1 may hold on Android but only partly on iPhone; the phone test will show it.
- **A denied prompt must not come back.** After a denial or a timeout in this session, the panel remembers it and shows "Turn on location" instead of asking again.
- **How-to wording** depends on the OS version; it needs a look on real phones (§5.2 item 4).
- **Location is only a hint to Exa** (C's live test): "Near you" changes the search area, but results may still be online or far away. That is a known limit, fixed later by a places API.
- **Open question for B:** is the chip wording "📍 Use my location" / "Turn on location" fine as written in the plan? I will use it as written unless told otherwise.

## Out of scope
- Real store distances and a places API (`LOCATION.md` §8).
- Device location for anything peer-to-peer (search, matching, walking minutes stay dorm-level).
- The Playwright smoke test, hosting on a VM, and a `make tunnel` target.

## Deviations from existing plans
- **Implementer:** `LOCATION.md` assigns §5.1 to C and §5.2 to B; A builds both, with their agreement, and they review the PR.
- **Campus label:** `LOCATION.md` §5.1 item 2 allows either a new setting or deriving the label. This build adds the setting `COMMERCIAL_DEFAULT_LABEL`.
- **`near_source`:** no contract change. `"dorm"` stays in the type and is simply never returned (as §5.1 item 3 says).
- Everything else follows `plans/LOCATION.md` as written.

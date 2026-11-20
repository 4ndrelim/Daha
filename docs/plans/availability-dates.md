# Plan: availability dates for listed items

- Status: **built 2026-11-19** by A, across A, B and C files with the team's OK · No migration · Contract: additive only
- Related: `PLAN.md` §6 (`items.available_from`, `items.available_until`), §7 (`ItemCard`, `POST /items/{id}/borrow`, `GET /search`)

## 1. Goal
A lender can say "available from" and "until" for a thing. Everyone sees it ("Available from Sat 21 Nov"),
and the app respects it: outside its dates an item is not offered as available, and cannot be borrowed for those days.

## 2. What already existed (checked in the code before building)
| Area | State before | Where |
|---|---|---|
| Database | ✅ `available_from`, `available_until` (nullable `DATE`) since the first migration | `backend/alembic/versions/0001_initial_schema.py`, `app/models/__init__.py` |
| API: create / edit | ✅ both accepted; 400 if "until" is before "from". ❌ a past "until" was accepted | `app/schemas/items.py`, `app/services/items.py` |
| API: item page | ✅ returned on `ItemDetail` | `app/services/serializers.py` |
| API: cards | ❌ not on `ItemCard`, so lists could not show them | `app/schemas/items.py` |
| Item form (new + edit) | ✅ two date inputs. ❌ no lower limit, no explanation, no way to clear, side by side even at 360 px | `web/src/app/(app)/add/item/item-form.tsx` |
| Scan review | ❌ nothing (the server already accepted the fields on publish) | `web/src/components/scan/defaults-bar.tsx`, `review-model.ts` |
| Item page | 🟡 one row "Now – whenever". ❌ no notice, borrow sheet ignored the dates | `web/src/app/(app)/items/[id]/page.tsx` |
| Cards | ❌ | `web/src/components/daha/item-card.tsx` |
| Search | 🟡 only when the query names dates ("this weekend" → overlap filter). ❌ otherwise the dates were ignored: a tent "from next month" looked available today | `app/discovery/search.py`, `query_parser.py` |
| Feeds, request matching, reverse matching, "You could help", mutual matching | ❌ ignored the dates | `app/discovery/feeds.py`, `matching.py`, `mutual.py` |
| Borrow | ❌ ignored the dates | `app/routers/items.py` |
| Seed | 🟡 two "this weekend" rows | `app/seed/data/items.json` |

So the storage and the form were there; nothing read the dates. This plan builds only the missing parts.

## 3. Rules
"Today" is the campus day (`CAMPUS_TZ=America/Los_Angeles`, `geo.campus_today()`), on the server. Both dates are inclusive.

| Item | Called | Search (default, "available only") | Search "show all", profiles, community pages, new near you | Request matching | Mutual matching | Borrow |
|---|---|---|---|---|---|---|
| no dates, or today inside them | now | shown | shown | yes | yes | yes |
| `available_from` ahead | upcoming | hidden | shown with "Available from Sat 21 Nov", ranked lower | only if the request's dates reach it | no | yes, with a start date inside the dates ("ask ahead") |
| `available_until` passed | ended | hidden | hidden (profile: shown as "Ended …") | no | no | no |

- A search that names dates ("tent this weekend") is judged on those dates, as before.
- A request without dates means "now": only items available today match. With `needed_from`/`needed_until`, an item matches when it is available on at least one of those days.
- Borrow messages (409, shown as they are): "“Ski jacket” is available from Sat 21 Nov. Pick a start date on or after that." · "… needs to be back by Mon 23 Nov. Pick an earlier return date." · "… is only available until …" · "… was only available until …".
- An owner can still offer their own item on someone's request whatever its dates (their call).
- Nothing is switched off by a timer. Every read checks the dates, so there is no nightly job to forget.

## 4. Data and contract
- No migration.
- `ItemCard` gains `available_from`, `available_until` (moved up from `ItemDetail`, which still has them) and `available_now: boolean`. Optional in the TypeScript type, so mocks and older clients keep working.
- `POST /items`, `PATCH /items/{id}`, scan publish: 400 "The “until” date (…) has already passed". On edit this is checked only when a date is in the request, so an old item can still be renamed or re-opened by clearing the date.
- `POST /items/{id}/borrow`: new 409 reasons above. `can_borrow` is false for an ended item.
- `GET /search`: behaviour in §3; `match_reason` says "From Sat 21 Nov" instead of "Available" for upcoming items.

## 5. Files
| File | Owner | Change |
|---|---|---|
| `backend/app/services/availability.py` (new) | A | the rules: `window`, SQL clauses, `borrow_problem`, `dates_problem` |
| `backend/app/services/items.py`, `app/routers/items.py`, `app/schemas/items.py`, `app/services/serializers.py` | A | validation, borrow check, card fields, `can_borrow` |
| `backend/app/discovery/search.py`, `scoring.py`, `config.py`, `feeds.py`, `matching.py`, `mutual.py` | C | one clause each; `UPCOMING_FACTOR = 0.6`; reason label |
| `backend/app/seed/seed.py`, `seed/data/items.json` | A | `"avail": {"from": 2, "until": 23}` (days from today); 4 demo items |
| `backend/tests/discovery/test_availability_dates.py` (new) | A | 14 tests |
| `web/src/lib/availability.ts` (new), `components/daha/availability-fields.tsx` (new) | B | wording, campus "today", the shared date fields |
| `web/src/components/daha/chips.tsx`, `item-card.tsx`, `app/(app)/items/[id]/page.tsx`, `app/(app)/add/item/item-form.tsx` | B | card line, notice, borrow sheet limits, form |
| `web/src/components/scan/defaults-bar.tsx`, `review-model.ts`, `review-step.tsx` | C | dates for the whole batch |
| `web/src/lib/api/types.ts`, `PLAN.md` §7, `docs/decisions.md` | shared | contract |

## 6. Steps
1. `availability.py` and its unit test. 2. Card fields + validation + borrow. 3. Search, feeds, matching, mutual. 4. Seed. 5. Web: helper, card, item page, borrow sheet, form, scan review. 6. Docs. 7. Checks, reseed, browser pass at 360 px, accessibility scan.

## 7. Tests
- Backend (`tests/discovery/test_availability_dates.py`): scan publish with dates; inclusive ends; the campus day; dates on cards; a past "until" refused, an old item still editable; default search hides upcoming and ended, "show all" lists upcoming below available ones, a dated query finds an item that starts that day; matching with and without request dates; an item listed after the request; mutual matching drops and regains a pair when the date changes; five borrow cases; an ended item.
- Web: lint, typecheck, build; headless browser at 360 px (form, scan review fields, card, item page, borrow sheet); axe scan.

## 8. Risks and open questions
- **Phone clock vs campus day.** The web computes the campus day with `Intl` for picker limits only; the server decides. A phone in another time zone may offer one day too many in the picker and then gets the server's sentence.
- **Stored matches.** `request_matches` rows are computed when a request or item is saved. Every place that shows them re-checks the dates, so a stale row never surfaces; a date edit on an item recomputes its rows through the existing reverse-matching hook.
- **Upcoming items disappear from default search.** That is the rule asked for. "Show all" in the filter sheet lists them. Open question for B: should the Explore empty state mention it?
- **Date inputs on iPhone** ignore `min`/`max` in some versions; the inline message and the server check cover it.

## 9. Out of scope
Recurring availability ("weekends only"), times of day, a calendar of bookings, blocking days already promised to another borrower, reminders when an item becomes available, availability on requests (they already have needed dates).

## 10. Self-review against the code (what I changed in this plan)
- **`available_only` defaults to true** (`app/discovery/router.py`, and the web's filter sheet). My first draft said upcoming items show in search with a label; in the real default they must be hidden, and only "show all" lists them. Rule table and tests rewritten.
- **Dated searches would have broken.** With "available only" on, a blanket "available today" clause would hide the seeded "free this weekend" boxes from the query "boxes this weekend". The today-clause is skipped when the query names dates.
- **`ItemDetail(**card.model_dump(), available_from=…)`** would have passed the same field twice once the card had it; the explicit copies were removed.
- **Free and swap items have no date pickers** in the borrow sheet, so asking ahead would always be refused. The sheet now sends the item's first day as the start date for an upcoming item.
- **Reverse matching** (`reverse_match_item`, run when an item is saved) was missing from the first file list; it needed the mirror-image clause.
- **The borrow sheet replaced every 409 with one fixed sentence**, which would have hidden the new messages; it now shows the server's sentence.
- **Seed:** one demo row was first given to Sam, whose empty shelf is part of the demo (`test_seed.py`), and used a category that does not exist; moved to Leo, category fixed.
- **Weekend-proof test:** a test item "from Saturday" is available on Saturdays; the test now uses a fixed offset for the hidden case.

## 11. Done when
- [x] Lender can set, change and clear both dates in the item form, and set them for a batch in scan review.
- [x] Cards and the item page say "Available from Sat 21 Nov" / "Available until …".
- [x] Outside its dates an item is not shown as available in search, matching or mutual matching.
- [x] A borrow request outside the dates is refused with a sentence that says what to change.
- [x] Dates follow America/Los_Angeles. Demo data has items with future availability.
- [x] Works at 360 px; axe finds no violations on the changed screens.
- [x] ruff, pytest, pnpm lint/typecheck/build, `make smoke`.

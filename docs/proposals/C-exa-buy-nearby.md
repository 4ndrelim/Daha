# Buy or rent nearby: commercial alternatives from web search (Exa)
- Status: accepted (built as C6)
- Author: Andre · Date: 2026-11-17
- Problem it solves: when nobody on campus has listed something, or someone can't wait for a lender, they leave DAHA to search stores. We can show the closest store and rental options nearby, cheapest first, without hiding the free option (borrowing).
- Proposal: `POST /api/search/commercial` (C, `app/discovery/commercial.py`) runs one Exa web search for the cleaned search words near the person, reads a per-page structured summary (is it really an offer, product, price, unit, buy/rent/service, seller, store town), and returns up to 8 offers sorted by price. On Explore (B's screen), the panel opens by itself when campus has ≤ 2 items; otherwise a "Compare store prices nearby" button opens it. Details: `plans/C-ai-discovery.md` → C6.
- Cost: usage-based. Exa `auto` search $7 per 1k requests (≤ 10 results) + summaries $1 per 1k pages ≈ $0.017 per uncached lookup. Exa's free tier is $10 a month, so the default `COMMERCIAL_BUDGET_USD=9` keeps us inside it (~500 lookups/month, more with cache hits). Prices from exa.ai/pricing, checked 2026-11-17.
- Effort: ~1 day. Touches `backend/app/discovery/{commercial,router}.py`, `backend/app/schemas/discovery.py`, `backend/app/core/config.py`, `web/src/components/daha/buy-nearby.tsx`, `web/src/lib/near.ts`, `web/src/app/(app)/explore/explore-screen.tsx`, the search endpoint and mock, `PLAN.md` §5.3/§7.
- Keys / accounts needed: `EXA_API_KEY` (Exa dashboard). Who has it: Andre.
- Risks / privacy:
  - Only the cleaned words (emails, phone numbers and links removed) and a coarse area leave our server. The area is the dorm's coordinates or the browser's location (opt-in, https only), both rounded to ~1 km, or a typed town/ZIP. Never a name, user id, dorm name, or free text from other people.
  - Coordinates aren't stored: the cache key is a hash, and the `commercial_lookup` event keeps only the kind of location (dorm/device/place/campus).
  - Prices come from Exa's per-page summaries (generated text), so the UI says "prices can change, check before you go" and links to the source page.
  - Product photos are hot-linked from stores with `referrerPolicy="no-referrer"`; offer links open with `noopener noreferrer nofollow`.
  - Showing stores could pull people away from borrowing, so the panel is secondary unless campus has ≤ 2 items, and it always ends with "ask your dorm first".
- Recommendation: do now (done).

## Decisions
| date | decision | why |
|---|---|---|
| 2026-11-17 | Auto-open at ≤ 2 campus items; otherwise behind a button | "Limited results" should get help right away; with plenty of campus options, buying stays opt-in |
| 2026-11-17 | Location: typed place > browser (opt-in) > dorm > campus, all rounded to ~1 km; Exa gets coordinates plus "near me" | Exa uses coordinates only for location-dependent queries; ~1 km is enough for "nearby" and matches DAHA's dorm-level privacy |
| 2026-11-17 | One `/search` call with per-page JSON summaries, not `outputSchema` synthesis | Each offer stays tied to the page it came from; synthesis has a 10-property schema limit and adds ~2 s |
| 2026-11-17 | `POST`, not `GET` | An opted-in location never lands in URLs or access logs |
| 2026-11-17 | Spend tracked through `commercial_lookup` events (counts and kinds only), no new table | No migration; the events table already exists for analytics |
| 2026-11-17 | `backend/.env.example` defaults to `COMMERCIAL_PROVIDER=exa`; the code default stays `mock` | The team tries it with the shared key; tests and CI never call Exa; the daily cap and monthly budget limit spend. Mock results are labeled "Sample data" |
| 2026-11-17 | Live test: location is only a hint to Exa (results came from other states); real "nearby" needs a places API later | Honest limit of web search; prices and ranking work |

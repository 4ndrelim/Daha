# Plan: phone location for "Buy or rent nearby"

- Status: **built 2026-11-18** by A with B's and C's agreement (`docs/plans/location.md`); phone test table in §6 still to be filled in · Owners: **B** (web, most of it) + **C** (server) · Effort: about 1 day plus an hour of phone testing
- Depends on: C6 "Buy or rent nearby" being merged (it adds the files below), and an **https** link for phones (§3)

## 1. The rule
Most students will use DAHA on their phones. When the phone's location is on and DAHA is allowed to use it, store search uses **where the person is right now**. When it isn't (location off, permission not given yet, permission denied, the browser can't, or the page is on plain http), store search uses **Stanford campus**. A town or ZIP the person types still overrides both.

Device location is only for store search. Everything peer-to-peer (campus search, matching, walking minutes) stays dorm-level, as `PLAN.md` §7.9 and `ARCHITECTURE.md` §8 promise.

## 2. Where we are today
- **Order now:** typed town/ZIP → the browser's location, but only if the person picks "Near me right now" in the "Where should we look?" sheet → the dorm's coordinates → Stanford campus. So the dorm is the default, and the phone's location is one extra tap away every time.
- **Phones on `make lan` links can't share location at all.** Those links are `http://<laptop-ip>:3000`, and browsers only give location to https pages (and `localhost`). That's why the option is hidden for most phone testers today.
- **Code to build on** (arrives with C6):
  - `web/src/lib/near.ts`: `canUseDeviceLocation()`, `roughDeviceLocation()` (rounds to 2 decimals, ~1 km, before anything leaves the browser), `useNearChoice()` (the remembered choice).
  - `web/src/components/daha/buy-nearby.tsx`: `BuyNearby` (the panel and its query), `NearSheet` (the "Where should we look?" sheet).
  - `backend/app/discovery/commercial.py`: `resolve_near()` (picks the location; rounds again on the server).
  - `backend/tests/discovery/test_commercial.py`: the location tests.
  - The endpoint is already a `POST`, so coordinates never land in URLs or access logs.

## 3. Prerequisite: an https link on phones
Browsers share location only with secure pages.
- **Testing now:** `cloudflared tunnel --url http://localhost:3000` (`plans/INTEGRATION.md` §3.1) prints an `https://….trycloudflare.com` link that works on any phone.
- **Hosted:** the VM + Caddy setup (`plans/INTEGRATION.md` → "Online for real") serves https automatically.
- **Laptop:** `http://localhost:3000` counts as secure, so location works in the laptop's own browser.
- `make lan` links stay plain http. There the app falls back to Stanford campus, which is expected.

## 4. Target behaviour
| Phone / browser state | Location used | Label in the panel | What the person sees |
|---|---|---|---|
| Location already allowed for DAHA | current location (rounded ~1 km) | "Near you" | results right away, no prompt |
| Not asked yet, and they tapped **Compare store prices nearby** | ask now: allowed → current location, else campus | "Near you" / "Near Stanford campus" | one line of why ("To show stores near you. Rough location only, never saved."), then the browser's prompt |
| Not asked yet, and the panel opened by itself (≤ 2 campus results) | Stanford campus | "Near Stanford campus" | results, plus a **📍 Use my location** chip (tapping it asks, then refreshes) |
| Denied, location services off, no answer within 5 s, or no geolocation | Stanford campus | "Near Stanford campus" | results, plus **Turn on location** (opens the short how-to in §5.2) |
| Plain-http page | Stanford campus | "Near Stanford campus" | no location option |
| Typed town or ZIP | that place | "Near 94040" | remembered in this browser until changed |

Rules:
- **Never prompt on page load,** only right after a tap. Prompts out of nowhere get denied, and browsers may quiet them.
- **Never wait more than ~5 s** for a location. If it's slower, use campus and show the results.
- **Remember only the mode** in this browser (`auto` · `campus` · a typed place). Never store coordinates, on the device or the server.
- **Coordinates leave the browser rounded to ~1 km,** only in the POST body of `/api/search/commercial`. They're never logged or stored, and Exa receives only that rounded pair.

## 5. Work, step by step

### 5.1 Server (C, ~1–2 h)
1. `resolve_near()` in `backend/app/discovery/commercial.py`: the new order is **typed place → device coordinates → Stanford campus**. Remove the dorm step. Dorms are all on campus, so results barely change, and the rule becomes simply "you, or campus".
2. Campus label: "Stanford campus". Add `COMMERCIAL_DEFAULT_LABEL=Stanford campus` next to `COMMERCIAL_DEFAULT_PLACE` in `backend/.env.example` and `PLAN.md` §5.3, or derive the label from the place.
3. Keep `"dorm"` in `near_source` in the types for now so nothing breaks, but stop returning it, and note that in `PLAN.md` §7.2.
4. Tests: rewrite `test_near_prefers_typed_place_then_browser_then_dorm_then_campus` for the new order; add "a user with a dorm who sends no coordinates → campus".

### 5.2 Web (B, ~4–6 h)
1. **`web/src/lib/near.ts`**
   - Add `locationPermission(): Promise<"granted" | "prompt" | "denied" | "unavailable">`. Return `unavailable` when `!window.isSecureContext` or there's no `navigator.geolocation`. Otherwise use `navigator.permissions.query({ name: "geolocation" })` where the browser supports it, and treat "can't tell" as `prompt`.
   - Change the remembered choice to `"auto" | "campus" | { place }`, defaulting to `auto` (use location if allowed, else campus). Migrate old saved values: `dorm` → `auto`, `device` → `auto`.
   - Keep `roughDeviceLocation()` (rounding, low accuracy, 10-minute cache) and lower its timeout to 5 s.
2. **`BuyNearby`** in `web/src/components/daha/buy-nearby.tsx`
   - Track how the panel opened: `openedBy: "tap" | "auto"`.
   - In the query for `auto`:
     - `granted` → get the rough location, send `lat`/`lng`;
     - `prompt` + `tap` → call `roughDeviceLocation()` (this shows the prompt), send the coordinates, or fall back to campus;
     - `prompt` + `auto` → send nothing (campus) and show the **📍 Use my location** chip;
     - `denied` / `unavailable` → send nothing (campus) and show **Turn on location**.
   - Labels: "Near you", "Near Stanford campus", "Near <place>".
3. **`NearSheet`:** options **Use my location** (recommended) · **Stanford campus** · **Somewhere else** (town or ZIP). When permission is denied, the first option opens the how-to instead.
4. **"Turn on location" how-to** (a small sheet; check the wording on real phones, because menus move between OS versions):
   - **iPhone (Safari):** Settings → Privacy & Security → Location Services: on, then Safari Websites → While Using the App. For this site: the page-settings button in Safari's address bar → Website Settings → Location → Allow. The installed DAHA app (home-screen) asks on its own the first time.
   - **Android (Chrome):** turn Location on in quick settings. For this site: the icon left of the address → Permissions → Location → Allow. If Chrome itself has no location access: Settings → Apps → Chrome → Permissions → Location.
5. **Events** (counts and kinds only, never coordinates): `location_permission` with `{state, opened_by}`. The existing `commercial_search_shown` already reports `near` (device, campus or place).

### 5.3 Docs (whoever implements it)
- `PLAN.md` §2 item 12 and `ARCHITECTURE.md` §8: "dorm-level only" gets one stated exception: store search may use the phone's location, rounded to ~1 km, only when allowed, never stored.
- `plans/C-ai-discovery.md` → C6: update the location order.
- `docs/decisions.md`: one line for the new default.

## 6. Testing
**Automated**
- Backend: the updated `resolve_near()` tests (`uv run pytest -q tests/discovery/test_commercial.py`).
- Web, once the Playwright smoke test exists (P1 #6): a context with `geolocation: { latitude: 34.05, longitude: -118.24 }` and `permissions: ["geolocation"]` shows "Near you" and sends `lat: 34.05, lng: -118.24`; a context without the permission shows "Near Stanford campus".

**By hand, on real phones over the https link**
| Device | Allowed | Not asked yet | Denied | Location services off | http link |
|---|---|---|---|---|---|
| iPhone, Safari | Near you | prompt after a tap | campus + how-to | campus + how-to | campus |
| iPhone, installed DAHA app | Near you | prompt after a tap | campus + how-to | campus + how-to | n/a |
| Android, Chrome | Near you | prompt after a tap | campus + how-to | campus + how-to | campus |
| Laptop Chrome (DevTools → Sensors → Location, set somewhere far away) | Near you | prompt after a tap | campus | n/a | n/a |

For each: the right label, results within ~6 s, no prompt again after a denial, and no coordinates in the URL (browser Network tab), the API log, or the `events` / `ai_cache` tables.

## 7. Done when
1. On a phone over https with location allowed, store results use the current location ("Near you") with no extra tap.
2. Without location (not allowed, off, unavailable, or http), results use Stanford campus, with no errors and no repeated prompts.
3. The permission prompt only ever appears right after a tap, with one line saying why.
4. A typed town or ZIP overrides both and is remembered.
5. Coordinates leave the browser only rounded to ~1 km, only in the POST body, and are never stored or logged.
6. The checks pass: `uv run ruff check . && uv run pytest -q` and `pnpm lint && pnpm typecheck && pnpm build`.

## 8. Later (not in this plan)
- **Real store distances** ("Target · 2.1 mi"): Exa treats location only as a hint, so truly local results need a places service (Google Places, Mapbox, or OpenStreetMap). Its own proposal (`docs/proposals/`), because of cost and keys.
- **Location for campus features** (e.g. "items near you right now"): needs a privacy review first; DAHA is dorm-level by design.

# Person B — Frontend (web app)

**Mission:** every screen except the scan flow, the design system, and a mock API, so you're never blocked by A or C. Contract: `PLAN.md` §7. Your paths: `web/` except C's (`PLAN.md` §4).

**⏰ Hackathon targets** (`PLAN.md` §0): B0 Tue 11:00 · B1 Tue 15:00 · B2 + B3 Tue 21:00 · B4 Wed 10:00 · B5 Wed 15:00 · B6 Wed 18:00 · demo video Thu 08:00–11:30 · freeze and last redeploy Thu 11:30.

## Status (2026-11-17): the planned milestones are merged and the web runs live; next comes improving and iterating
| Milestone | PR | Notes |
|---|---|---|
| B0 skeleton, contract types, API client, app shell | #6 | |
| B1 login, signup, home, shared components | #7 | A-domain mocks skipped: A1–A4 had already merged |
| B2 explore & search | #8 | |
| B3 add menu, item form, request composer, item page | #9 | |
| B4 request page, offers, chat, transaction card, reviews | #10 | |
| B5 communities, profile, public profile, notifications, invites | #11 | |
| B6a polish, QA, contract check | #12 | no response mismatches; 8 request-body fields are nullable in the API but omit-only in TS |
| B6b go live on every domain + full demo-script pass | #15 | `PLAN.md` §10 steps 1–9 passed headless on fresh seed data |
| B7 installable app (accepted `docs/proposals/B-pwa.md`, part 1) | #13, #14 | push (part 2) rejected for the hackathon |
| fix: `pnpm typecheck` runs `next typegen` first | #19 | passes on a fresh clone |

**Behaviour that differs from, or adds to, the text below** (each line is in `docs/decisions.md`):
- **Mocks:** `web/.env.example` now defaults to `NEXT_PUBLIC_MOCK=none`. The stand-ins for `search, feed, matches, ai` stay in `web/src/lib/api/mock/` for working without a backend.
- **Rendering:** Next.js 16 with `cacheComponents`. The logged-in app renders in the browser only (`AuthGate` uses `use(browser())`), because the token lives in `localStorage`.
- **Signup is two steps:** the account first (`POST /auth/signup` without `dorm_id`), then a dorm picker (`GET /communities?kind=dorm` + `PATCH /me {dorm_id}`), since `GET /communities` needs auth. Invite links preselect `?dorm=<slug>`. The picker shows member counts only.
- **Home:** the big scan card shows while `show_scan_cta` is true; after that, a slim "Snap more" banner.
- **Join with code** lives on each private group's card in Discover groups, because the join call needs the group id.
- **Top bar:** the dorm chip shows the dorm's nickname when it has one ("FloMo").
- **`downscaleImage`** lives in `web/src/lib/image.ts` (C's `components/scan/downscale.ts` exists too).
- **PWA:** icons are committed PNGs in `web/public/icons/`. Two extra events: `install_prompt_shown`, `app_installed`.
- **Demo:** in step 4 Jordan must pick **Who sees it → Campus**. The composer defaults to My dorm, so Wilbur's Maya isn't pinged for a FloMo-only request.
- **Not done (optional):** the `docs/ux-references/` screenshots (a human TODO).
- **B8:** `page_view` is sent on every route change inside the app (path only, never the query string). Playwright smoke test: `web/e2e/smoke.spec.ts`; run `cd web && pnpm e2e` against a running `make api` + `make web` (mock AI, so it's free). It posts one test request; `make seed` clears it.

**Next phase: improve and iterate** (most students will use DAHA on their phones, so phone UX comes first):
1. The weekly top 5 UX fixes from feedback (`plans/INTEGRATION.md` → "Iterate").
2. ✅ Phone location for "Buy or rent nearby" (built by A in #24).
3. ✅ The Playwright smoke test (P1 #6) and the missing `page_view` event (B8).
4. From the research list above: ✅ an accessibility audit (B9: axe, 17 screens, 0 violations),  messaging-style motion, a map view for "near me".

**If behind, cut** (in this order):
1. invite links
2. the `/u/[id]` public profile
3. the Create-group sheet (seeded groups only)
4. the Members tab
5. analytics `track()` calls
6. the profile Reviews tab

## 🧑 Human TODOs (B)
- [ ] Install the prerequisites. Accept the GitHub invite (check your email), then clone the repo.
- [ ] Phone testing: keep your phone on the same Wi-Fi as your laptop and open the link Claude prints (`http://<laptop-ip>:3000`).
- [ ] After B0: look at the app shell on your phone and tell Claude whether the look (colors, wording, vibe) feels right.
- [ ] Optional but valuable: drop 5–10 screenshots of real dorm-chat requests (**blur names**) into `docs/ux-references/`. They guide tone and help C's evals.
- [ ] At every ✅ checkpoint: merge the PR and paste the message.
- [ ] When A or C post a checkpoint, tell Claude: *"Pull main and switch <domains> to live"*. Claude edits `NEXT_PUBLIC_MOCK` in `web/.env.local`. In hands-off mode, Claude does this on its own when it sees their milestones merged.

## Design points (go through these with the human in *involved* mode; in hands-off mode use §1–§2 as written)
- **Look and feel:** colors, wordmark, and tone of copy. The tokens in §1 are only a starting point.
- **Home:** which sections come first, and how prominent the "Show us what you have" scan card is.
- **Community channel:** how chat-like it should feel (bubbles vs. cards).
- **Item cards:** photo-first or text-first, and which details show on the card.
- **Empty states and microcopy**, e.g. "Nobody's listed that yet — ask your dorm?"

## Research & proposals (async)
Research these in small slices, after a milestone or while CI runs. **Never let research block a milestone.** Write each finding as a proposal (`AGENTS.md` §6, template in `docs/proposals/README.md`) and present it at the start of the next session.

- A map view for "near me", using open map tiles and walking-distance rings.
- Installable app (PWA) plus push notifications.
- Privacy-friendly product analytics for the demo: funnels such as scan → publish and request → offer.
- Motion and micro-interactions that make DAHA feel like a messaging app.
- Accessibility audit tooling.

## ✅ B0 — Web skeleton (Phase 0; start right away; touch only `web/`)
1. **Scaffold:** `pnpm create next-app@latest web` with TypeScript, App Router, Tailwind, ESLint, a `src/` directory, and the alias `@/*`. Add `"typecheck": "tsc --noEmit"`.
2. **Dependencies:** @tanstack/react-query, react-hook-form, zod, @hookform/resolvers, date-fns, lucide-react, sonner, clsx, tailwind-merge.
3. **shadcn/ui:** run `init`, then add: button card input textarea label badge avatar tabs sheet dialog dropdown-menu select checkbox switch slider skeleton separator toggle-group scroll-area popover calendar progress sonner.
4. **`next.config.ts` rewrites:** `/api/:path*` → `${API_PROXY_TARGET}/api/:path*` and `/uploads/:path*` → `${API_PROXY_TARGET}/uploads/:path*`, with a default target of `http://localhost:8000`. Create `web/.env.example` per `PLAN.md` §5.4.
5. **API layer** (`src/lib/api/`):
   - `types.ts`: `PLAN.md` §7.2 **verbatim**.
   - `client.ts`:
     - `http<T>(method, path, {body?, form?, query?})`: prefixes `/api`; adds the Bearer token from `localStorage["daha_token"]`; sends JSON; throws `ApiError {status, detail}`; on 401, clears the token and goes to `/login?next=<current>`.
     - `isMocked(domain)`, which reads `NEXT_PUBLIC_MOCK` (`all` / `none` / comma list).
     - `call<T>(domain, live, mock)`.
   - `endpoints/<domain>.ts`: one typed function per endpoint in §7.3, **except scans** (C adds `endpoints/scans.ts`).
   - `index.ts`: exports `api`.
   - Until B1, the mock functions throw `"mock not implemented"`.
6. **Design tokens** (§1 below), Inter via `next/font`. Components: `QueryProvider`, `Toaster`, `AppShell` (top bar + bottom nav), `AuthGate` (redirects to `/login?next=` when there's no token).
7. **Placeholder pages** for every route in §2, including C's `/onboarding` and `/add/scan` (C owns those files after this).
8. **Checks:** `pnpm lint && pnpm typecheck && pnpm build`.

Checkpoint: *"Phase 0 web merged ✅ — `make web` shows the app shell. C: your pages are src/app/onboarding and src/app/(app)/add/scan."*

## 1. Design system
- **Feel:** a campus community app crossed with chat and a light marketplace. Friendly, rounded, immediate. **Not** an e-commerce catalog.
- **Tokens** (CSS variables mapped in Tailwind):
  - primary emerald-600 `#059669` (hover emerald-700); primary-soft emerald-50
  - accent amber-400 `#FBBF24`, for points and badges
  - ink stone-900 `#1C1917`; muted stone-500
  - background `#FAFAF9`; card white
  - danger rose-600
  - radius: cards `rounded-2xl`, buttons `rounded-full`
  - soft shadows (`shadow-sm`)
- **Type:** Inter. Page titles 22/28 semibold, section headers 17 semibold, body 15, meta 13 stone-500.
- **Layout:** mobile-first. Content is `max-w-md mx-auto px-4`; desktop shows the same centered column. Test at 360, 390, and 430 px widths.
- **Mobile checklist** (applies to every screen, including C's scan pages):
  - **Notches and home bars:** the bottom nav and sticky bars respect safe areas. Use `viewport-fit=cover` with `padding-bottom: env(safe-area-inset-bottom)`.
  - **Full-height screens** use `100dvh`, not `100vh`, so the browser toolbar doesn't cut them off.
  - **Text inputs** use font size ≥ 16 px, otherwise iPhone Safari zooms in when you tap them.
  - **The keyboard** never hides the composer or the primary button; they stay visible while typing.
  - **Touch:** nothing depends on hover. Tap targets are ≥ 44 px, with nothing important at the very screen edges.
  - **Images:** lazy-load them, and show emoji tiles while they load, so slow campus Wi-Fi still feels fast.
- **Bottom nav:** Home · Explore · **Add** (a raised round primary button with a camera-plus icon) · Communities · Profile.
- **Top bar:** the DAHA wordmark, a dorm chip, a bell (unread badge), and a chat icon (unread badge).
- **Chips:**
  - type: Lend = emerald, Free = amber, Swap = sky
  - status: Available / Reserved / Lent out / Unavailable
  - category chips use the emoji from `PLAN.md` §9
- **Shared components** (B owns them; C may use them):
  - `ItemCard`: square thumbnail, or a category emoji tile on a soft tint; name; type chip; "2 min · Wilbur"; owner avatar
  - `ItemThumb`; `RequestCard` (chat-bubble style: avatar + name + dorm + time ago; bubble with `raw_text`; chips for item, date, and duration; footer "3 matches nearby" + **I have this**)
  - `UserChip`, `DistanceChip`, `TxTypeChip`, `StatusBadge`, `CategoryChips`, `FilterSheet`, `EmptyState`, `SectionHeader`, skeletons
  - `TransactionCard`: a stepper (Requested/Offered → Accepted → Handed off → Returned/Completed) with one button per entry in `allowed_actions`
  - `Composer`: chat-style input with a send button
- **Action labels:**
  - `accept` "Accept" · `decline` "Decline" · `cancel` "Cancel"
  - `hand_off`: "Mark handed off" (lend) or "Mark given" (give/exchange)
  - `mark_returned` "Got it back"
- **Copy:** short and warm, e.g. "Nobody's listed that yet — ask your dorm?"
- **States:** every list has a skeleton, an empty state with a next action, and an error with a retry. Mutations show toasts.

## 2. Screens (route → owner → data → must-haves)
| Route | Owner | Data | Must-haves |
|---|---|---|---|
| `/login` | B | `auth.login`, `auth.demoUsers`, `auth.demoLogin` | email + password; a "Try a demo account" list with one-tap login (when `NEXT_PUBLIC_DEMO_MODE`); link to signup; honors `?next=` |
| `/signup` | B | `auth.signup`, `communities.list({kind:'dorm'})`, `me.update` | two steps: name, `@stanford.edu` email (inline hint), password → then a searchable dorm picker (`PATCH /me {dorm_id}`); reads `?dorm=<slug>&ref=<id>` from invite links (the dorm is preselected); then goes to `/onboarding` |
| `/onboarding` | **C** | | (C's scan flow in first-run mode) |
| `/home` | B | `feed.home` | greeting; a big gradient scan card when `show_scan_cta` ("Show us what you have — snap your desk, we'll list it") → `/add/scan`, and a slim "Snap more" banner after that; **You could help** (horizontal cards: request + your matching item + Offer); **Requests near you** (`RequestCard` list); **New near you** (2-column `ItemCard` grid); a stats line ("Wilbur has 124 things to share") |
| `/explore` | B | `search.search` | search bar with rotating example placeholders (the 5 demo queries); category chips; a My dorm / Campus toggle; `FilterSheet` (walking 5/10/15/30/any, type, condition, available only); "Understood:" chips from `parsed.chips`; tabs Items / Requests / Communities; "Load more"; the empty state offers **Ask for it** → `/add/request?text=<q>` |
| `/add` | B | | three big options: 📸 Snap your stuff (AI lists it) → `/add/scan` · 📝 List one item → `/add/item` · 🙋 Ask for something → `/add/request` |
| `/add/scan` | **C** | | (C's scan flow) |
| `/add/item` | B | `uploads.create`, `items.create`, `places.list`, `me` | photos (optional, ≤ 6); name, category, description, quantity, condition, type (services can't be Lend); max lend days (Lend only); availability dates; visibility (My dorm by default / Campus / Groups multi-select / **Private: only me, ping me if someone needs it**); pickup spot + private note ("only shared after you accept"). Submits to the item page |
| `/add/request` | B | `ai.parseRequest` (debounced 400 ms), `requests.create` | a big "What do you need?" box with examples; live editable chips (item, category, date, duration, type); visibility (defaults to My dorm; `?community=<id>` presets a group); if `kind=offer`, a banner "Looks like you're offering something — list it instead?" → `/add/item` prefilled. On post, go to the request page |
| `/items/[id]` | B | `items.get`, `items.borrow`, `conversations.direct` | image carousel or emoji tile; chips; status; distance + community; owner card (level, rating, completed count) → `/u/[id]`; description; availability; pickup spot name only. Primary action by type: Request to borrow / Ask for it / Propose swap, via a sheet with message + dates → `/messages/[conv]`. "Message" button. If mine: Edit, availability toggle, Delete |
| `/requests/[id]` | B | `requests.get`, `matches.get` (poll 2 s while `pending`, max 30 s), `requests.offer`, `transactions.action` | the requester's bubble + chips + status; **Available now** match list (the requester can tap "Ask to borrow", which sends `borrow` with `request_id`). When `private_pinged_count` > 0, show a quiet line "Quietly asked N people nearby who said they have one", with no names; **I can help** sheet for others: pick one of my items (my matching items first) **or** "I have one that's not listed" (name prefilled; photo optional; "also add to my shared stuff" on by default); offers list with Accept/Decline for the requester; Share (copy `share_url`); Mark fulfilled / Cancel |
| `/r/[id]` | B | | redirects to `/requests/[id]`, via login if needed |
| `/communities` | B | `communities.list({mine})`, `communities.list({kind:'group', q})`, `communities.create`, `communities.join` | Your dorm (big card); Your groups; Discover groups (search); Create group sheet (name, type, description, private; shows the join code afterwards); Join with code |
| `/communities/[slug]` | B | `communities.get`, `feed.community`, `communities.members` | header (emoji, name, member and item counts, Join/Leave, invite link); tabs **Channel** (a chat-like timeline: requests as bubbles, items as "Maya shared a desk lamp" cards) · **Inventory** · **Requests** · **Members**; a bottom composer "Ask {name} for something…" → `/add/request?community=<id>&text=…` |
| `/messages` | B | `conversations.list` (poll 10 s) | avatar, name, last message, item chip, unread dot |
| `/messages/[id]` | B | `conversations.get`, `conversations.messages` (poll 3 s with `after_id`), `transactions.get`, `transactions.action`, `transactions.review` | `TransactionCard` pinned on top; messages (system messages centered and gray); composer; mark read on open; a review sheet (stars + text) when `can_review` |
| `/profile` | B | `me`, `me.items`, `me.requests`, `transactions.list`, `users.reviews` | header: avatar, name, dorm, level progress bar, points, badges, rating. Tabs: Inventory (**Shared** and **Private** sections; status toggle; a "ping me" toggle for private items; edit; "+ Snap more"), Requests, Activity (active/past, by role), Reviews. Settings: walking radius slider, change dorm, invite link, Feedback (→ `events` `feedback_submitted`), log out |
| `/u/[id]` | B | `users.get`, `users.items`, `users.reviews` | public header + their shared items + reviews + Message |
| `/notifications` | B | `notifications.list`, `notifications.markRead` | list with icons per type; tapping follows `link`. A `private_match` shows **Help anonymously**, which opens the request with the offer sheet and that item preselected (`?offer_item=<id>`); "Mark all read". The bell badge polls `unread-count` every 20 s |

## ✅ B1 — Mock layer + auth + home + shared components
- **`src/lib/api/mock/db.ts`:**
  - in-memory fixtures: ≥ 4 dorms, 2 groups, 10 users, 30 items across categories, 10 requests in casual phrasing, 3 transactions with conversations
  - persisted to `localStorage["daha_mock_db"]`
  - a "Reset demo data" button in the Profile footer when mocked
- **Mock handlers** for every domain except `scans` (C):
  - they follow §7 semantics, including `allowed_actions` from `PLAN.md` §7.7, visibility, and `pickup_note` privacy
  - simple stand-ins for search, feed, matches, and ai (keyword match; a regex parse)
  - latency of 150–400 ms
- **Auth pages**, `AuthGate`, logout, 401 handling. **Home.** The shared components from §1.

Checkpoint: *"B1 ✅ app runs fully on mock data: login (demo users), signup, home."*

## ✅ B2 — Explore & search UI
Implement `/explore` per §2. Sync the URL with the query and filters (`?q=&category=&scope=`) so results are shareable. Fire `search_performed` and `search_result_clicked` events.

## ✅ B3 — Add menu, manual listing, request composer, item page + borrow
Implement `/add`, `/add/item`, `/add/request`, and `/items/[id]` per §2. Downscale photos in the browser before uploading (canvas, longest side ≤ 1600 px, JPEG 0.85). C writes a shared helper `downscaleImage` in `src/components/scan/downscale.ts`; import it if it exists, otherwise write it in `src/lib/image.ts`. Fire `request_composer_opened` and `request_posted`.

## ✅ B4 — Request page, offers, chat, transaction card, reviews
Implement `/requests/[id]`, `/r/[id]`, `/messages`, `/messages/[id]`, `TransactionCard`, and the review sheet. Use optimistic UI for sending messages. Fire `offer_sent` and `share_clicked`.

## ✅ B5 — Communities, profile, public profile, notifications, invites
Implement `/communities`, `/communities/[slug]`, `/profile`, `/u/[id]`, `/notifications`, and the bell and chat badges. The invite link is `${origin}/signup?dorm=<slug>&ref=<me.id>`. Fire `invite_copied` and `feedback_submitted`.

## ✅ B6 — Polish + go live (shipped as B6a #12 and B6b #15)
- **States:** loading, empty, and error states everywhere; toasts; skeletons.
- **Accessibility:** labels, focus rings, 44 px tap targets, contrast.
- **Phone QA:** at 360, 390, and 430 px widths, and in Safari and Chrome on a real phone.
- **Go live:** as A and C checkpoints land, remove those domains from `NEXT_PUBLIC_MOCK`. Then do a full pass with `NEXT_PUBLIC_MOCK=none` against `make seed` data and fix contract mismatches: report them to the owner, don't hack around them.
- **Contract check:** `pnpm dlx openapi-typescript http://localhost:8000/openapi.json -o /tmp/openapi.d.ts`, then compare nullability and enums with `types.ts`. Report differences in the group chat.

Checkpoint: *"B6 ✅ all screens done and running live (NEXT_PUBLIC_MOCK=none). Phase 1 done (B)."*

## ✅ B7 — Installable app (accepted proposal `docs/proposals/B-pwa.md`, Part 1 only)
Additive task, `PLAN.md` §2 P1 item 5. `web/src/app/manifest.ts` (standalone, `start_url=/home`, theme colors from §1); PNG icons in `web/public/icons/` (192, 512, maskable 512, Apple 180, favicon 48); `appleWebApp` metadata; an "Install DAHA" card on Profile (Install button via `beforeinstallprompt`, 2-step hint on iPhone, hidden when installed or dismissed); `BackButton` on item, request, user and community pages. No service worker, no push (Part 2 rejected for the hackathon).

## Phase 2 & 3 (B)
Fix issues labeled `B` during integration. Then do UX iteration from feedback (`plans/INTEGRATION.md` §3.5) and the P1 items: the PWA manifest and the Playwright smoke test.

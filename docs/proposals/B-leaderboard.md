# Opt-in leaderboard with podium awards (PLAN.md §2 P1 #7)
- Status: new (web built against a stand-in; needs A's endpoints and everyone's 👍 for the contract addition)
- Author: Person B · Date: 2026-11-18
- Problem it solves: points exist but nobody sees them outside their own profile. A weekly board and a dorm-vs-dorm ranking give people a fun reason to lend, and the three podium awards make good demo moments.
- Proposal (web is done; the backend part is for A):
  - **Web (built, `feature/aha-xmas`):** `/leaderboard` with *This week* / *All time* tabs, a podium (🥇 The Karma GOAT · 🥈 The Plug · 🥉 Certified Good Egg), ranks 4–10, *Dorm vs dorm*, and a "Show me on the leaderboard" switch with a nickname. Profile shows your own award and a link. Code: `web/src/lib/api/leaderboard.ts` (proposed types + calls + a clearly marked stand-in), `web/src/app/(app)/leaderboard/page.tsx`.
  - **Stand-in:** each call tries the real endpoint first. On 404 the screen shows sample data with a "Sample rankings for now" note, and the opt-in choice is kept on the phone only. When A's endpoints land, real data shows with no web change.
  - **What A must add** (additive only; nothing existing changes):
    1. **Columns on `users`** (migration): `leaderboard_opt_in bool NOT NULL DEFAULT false`, `leaderboard_nickname text NULL` (2–20 chars: letters, digits, space, `_`, `-`; unique, case-insensitive).
    2. **`PUT /api/me/leaderboard`** body `{opted_in: boolean, nickname: string | null}` → `LeaderboardMe`.
       - 422 if `opted_in` is true and the nickname is missing or invalid.
       - 422 if the nickname contains any part of the person's real name (2+ letters).
       - 409 "That nickname is taken".
       - Turning it off keeps the nickname for later.
    3. **`GET /api/leaderboard?period=week|all`** → `Leaderboard`:
       ```ts
       type LeaderboardPeriod = "week" | "all";
       type PodiumAward = "gold" | "silver" | "bronze";
       interface LeaderboardEntry { rank: number; nickname: string; dorm_name: string | null; points: number; exchanges: number; award: PodiumAward | null; is_me: boolean }
       interface DormRank { rank: number; community_id: ID; dorm_name: string; emoji: string | null; points: number; people: number }
       interface LeaderboardMe { opted_in: boolean; nickname: string | null; rank: number | null; points: number; award: PodiumAward | null }
       interface Leaderboard { period: LeaderboardPeriod; since: ISODateTime | null; people: LeaderboardEntry[]; dorms: DormRank[]; me: LeaderboardMe }
       ```
    4. **Scoring rules:**
       - **What counts:** only points from **completed transactions** (`points_ledger` rows with `ref_type = 'transaction'`). That covers lend +10, give +15, exchange +10, request bonus +5 and borrow +2. Item-publish points and review points don't count.
       - **Different people only:**
         - The other party must be a different user.
         - Each **(person, other party) pair counts at most once per week**: the first completed transaction between them that week.
         - "All time" adds up the weekly results, so trading back and forth with one friend can't farm points.
       - **Weeks:** "this week" starts Monday 00:00 America/Los_Angeles, and `since` is that moment in UTC.
       - **Who's on the board:** `people` holds the top 10 **opted-in** users with points > 0. Ties are broken by more distinct partners, then by who reached the score first. `award` goes to ranks 1–3.
       - **Dorms:** `dorms` adds up the qualifying points of **all** members of each dorm, opted in or not, and lists no individuals. `people` is the member count with points > 0. Sorted by points; dorms with 0 points are left out.
       - **`me`:** your own row whether or not you're opted in (`rank` is null when you're off the board or outside the top 10).
    5. **Privacy:**
       - The response never contains real names, user ids or avatars of other people.
       - Not in search, and nothing is logged beyond the usual request log.
    6. **Seed:** opt in about 8 demo users with nicknames, so the board isn't empty in the demo. Keep **Maya** opted out, so the demo can show joining.
    7. **Contract:** add the above to `PLAN.md` §7.2/§7.3 and `backend/app/schemas/`. B then moves the types from `leaderboard.ts` into `types.ts` and deletes the stand-in.
- Cost: free. No services or libraries.
- Effort: A ~1.5–2 h (migration, 2 endpoints, tests, seed). B: done; ~15 min to remove the stand-in afterwards.
- Keys / accounts needed: none.
- Risks / privacy:
  - **Opt-in by default** (PLAN.md says "opt-in"). Nobody appears until they choose a nickname and turn it on.
  - **Awards are shown only on your own profile,** not on public profiles. Public profiles show real names, so showing awards there would reveal who is behind each nickname.
  - A small dorm with one active person makes the dorm total close to personal. That's acceptable for the demo; a minimum of 3 people per dorm could be added later.
- Recommendation: accept. A builds items 1–7 after integration fixes. Until then the web stand-in keeps the demo working.

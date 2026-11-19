# Demo video: shot list (B records Thu morning, ≤ 3 min)
Follows `plans/INTEGRATION.md` §3.2 and the demo script in `PLAN.md` §10. Times are targets; the total stays under 3:00.

## Before you record (~10 min)
- [ ] `git pull`, then `make migrate` and **`make seed`**. Fresh data: the binder request, Maya's binder, the bike pump flow.
- [ ] Restart `make web` after pulling (it can keep old colors otherwise), then open the phone link once to check it's red and green.
- [ ] Photo AI:
  - The real one (`AI_PROVIDER=harnessrouter` in `backend/.env`) looks best, but each scan is a paid call. Ask the key holder first and keep it to 2–3 takes.
  - `mock` is free, but the items it "finds" are made up, so don't let the video claim it recognised your desk.
- [ ] Two devices:
  - **Phone A** (recording): Sam, a new signup in Wilbur.
  - **Phone B or the laptop**: Jordan (FloMo) and Maya (Wilbur), switched with the one-tap demo login.
- [ ] Phone recording:
  - iPhone: Control Center → Screen Recording.
  - Android: Quick Settings → Screen record.
  - Turn on Do Not Disturb, set brightness high, set the time to something clean, close other apps.
- [ ] A real desk or shelf with 5+ everyday things. No faces, documents, cards, keys or screens with personal info.

## Shot list
| # | Time | Screen | What happens | Say (short and warm) |
|---|---|---|---|---|
| 1 | 0:00–0:15 | A dorm group chat mock-up, or just talking to camera | The problem | "Need a binder tonight? Today you post in a 400-person group chat and hope. Most of what you need is already down the hall." |
| 2 | 0:15–0:25 | Phone A: signup → "Show us what you have" | Sam joins Wilbur | "Sam just moved into Wilbur." |
| 3 | 0:25–1:05 | Phone A: 2 photos → review → untick one, rename one → **My dorm · Lend** → **Share** | Scan a desk, items appear, share in one tap; points pop | "Two photos. DAHA lists what it sees, Sam picks what to share, and it's live for the dorm." |
| 4 | 1:05–1:40 | Phone B as Jordan: "anyone have a black binder I can borrow next Wednesday?" → **Who sees it → Campus** → Post | Chips appear, then "Available now" lists binders | "Jordan in FloMo asks in plain words. DAHA understands it and finds binders nearby, with walking time." |
| 5 | 1:40–2:05 | Maya: the notification → **I can help** → offer → Jordan **Accept** → one chat message | Offer, accept, chat | "Maya gets a nudge, offers hers, and they sort out the handoff in chat." |
| 6 | 2:05–2:25 | Laptop: Explore, "graphing calculator near me" | Same-dorm calculators first, with minutes | "Search works like you talk." |
| 7 | 2:25–2:45 | Jordan: "anyone have a bike pump?" → "Quietly asked N people nearby"; Phone A shows Sam's anonymous ping | Private "I have this" | "Sam never listed the pump publicly. DAHA quietly asks, and Jordan never sees who until Sam offers." |
| 8 | 2:45–3:00 | Phone: Home or Leaderboard | What's next | "Next: dorm-vs-dorm leaderboards, reminders, and more campuses. Borrow it from down the hall." |

## Gotchas
- **Step 4:** Jordan must pick **Campus**. The default is My dorm, and Maya (Wilbur) can't see a FloMo-only request.
- **Step 8:** the leaderboard still shows **sample** rankings (with a "Sample rankings for now" note) until A's backend lands. Show it only as "what's next", or skip it.
- Keep the AI wait in the cut. Speed up or trim the gap while the scan runs; the voiceover can carry it.
- Matched-neighbor cards ("You two can help each other") show only if the server has `MUTUAL_MATCHING` on. They're optional; skip them if they're not visible.

## After recording
- [ ] Trim to ≤ 3:00, add the voiceover, export at 1080p.
- [ ] Upload as **YouTube unlisted** or Google Drive ("anyone with the link"). Send the link to C for the README (`plans/INTEGRATION.md` §3.3).
- [ ] Take 5 phone screenshots for the README: home, scan review, request with matches, chat, search.

# DAHA: share stuff across campus

DAHA is a Stanford-wide app for lending, borrowing, giving away, and swapping everyday things and services. Think of the dorm group chat ("anyone have a calculator?") with three upgrades: everything is searchable, a single photo is enough to list your stuff, and a request reaches the people who actually have the item.

**The three moments that matter**
1. **"Show us what you have."** Take a photo of your desk or closet and the AI lists the items in it. You tick what you're happy to share and post everything with one tap, in under 60 seconds.
2. **"Anyone have a black binder I can borrow next Wednesday?"** DAHA understands the request, shows matching items nearby (your dorm first), and pings their owners. If nobody has listed one yet, someone can offer one they own.
3. **Borrow → hand off → return → review.** A simple flow with chat, plus points and badges for people who help.

---

## What the first version (the MVP) includes
- Sign up with a Stanford email and pick your dorm.
- Photo scan → AI-detected items → review → share in one tap. You can also list a single item by hand.
- Ask for things in plain English. Offer your items to other people's requests.
- Search ("graphing calculator near me", "formal clothes for an interview") with filters.
- Dorm and group pages that feel like a chat channel, plus each community's shared inventory.
- Chat, notifications, reviews, points, and badges.
- Privacy built in: dorm-level location only, photo metadata (EXIF) removed, pickup details shown only after both people agree, and the AI never posts anything without your OK.

**Not in the MVP:** payments, Stanford single sign-on, push or email notifications, native iPhone or Android apps.

---

## How it's set up (plain English)

```
 Your phone / laptop
        │
        ▼
 ┌──────────────┐    ┌──────────────────┐    ┌─────────────────────────┐
 │  Web app     │ ─▶ │  Backend server  │ ─▶ │  Database (Postgres)    │
 │  (what you   │    │  (rules, data,   │    │  users, items, requests │
 │   see)       │    │   search, AI     │    └─────────────────────────┘
 │  Person B    │    │   glue)  A + C   │ ─▶  HarnessRouter (AI that reads photos)
 └──────────────┘    └──────────────────┘     uses our $50 credit, Person C
```
- **Web app** (`web/`): the screens. It works on a phone browser, no app store needed.
- **Backend** (`backend/`): stores everything, enforces privacy rules, runs search and matching.
- **AI**: photos go to **HarnessRouter**, where our $50 credit lives, and the AI returns a list of items. Search uses a free AI model that runs on our own machine.
- Everything runs on a laptop first (`localhost`). We put it online later.

For the technical version, see `ARCHITECTURE.md`.

---

## The team split

| Person | Builds | Your human to-dos (Claude will remind you) |
|---|---|---|
| **A: Backend & setup** | the database, the server, login, borrowing and returning, chat, notifications, points, fake demo data, putting the app online | ☐ Invite B and C to the GitHub repo (`4ndrelim/Daha`) · ☐ make a secret key for `.env` (Claude shows you how) · ☐ merge PRs · ☐ later: set up hosting |
| **B: The app screens** | every screen (home, search, item pages, requests, chat, communities, profile) and how it looks; B can start right away using fake data | ☐ Check how it looks on your phone · ☐ give taste feedback (colors, wording) · ☐ optional: screenshots of real dorm-chat requests (names blurred) · ☐ merge PRs |
| **C: AI, search & photo scan** | the photo → items AI (HarnessRouter), the scan screens, search, matching requests to items, home feed | ☐ Get the HarnessRouter API key ($50 credit) · ☐ take 20–30 photos of desks, closets, and kitchens (no faces or documents) · ☐ choose the AI model with the team after the cost test · ☐ **lead integration and evals** |

**Can one person do everything?** Yes. Tell Claude "I'm doing all roles — follow Solo mode." It's slower but it works.
**Only two people?** One takes A and C's backend parts; the other takes B and C's scan screens (see `PLAN.md` §11).

---

## How we work (no git knowledge needed)
1. **Install once:** Git, GitHub CLI, Docker Desktop, Node.js 20+ (with pnpm), Python 3.12 (with uv), and Claude Code. Not sure how? Ask Claude: *"Check what I'm missing to work on this repo and help me install it."*
2. **Get the code:** accept the GitHub invite (check your email), run `gh repo clone 4ndrelim/Daha`, then open the `Daha` folder in Claude Code.
3. **Start:** say ***"I am Person B"*** (or A, or C). Claude loads the rules by itself, shows your to-do list, and starts your next task.
4. **Let Claude work.** It saves work on its own branch and opens a Pull Request (PR) when a piece is done.
5. **Merge:** open the PR link Claude gives you, skim it, and press **Merge**. Then paste Claude's ✅ message into the group chat.
6. **Next day:** say ***"Sync with main and continue my plan."***

Full details are in `CONTRIBUTING.md`.

---

## Timeline
| Phase | Who | What happens | Done when |
|---|---|---|---|
| **0. Setup** (about 2 h) | A (repo and backend skeleton), B (app skeleton), C (HarnessRouter cost test) | The skeleton exists and everyone can run it | A and B both post "Phase 0 merged" |
| **1. Build** (in parallel) | A, B, C separately | Each person builds their part. B uses fake data until A and C are ready | Each person posts "Phase 1 done" |
| **2. Integrate** (about 2–3 h, together) | **C drives**; A and B fix their parts live | Connect everything, run the demo script on real phones, fix bugs | The demo script passes; tag `v0.1-mvp` |
| **3. Demo & learn** (1–2 weeks) | A: put it online · B: polish from feedback · C: evals | Friends try it and we measure what works | Feedback and an eval report are in |
| **4. Smarter** (later) | Whoever's excited | ML, RL, and agent features using real usage data | See `plans/ROADMAP.md` |

---

## After the MVP: what's next
1. **Integration (C leads).** C runs the whole app on one laptop and walks through the demo. Whatever breaks goes back to its owner (A, B, or C) to fix. Then we tag the first version.
2. **Demo for feedback.** We share a temporary link from that laptop (free, about 1 minute to set up). 5–15 friends try it while we watch them do the photo scan, followed by a 5-question form.
3. **Online for real (A).** A small cloud server, about $6 a month (often free with student credits), running the same setup.
4. **Evals (C).** We score how well the AI does on our own photos and requests: did it find the right items, did search rank the right things first, how long it took, and what it cost. We improve the AI and re-run. Details are in `plans/EVALS.md`.
5. **ML and RL (later).** Every scan, edit, search, and borrow is logged, so we can train smarter ranking and learn whom to notify. We can also learn from users' corrections and build a campus assistant agent. See `plans/ROADMAP.md`.

---

## Money & secrets
- **$50 HarnessRouter credit** pays only for photo detection. Dev and tests use a free fake AI. C holds the key.
- Keys live only in `backend/.env`, which git ignores. **Never** paste keys into chat, screenshots, or code.
- Claude stops photo AI spending at $40 by default, keeping $10 for evals.

## Where things are
`README.md` (you are here) · `docs/PRODUCT_BRIEF.md` (the full product idea) · `CONTRIBUTING.md` (how to work) · `ARCHITECTURE.md` (diagrams) · `PLAN.md` (technical plan) · `plans/` (per-person plans, integration, evals, roadmap) · `AGENTS.md` (rules for Claude)

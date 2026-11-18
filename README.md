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
- Privately tick things you own (bike pump, tool kit…). Nobody sees your list, but DAHA quietly pings you when someone nearby needs one.
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
- **Everything in one command:** `make up` runs the database, backend, and web app in Docker (open http://localhost:3000); `make down` stops it. Every pull request is checked automatically (GitHub Actions).

For the technical version, see `ARCHITECTURE.md`.

---

## The team split

| Person | Builds | Your human to-dos (Claude will remind you) |
|---|---|---|
| **A: Backend & setup** | the database, the server, login, borrowing and returning, chat, notifications, points, fake demo data, putting the app online | ☐ Make a secret key for `.env` (Claude shows you how) · ☐ merge PRs · ☐ later: set up hosting |
| **B: The app screens** | every screen (home, search, item pages, requests, chat, communities, profile) and how it looks; B can start right away using fake data | ☐ Check how it looks on your phone · ☐ give taste feedback (colors, wording) · ☐ optional: screenshots of real dorm-chat requests (names blurred) · ☐ merge PRs |
| **C: AI, search & photo scan** | the photo → items AI (HarnessRouter), the scan screens, search, matching requests to items, home feed | ☐ Get the HarnessRouter API key ($50 team credit; ask the account holder) · ☐ take 20–30 photos of desks, closets, and kitchens (no faces or documents) · ☐ choose the AI model with the team after the cost test · ☐ **lead integration and evals** |

**Can one person do everything?** Yes. Pick **Solo** when Claude asks for your role. It's slower but it works.
**Only two people?** One takes A and C's backend parts; the other takes B and C's scan screens (see `PLAN.md` §11).

---

## How we work (no git knowledge needed)
1. **Install once:** Git, GitHub CLI, Docker Desktop, Node.js 20+ (with pnpm), Python 3.12 (with uv), and Claude Code. Not sure how? Claude helps in step 3.
2. **Get the code:** accept the GitHub invite (check your email), run `gh repo clone 4ndrelim/Daha`, then open the `Daha` folder in Claude Code.
3. **Say anything**, e.g. ***"Understand the docs and begin."*** Plan on **5–10 minutes** together. Claude will:
   - ask which role you're taking: A, B, C, or all of them (Solo);
   - ask how involved you want to be:
     - **hands-off:** it builds your plan as written;
     - **involved:** it walks you through the design choices first, so you can change things;
   - help you set up: tools, keys, accounts;
   - show what it will build, phase by phase.
4. **Approve, then switch Claude to auto mode** (Claude shows you how). It works on its own branch and opens Pull Requests (PRs) as pieces finish.
5. **Merge:** open the PR link and press **Merge**. If you told Claude it can merge its own PRs, it does this itself. Then paste Claude's ✅ message into the group chat.
6. **Next time:** open Claude in the folder and say ***"continue"***. It remembers your role and mode, and shows you anything it researched for you (see "Extra APIs & ideas" below).

Full details are in `CONTRIBUTING.md`.

---

## Timeline (hackathon: submit by **Thu Nov 19, 12:00**)
| When | What | Who |
|---|---|---|
| **Tue morning**, by ~11:00 | Kickoff with Claude (10 min each), skeletons, HarnessRouter test | A, B, C |
| **Tue → Wed afternoon** | Build in parallel. Leave Claude running in auto mode overnight if you can | A, B, C |
| **Wed 18:00** | **Feature freeze**, then integrate together (~3–4 h; C drives) and tag `v0.1-mvp` | everyone |
| **Wed night** | 3–5 friends try it through a temporary link. Note the top bugs | C hosts, everyone watches |
| **Thu 08:00–10:30** | Fix the top bugs · record the demo video · get quick AI numbers for the pitch | A/C fix · B: video · C: numbers |
| **Thu 10:30–11:30** | Submission: write-up, video, screenshots, repo link. **Submit by 11:30** (30-minute buffer) | C submits, everyone reviews |

Per-person target times, and what gets cut if we fall behind: `PLAN.md` §0.

---

## After the hackathon (beyond the hackathon scope; good next steps)
1. **Online for real (A).** A small cloud server, about $6 a month (often free with student credits), running the same setup so the app stays up. *Beyond the hackathon scope.* For Thursday, the temporary link plus the demo video is enough.
2. **A week of real feedback.** Dorm-mates use it, fill in a 5-question form, and we fix the top 5 issues each week.
3. **Full evals (C).** Score the AI on 20–30 of our own photos and requests: did it find the right items, did search rank the right things first, speed, cost. Then improve and re-run (`plans/EVALS.md`).
4. **Follow-ups from feedback:** the personal inventory keeper and declutter mode (`plans/C-ai-discovery.md` F1–F3), plus the P1 list in `PLAN.md` §2.
5. **ML and RL (later).** Every scan, edit, search, and borrow is logged, so we can train smarter ranking, learn whom to notify, learn from users' corrections, and build a campus assistant agent (`plans/ROADMAP.md`).

---

## Extra APIs & ideas
Claude may find APIs or services that would make DAHA a lot better, such as web search. It won't stop building to add them. Instead it writes a short proposal in `docs/proposals/` (what it is, why it helps, cost, effort) and shows you at the start of your next session. You decide: accept, defer, or reject. Nothing paid is ever added without your OK.

**Team keys (who to ask):**
- HarnessRouter ($50 team credit, photo AI): the team account holder; ask in the group.
- **Web search API: tag Andre.**

## Money & secrets
- **$50 HarnessRouter credit** pays only for photo detection. Dev and tests use a free fake AI. Person C uses the key.
- Keys live only in `backend/.env`, which git ignores. **Never** paste keys into the group chat, screenshots, or code. Share them privately.
- Claude stops photo AI spending at $40 by default, keeping $10 for evals.

## Where things are
`README.md` (you are here) · `docs/PRODUCT_BRIEF.md` (the full product idea) · `CONTRIBUTING.md` (how to work) · `ARCHITECTURE.md` (diagrams) · `PLAN.md` (technical plan) · `plans/` (per-person plans, integration, evals, roadmap) · `docs/proposals/` (ideas Claude found for you to review) · `docs/research/` (deeper research, e.g. more HarnessRouter workflows) · `AGENTS.md` (rules for Claude)

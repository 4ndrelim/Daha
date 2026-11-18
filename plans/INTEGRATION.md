# Integration (Phase 2) and the hackathon finish (Phase 3)

> **Status (2026-11-17):** the demo script (`PLAN.md` §10, steps 1–9) passed headless on fresh seed data with `NEXT_PUBLIC_MOCK=none` (B6b, PR #15), and `make up` + CI exist (A5). Not done yet: a full run with `AI_PROVIDER=harnessrouter` (the keys are verified; `docs/ai-spike.md`), the two-phone pass, and the `v0.1-mvp` tag. Phones need the **https** tunnel link (§3.1) for location (`plans/LOCATION.md`); `make lan` links are plain http. After this checklist, the work continues in the weekly loop at the end of this file: this is where iteration starts, not where the project ends.

**Integration lead: Person C.** C's laptop holds the HarnessRouter key, and C's work spans backend and frontend. A and B join the session, live or on a call, and their Claudes fix issues in their own areas.

## 🧑 Human TODOs
- [ ] **All:** block **Wed 18:00–22:00** for integration, in person or on a call, and bring your phone.
- [ ] **C:** host it. Have Docker running and `backend/.env` filled in, with `AI_PROVIDER=harnessrouter`.
- [ ] **A and B:** keep Claude open on your own laptops to fix issues labeled with your letter.
- [ ] **After the session:** C posts the `v0.1-mvp` message. Thursday morning is polish and submission (§3.2–§3.3).

## Phase 2: integration checklist (C's Claude runs it top to bottom; do the steps in order)
1. **Feature freeze (Wed 18:00).** Everyone merges their open PRs. After this, only fixes.
2. **Fresh clone** into a new folder. Follow `README.md` from zero, and fix any doc step that fails (that's a docs PR).
3. **Start live:**
   - `make db migrate seed`
   - terminal 1: `make api` with `AI_PROVIDER=harnessrouter`, `EMBEDDINGS_PROVIDER=fastembed`
   - terminal 2: `make web` with `NEXT_PUBLIC_MOCK=none`
   - `make reindex`
4. **API smoke:** `make smoke` must be all ✅. Each ❌ becomes a GitHub issue for its owner.
5. **Contract diff:** `pnpm dlx openapi-typescript http://localhost:8000/openapi.json -o /tmp/openapi.d.ts`, then compare it with `web/src/lib/api/types.ts` for nullability, enum strings, and missing fields. The owner of the wrong side fixes it.
6. **Demo script** (`PLAN.md` §10): first on desktop, then on two phones (`make lan` → `http://<ip>:3000`). Each bug becomes an issue: `gh issue create --label A|B|C --title … --body "<steps> / <expected> / <actual>"`. Owners fix it and C re-tests.
7. **Privacy & safety pass:**
   - a dorm-only item is invisible to another dorm (search plus direct URL → 404)
   - the pickup note stays hidden until a transaction is accepted
   - an uploaded photo has no EXIF data (`exiftool` or Pillow)
   - `grep -r "sk-hr" web/.next web/src` finds nothing
   - logs contain no keys
8. **Performance:** search p95 < 300 ms (from `search_logs.latency_ms`); home < 500 ms; record scan seconds per photo.
9. **Tag:** `git tag v0.1-mvp && git push --tags`. C posts: *"v0.1-mvp ✅ — demo script passes. Next: quick demo with friends (§3.1), then Thursday polish and submission."*

## Phase 3: hackathon finish (Wed night → submit by Thu 11:30)
### 3.1 Quick demo with friends (Wed night, ~1 h, C hosts)
- Install `cloudflared` (`brew install cloudflared`), then run `cloudflared tunnel --url http://localhost:3000`. It prints a temporary `https://….trycloudflare.com` link that works while C's laptop is running.
- With `DEMO_MODE=true`, have 3–5 friends try the photo scan and a request on their phones. Time "first photo → items shared" and watch where they hesitate.
- Ask them three questions:
  1. Was anything confusing?
  2. Did the AI get your stuff right?
  3. Would you use this instead of the dorm group chat?
- Turn the findings into GitHub issues labeled `feedback` plus `A`, `B`, or `C`. Pick the top 5 for Thursday.

### 3.2 Polish (Thu 08:00–10:30)
- **A and C:** fix the top `feedback` and bug issues in your areas. Small PRs, same rules as always.
- **B:** UI polish from the feedback, then record the **demo video** (≤ 3 min: a phone screen recording plus the laptop):
  1. the problem: dorm group chats
  2. scan a desk → items shared in one tap
  3. "anyone have a black binder?" → matches + notification → offer → accept
  4. search: "graphing calculator near me"
  5. private "I have this" → anonymous ping
  6. what's next
- **C:** the mini-eval for the pitch (`plans/EVALS.md` → Hackathon mini-eval, ~45 min).
- **10:30: code freeze.** After this, only submission work.

### 3.3 Submission (Thu 10:30–11:30; submit by 11:30)
**C submits; A and B review.** Check the hackathon's own submission requirements first and adjust this list.
- [ ] `main` is clean, and the README top has the demo video link plus 3–5 screenshots: home, scan review, request with matches, chat, search.
- [ ] The demo video (B) is uploaded, e.g. YouTube unlisted or Drive, and linked.
- [ ] The write-up (C), about 300 words:
  - the problem
  - what we built
  - how it works (link `ARCHITECTURE.md`)
  - how we use HarnessRouter
  - three numbers from the mini-eval
  - what's next (`plans/ROADMAP.md`)
- [ ] A live-demo plan for judging: either the tunnel (C's laptop on, stack running) or the video, if judges don't need a live link.
- [ ] Team names and roles, then **submit by 11:30**. That leaves a 30-minute buffer for upload problems.

## After the hackathon (beyond the hackathon scope; good next steps)
### Online for real (A)
1. **VM:** create a small Ubuntu VM (1 vCPU, 2 GB; e.g. DigitalOcean, about $6/month, often free with GitHub Student Pack credit). Install Docker, then `git clone`. This needs A5 (Dockerfiles) first.
2. **Env:** fill `backend/.env` with production values: a new `JWT_SECRET`, `DEMO_MODE=false`, `PUBLIC_BASE_URL`, `AI_PROVIDER=harnessrouter`.
3. **Run:** `make up` (Docker Compose `full` profile), with **Caddy** in front for automatic HTTPS, on a domain or a free subdomain (e.g. DuckDNS).
4. **Backups:** a nightly `pg_dump` cron to a backup folder, kept for 7 days.
5. **Done when:** the deployed app passes demo-script steps 1–6 on a phone.

### A week of real feedback (B)
- The in-app **Feedback** button records `feedback_submitted` events. Also share a 5-question form:
  1. How long did it take to share your first items? Was anything confusing?
  2. Did the AI get your items right? What did it miss or get wrong?
  3. Would you use DAHA instead of the dorm group chat? Why or why not?
  4. What would you borrow or lend first?
  5. Did anything feel unsafe or too public?
- Triage weekly into a top-5 list of GitHub issues labeled `feedback`.

### Full evals (C)
Follow `plans/EVALS.md`: baseline → improve → re-run. Publish the report in `evals/reports/`.

### Iterate (weekly loop)
- **B:** UX fixes from the feedback top 5.
- **A:** backend and infra fixes, plus P1 items such as overdue reminders and the leaderboard.
- **C:** AI quality from the evals (prompt v2, ranking weights, match threshold) and the follow-ups F1–F3.
- Every week: merge, redeploy (`git pull && make up`), and post a short changelog in the chat.

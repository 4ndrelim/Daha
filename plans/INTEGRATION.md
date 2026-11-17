# Integration (Phase 2) and Demo → Feedback → Deploy (Phase 3)

**Integration lead: Person C.** C's laptop holds the HarnessRouter key, and C's work spans backend and frontend. A and B join the session, live or on a call, and their Claudes fix issues in their own areas.

## 🧑 Human TODOs
- [ ] **All:** pick a 2–3 hour slot after all three "Phase 1 done" messages, and bring your phone.
- [ ] **C:** host it. Have Docker running and `backend/.env` filled in, with `AI_PROVIDER=harnessrouter`.
- [ ] **A and B:** keep Claude open on your own laptops to fix issues labeled with your letter.
- [ ] **After the session:** C posts the `v0.1-mvp` message and A runs the deploy (§3.3).

## Phase 2: integration checklist (C's Claude runs it top to bottom; do the steps in order)
1. **Freeze.** Everyone merges their open PRs. After this, only fixes.
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
9. **Tag:** `git tag v0.1-mvp && git push --tags`. C posts: *"v0.1-mvp ✅ — demo script passes. Next: tunnel demo (§3.1) + deploy (A)."*

## Phase 3: the steps after the MVP, in order
### 3.1 Same-day demo link (C, about 10 minutes)
- Install `cloudflared` (`brew install cloudflared`), then run `cloudflared tunnel --url http://localhost:3000`. It prints a temporary `https://….trycloudflare.com` link.
- Keep `DEMO_MODE=true` so testers can use demo accounts, or let them sign up with `@stanford.edu`.
- Watch 3–5 students try it. Time "first photo → items shared" and note where they hesitate.

### 3.2 Feedback (B, about 1 week)
- The in-app **Feedback** button records `feedback_submitted` events. Also share a 5-question form:
  1. How long did it take to share your first items? Was anything confusing?
  2. Did the AI get your items right? What did it miss or get wrong?
  3. Would you use DAHA instead of the dorm group chat? Why or why not?
  4. What would you borrow or lend first?
  5. Did anything feel unsafe or too public?
- Triage weekly into a top-5 list in GitHub issues, labeled `feedback`.

### 3.3 Deploy (A)
1. **VM:** create a small Ubuntu VM (1 vCPU, 2 GB; for example DigitalOcean, free with GitHub Student Pack credit). Install Docker, then `git clone`.
2. **Env:** fill `backend/.env` with production values:
   - a new `JWT_SECRET`, `DEMO_MODE=false`, the `PUBLIC_BASE_URL`, `AI_PROVIDER=harnessrouter`
3. **Run:** `make up` (Docker Compose `full` profile), plus **Caddy** in front with automatic HTTPS. Use a domain or a free subdomain (DuckDNS or similar).
4. **Backups:** a nightly `pg_dump` cron to a backup folder, kept for 7 days.
5. **Done when:** the deployed app passes the demo script steps 1–6 on a phone.

### 3.4 Evals (C)
Follow `plans/EVALS.md`. Baseline → improve → re-run. Publish the report in `evals/reports/`.

### 3.5 Iterate (weekly loop)
- **B:** UX fixes from the feedback top 5.
- **A:** backend and infra fixes, plus P1 items such as overdue reminders and the leaderboard.
- **C:** AI quality from the evals: prompt v2, ranking weights, match threshold.
- Each week: merge, redeploy (`git pull && make up`), and post a short changelog in the chat.

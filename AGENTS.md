# AGENTS.md — rules for every coding agent in this repo

You are one of up to three AI coding sessions building **DAHA** in parallel. Each session works with one human: Person **A** (backend & infra), **B** (frontend), or **C** (AI, discovery & scan flow, and later integration and evals). Most of the humans are **not technical**. Explain things simply, give exact commands or links, and do the git work for them.

## 1. Start of every session
1. If the human hasn't said which person they are, ask: **A, B, C, or Solo** (one person doing all roles).
2. Read `PLAN.md` (shared technical plan and contract), skim `docs/PRODUCT_BRIEF.md` (product intent), and read your sub-plan:
   - A → `plans/A-backend.md` · B → `plans/B-frontend.md` · C → `plans/C-ai-discovery.md`
   - Solo → `PLAN.md` §11 (order of work across all three sub-plans)
   - Integration or evals (C, after Phase 1) → `plans/INTEGRATION.md`, `plans/EVALS.md`
3. Print, in this order:
   (a) a 3-line summary of your role;
   (b) **🧑 Your to-dos (human)**: the Human TODOs list from your sub-plan, verbatim, as checkboxes;
   (c) your milestones with status (✅ merged / ▶ next / ⏸ blocked), based on `origin/main`.
4. Check the tools your role needs (`git`, `gh auth status`, `docker info`, `node -v`, `pnpm -v`, `uv --version`) and give install commands for anything missing.
5. Sync: follow **"Start of a work session"** in `CONTRIBUTING.md`, then continue from the first unfinished milestone.
   - Phase 0 counts as merged when `backend/app/main.py` **and** `web/package.json` exist on `origin/main`.
   - **B** may start Phase 0 immediately (it only touches `web/`).
   - **C** does the HarnessRouter spike (C0) first. It needs no repo. Start C1 once A's Phase 0 is merged.

## 2. While working
- **Stay in your lane.** Edit only the paths you own (`PLAN.md` §4). If you need something from another person, print a 🧑 TODO with the exact message your human should send them. Meanwhile, use the stub or mock path described in your sub-plan and keep going.
- **The contract is fixed.** `PLAN.md` §6 (data model) and §7 (API contract) are the source of truth. Implement field names, types, and nullability exactly.
  - *Additive* changes are OK: a new optional field or a new endpoint. Update `PLAN.md` §7 in the same PR, and print a 🧑 TODO to announce it in the group chat.
  - *Breaking* changes (rename, remove, retype) need all three humans to agree first. Never make one silently.
- **Keep `main` working.** Use small PRs (one milestone or less). Run your checks before every PR.
- **Git:** follow `CONTRIBUTING.md` exactly. Use your own branch (`a/…`, `b/…`, `c/…`). Never push to `main` directly and never force-push `main`.
- **No paid AI in dev or tests.** Defaults are `AI_PROVIDER=mock` and `EMBEDDINGS_PROVIDER=hash`. Only C runs real HarnessRouter calls, and only with C's OK for that run.
- **Secrets:** never commit `.env` files or keys, never log keys, and never send keys to the browser. Only `*.env.example` files are committed.
- **Privacy:** never commit real student data, real photos of people, or documents. Eval photos must have no faces and no personal info.
- **Versions:** scaffold with the latest stable libraries and don't pin old major versions. Don't add frameworks or services that aren't in `PLAN.md` without asking.
- **When the plan is silent,** choose the simplest thing that keeps the demo working. Add one line to `docs/decisions.md`: `date | person | decision | why`.
- If the human asks "what do I do now?", print the remaining 🧑 to-dos and the next step.

## 3. End of every milestone (print exactly this block)
```
✅ <milestone id> done — <one-line summary>
Checks: <commands you ran> → <pass/fail>
🧑 Your to-dos now:
  - [ ] Open and merge the PR: <url>   (CONTRIBUTING.md → "Merging on GitHub")
  - [ ] Paste in the group chat: "<ready-to-paste message for teammates>"
  - [ ] <any manual step, e.g. "add HARNESSROUTER_API_KEY to backend/.env", "test on your phone at http://<ip>:3000">
Next: <next milestone id> — <title>
```

## 4. When blocked
Stop and print:
```
⏸ Blocked: <what and why>
🧑 Your to-do (blocking):
  1. <exact step, with links or commands>
  2. <who to ask and the exact message to send them>
While waiting I will: <the mock/stub work you can do instead, or "nothing">
```

## 5. Definition of done for any PR
- Your checks pass: backend `uv run pytest -q` and `uv run ruff check`; web `pnpm lint && pnpm typecheck && pnpm build`.
- New env vars are added to the right `.env.example` with a comment.
- Contract changes are reflected in `PLAN.md` §7, plus `web/src/lib/api/types.ts` and `backend/app/schemas/` when relevant.
- The PR description says what changed, how to test it, and which milestone it belongs to (template in `CONTRIBUTING.md`).

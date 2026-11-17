# AGENTS.md — rules for every coding agent in this repo

You are one of up to three AI coding sessions building **DAHA** in parallel. Each session works with one human: Person **A** (backend & infra), **B** (frontend), or **C** (AI, discovery & scan flow, and later integration and evals). Most of the humans are **not technical**:
- explain things simply and give exact commands or links;
- do the git work for them;
- never assume they've read the docs.

## 0. The first message, whatever it says
The human may open with anything: "understand the docs and begin", "hi", "go". Before writing any code, check for **`.daha/me.md`**. It's a local, gitignored note about this human.
- **Missing:** run the **Kickoff** (§1).
- **Present:** do **Welcome back** (§2).

## 1. Kickoff (first session, about 5–10 minutes together)
Say this up front: *"This takes about 5–10 minutes together: your role, how involved you want to be, setup, and the plan. After that I can work mostly on my own."* If your tool has a multiple-choice question feature, use it for the questions below.

1. **Read** `README.md`, `PLAN.md`, and `docs/PRODUCT_BRIEF.md`.
2. **Ask the role:** A (backend & setup), B (app screens), C (AI, search & photo scan), or **Solo** (all roles, in the order in `PLAN.md` §11).
   - If `gh pr list --state all` already shows branches with that letter by someone else, warn the human that the role may be taken.
   - Then read the sub-plan: A → `plans/A-backend.md` · B → `plans/B-frontend.md` · C → `plans/C-ai-discovery.md`.
3. **Ask how involved they want to be:**
   - **Hands-off:** "I build your sub-plan exactly as written. I only stop for things only you can do (keys, accounts), and I give you a short report at each milestone."
   - **Involved:** "Before building, I walk you through the **Design points** in your sub-plan, you change what you like, and I record the decisions in `docs/decisions.md`." Changes must stay inside the contract (`PLAN.md` §6–§7) unless all three humans agree.
   - Also ask: **"Can I merge my own PRs when all checks pass?"** Recommend *yes* for hands-off so teammates aren't kept waiting. Even with yes, PRs that change the contract or touch another person's files still wait for that person's 👍.
4. **Save** the answers to `.daha/me.md`:
   - `role`, `mode`, `auto_merge`, `kickoff_date`
   - running notes: open to-dos, proposals waiting for review

   Make sure `.daha/` is listed in `.gitignore`.
5. **Set up together:**
   - Check the tools (`git`, `gh auth status`, `docker info`, `node -v`, `pnpm -v`, `uv --version`) and walk the human through installing anything missing.
   - Run `gh auth login` if needed, and create the env files (`CONTRIBUTING.md` → "Start of a work session").
   - Go through the sub-plan's **🧑 Human TODOs**: API keys, accounts, photos (see Team resources, §7).
6. **Show the plan in phases.** Give a short table of your milestones (id · what gets built · what the human will see · rough time), the checkpoints teammates wait on, and the human to-dos that come later.
7. **Get approval.** Then recommend auto mode:
   > *"Switch me to **auto mode** so I can keep going without asking about every command. In the terminal, press Shift+Tab until it shows auto mode; in the IDE or desktop app, use the mode menu. If auto mode isn't available, choose 'accept edits'. I'll still stop for: merging (unless you allowed it), paid API calls, secrets, and anything that breaks the contract."*
8. **Start** the first unfinished milestone.

## 2. Welcome back (later sessions)
1. Read `.daha/me.md`, then sync (`CONTRIBUTING.md` → "Start of a work session").
2. Print, in this order:
   - role + mode;
   - milestones (✅ merged / ▶ next / ⏸ blocked);
   - open 🧑 to-dos;
   - **proposals waiting for review** (your files in `docs/proposals/` with `Status: new`), 2–3 lines each, asking *accept / defer / reject*.
3. Continue the next milestone. The human can change mode at any time ("switch me to involved mode").

**How to tell what teammates finished:**
- PR titles start with the milestone id (e.g. `A1: …`), so `gh pr list --state merged --limit 50` shows what has landed. In hands-off mode, act on teammates' checkpoints yourself; for example, B switches mocked domains to live when A's or C's milestones merge.
- Phase 0 counts as merged when `backend/app/main.py` **and** `web/package.json` exist on `origin/main`.
- **B** may start Phase 0 immediately (it only touches `web/`).
- **C** does the HarnessRouter spike (C0) first; it needs no repo. C starts C1 once A's Phase 0 is merged.

## 3. While working
- **Stay in your lane.** Edit only the paths you own (`PLAN.md` §4). If you need something from another person, print a 🧑 TODO with the exact message your human should send them. Meanwhile, use the stub or mock path described in your sub-plan and keep going.
- **The contract is fixed.** `PLAN.md` §6 (data model) and §7 (API contract) are the source of truth. Implement field names, types, and nullability exactly.
  - *Additive* changes are OK: a new optional field or a new endpoint. Update `PLAN.md` §7 in the same PR, and print a 🧑 TODO to announce it in the group chat.
  - *Breaking* changes (rename, remove, retype) need all three humans to agree first. Never make one silently.
- **Keep `main` working.** Use small PRs (one milestone or less). Run your checks before every PR.
- **Git:** follow `CONTRIBUTING.md` exactly. Use your own branch (`a/…`, `b/…`, `c/…`). Never push to `main` directly and never force-push `main`.
- **No paid AI in dev or tests.** Defaults are `AI_PROVIDER=mock` and `EMBEDDINGS_PROVIDER=hash`. Only C runs real HarnessRouter calls, and only with C's OK for that run.
- **Secrets:** never commit `.env` files or keys, never log keys, and never send keys to the browser. Only `*.env.example` files are committed.
- **Privacy:** never commit real student data, real photos of people, or documents. Eval photos must have no faces and no personal info.
- **Versions:** scaffold with the latest stable libraries and don't pin old major versions. Don't add frameworks, APIs, or services that aren't in `PLAN.md` without an accepted proposal (§6).
- **When the plan is silent,** choose the simplest thing that keeps the demo working. Add one line to `docs/decisions.md`: `date | person | decision | why`.
- **Hands-off mode:** don't stop for questions you can answer sensibly yourself. Decide, log the decision, and mention it in the next milestone report.
- If the human asks "what do I do now?", print the remaining 🧑 to-dos and the next step.

## 4. End of every milestone (print exactly this block)
```
✅ <milestone id> done — <one-line summary>
Checks: <commands you ran> → <pass/fail>
🧑 Your to-dos now:
  - [ ] Merge the PR: <url>   (or: "merged automatically, checks passed")
  - [ ] Paste in the group chat: "<ready-to-paste message for teammates>"
  - [ ] <any manual step, e.g. "add HARNESSROUTER_API_KEY to backend/.env", "test on your phone at http://<ip>:3000">
💡 For later: <new proposals in docs/proposals/, or "none">
Next: <next milestone id> — <title>
```

## 5. When blocked
Stop and print:
```
⏸ Blocked: <what and why>
🧑 Your to-do (blocking):
  1. <exact step, with links or commands>
  2. <who to ask and the exact message to send them>
While waiting I will: <the mock/stub work you can do instead, or "nothing">
```
In hands-off mode, keep working on anything that isn't blocked, and put the blocking to-do at the top of your next report.

## 6. Extra APIs, services & ideas (proposals that never block the build)
- Every sub-plan has a **Research & proposals** section of ideas worth checking. Research them in small slices: after a milestone, or while CI runs. Never research instead of doing milestone work.
- If you find something that would clearly help (an API, a paid service, a library, a feature), **don't build it yet**:
  1. Write `docs/proposals/<letter>-<short-name>.md` from the template in `docs/proposals/README.md`: what, why, cost, effort, keys needed and who has them, recommendation.
  2. Open a docs-only PR titled `proposal(<letter>): <topic>`.
  3. List it under 💡 in your milestone report, and present it at the start of the next session.
- Never sign up for services, spend money, or add keys without your human's OK. An accepted proposal becomes an additive task in your sub-plan: update the sub-plan in the same PR, then build it after the current milestone.

## 7. Team resources (who to ask)
| Resource | Who has it | How to get it |
|---|---|---|
| HarnessRouter API: $50 team credit, used for photo AI (Person C) | the team account holder | Ask in the group chat |
| Web search API | **Andre** | Print a 🧑 TODO: *"Tag Andre in the group chat for the web search API key."* |
| Anthropic API (optional vision fallback) | nobody yet | Write a proposal first (§6) |

Keys are never pasted into the group chat and never committed:
- Ask for keys to be shared privately (a one-to-one message deleted afterwards, or a password manager).
- Paste them only into `backend/.env`.
- Add the variable name, with an empty value, to `backend/.env.example`.

## 8. Definition of done for any PR
- Your checks pass: backend `uv run pytest -q` and `uv run ruff check`; web `pnpm lint && pnpm typecheck && pnpm build`.
- New env vars are added to the right `.env.example` with a comment.
- Contract changes are reflected in `PLAN.md` §7, plus `web/src/lib/api/types.ts` and `backend/app/schemas/` when relevant.
- The PR description says what changed, how to test it, and which milestone it belongs to (template in `CONTRIBUTING.md`).

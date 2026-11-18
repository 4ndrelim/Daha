# Contributing to DAHA

There are two parts here. **Part 1** is for humans: what to click and what to say to Claude. **Part 2** is for agents: the exact git workflow. Agents must follow Part 2 to the letter.

---

## Part 1: for humans (no git knowledge needed)

> **The one rule:** every change goes through a **branch** and a **Pull Request (PR)**, never straight to `main`. That includes docs and one-line fixes. Claude makes the branch and the PR for you. `main` only changes when a PR is merged.

**Words you'll see**
- **Branch:** your own copy of the code to work on, so you never break anyone else's work.
- **PR (Pull Request):** a request to add your branch's work into the shared version (`main`).
- **Merge:** accepting a PR. After that, everyone gets the work the next time they sync.
- **Conflict:** two people changed the same lines. Claude fixes these for you.
- **Sync / pull:** getting everyone's latest merged work. Claude does this on its own, before each piece of work.

**Phrases to paste into Claude**
| When | Say this |
|---|---|
| First time | `Understand the docs and begin.` Claude asks your role and how involved you want to be (about 5–10 min) |
| Every new session | `Continue.` (or `Sync with main and continue my plan.`) |
| After a pull, or you got a new key | `Refresh my env files.` Claude runs `make env`. Paste keys only into `backend/.env` |
| See what Claude researched | `Show me your proposals.` |
| Change how involved you are | `Switch me to involved mode.` or `Switch me to hands-off mode.` |
| A piece is done | `Open a PR for this milestone.` |
| After checks pass | `Merge my PR.` (or press **Merge** on GitHub) |
| Something conflicts | `Fix the merge conflict with main, keeping everyone's changes.` |
| You're lost | `What are my to-dos right now?` |
| Someone announced a change | `Pull main and adapt to the new change: <paste message>.` |
| Found a bug in someone else's part | `Open a GitHub issue for Person A: <describe bug>.` |

**Auto mode.** After the kickoff, switch Claude to auto mode so it doesn't ask about every command:
- **Terminal:** press Shift+Tab until it shows auto mode.
- **IDE or desktop app:** use the mode menu.
- If auto mode isn't there, pick "accept edits".

**Merging on GitHub (about 30 seconds).** Skip this if you let Claude merge its own PRs.
1. Open the PR link Claude gave you.
2. Wait for the green ✓ checks (after CI is set up).
3. Click **Squash and merge**, then **Confirm**, then **Delete branch**.
4. Paste Claude's ✅ message in the group chat.

**Group chat etiquette**
- Post every ✅ checkpoint message. Teammates' Claudes use them to switch from fake data to real data.
- If Claude says **"contract change"**, post it and tag everyone.
- If Claude says **"blocked"**, send the exact message it wrote to the person it names.

---

## Part 2: for agents (exact workflow)

### The one rule: branch → PR → merge (never commit or push to `main`)
- **Every change goes through a PR:** code, docs, proposals, one-line fixes. The path is always new branch → commits → push the branch → PR → merge the PR.
- **Your local `main` is read-only.** Only ever `git pull` into it. Never `git commit` while on `main`, and never `git push origin main`, forced or not.
- **Before every commit and push,** check `git branch --show-current`. If it says `main`, stop and create a branch first: `git checkout -b <letter>/<topic>`.
- **`main` changes only by merging a PR,** with `gh pr merge` or the GitHub button (see "Merging" below).
- **Safety net:** `.githooks/` blocks commits on `main` and pushes to `main`. Turn it on once per clone with `git config core.hooksPath .githooks`.
- **Committed on `main` by accident?** Commit any loose changes first, then move the work to a branch:
  ```bash
  git branch <letter>/<topic>      # your commits are now saved on a new branch
  git reset --hard origin/main     # local main back to the shared version
  git checkout <letter>/<topic>    # continue here, then open a PR
  ```

### Start of a work session
1. **First time on a machine:**
   - Run `gh auth status`. If logged out: `gh auth login`, then choose GitHub.com, HTTPS, and log in with a browser.
   - Turn on the safety hooks: `git config core.hooksPath .githooks`.
   - Create your env files: `make env`. Then fill in the keys you have (see "Environment files" below).
2. **Every session:** sync (next section), then follow the development loop.

### Environment files (`.env`)
Settings and secret keys live in two local files that git ignores. Only the `*.env.example` templates are committed, and they explain every variable.

| Your file | Used by | Template (committed) |
|---|---|---|
| `backend/.env` | the API, `make` targets, backend scripts, `make up` (Docker) | `backend/.env.example` |
| `web/.env.local` | the Next.js dev server (no secrets) | `web/.env.example` |

- **Create or refresh them with `make env`.** The first time, it copies the templates. After a pull, it appends any variables a teammate added (with the template's default) and prints their names. It never changes a line you already have, so your keys stay put.
- **Fill in the keys you have,** only in `backend/.env`. Never put them in chat, screenshots, or code.

  | Variable | What it's for | Format | Who has it |
  |---|---|---|---|
  | `JWT_SECRET` | signs login tokens | the output of `openssl rand -hex 32` | make your own |
  | `HARNESSROUTER_API_KEY` | photo AI (HarnessRouter) | one key, or several comma-separated with no spaces: `sk-hr-aaa,sk-hr-bbb`. Photos are load-balanced across them. Keys in one organization share its credit and its task limit | the team account holder (`AGENTS.md` §7) |
  | `HARNESSROUTER_VISION_HARNESS_ID` | the harness each key runs | don't type it: after setting the keys, run `cd backend && uv run python scripts/setup_harnessrouter.py --write-env` (free; one harness per key, saved in key order) | generated |
  | `ANTHROPIC_API_KEY` | optional vision fallback | `sk-ant-…` | nobody yet (proposal first) |

  Any other key (for example web search) is listed in `AGENTS.md` §7 and explained in `backend/.env.example`.
- **Check your HarnessRouter keys for free:** `cd backend && uv run python scripts/setup_harnessrouter.py --check` prints `key 1/3: OK · organization …` for each key (never the key itself) and points out keys that share an organization.
- **The template turns the real AI on** (`AI_PROVIDER=harnessrouter`, and `COMMERCIAL_PROVIDER=exa` for store search), so everything works once the shared keys are in. Each photo (≈ $0.10) and each new store search (≈ $0.02) spends team credit, capped by `AI_BUDGET_USD` and `COMMERCIAL_BUDGET_USD`. No keys yet, or working offline? Set both to `mock`: free sample data. Tests always use `mock`.
- **After editing `backend/.env`,** restart `make api`: settings are read once at startup.
- **Agents adding a variable:** add it to the right `.env.example` in the same PR, with a comment and a safe default (empty for keys), and mention it in the PR description. Teammates pick it up with `make env`.

### Always sync with `main` (the golden rule)
Teammates merge all day, so sync **every time** at these moments:
- the start of every session;
- before starting each milestone (every new branch comes from a fresh `main`);
- before opening or updating a PR;
- when a teammate's milestone you depend on lands (`gh pr list --state merged --limit 10`);
- at least every ~2 hours during long auto-mode sessions.

```bash
git status            # uncommitted work? commit it to your branch first (never discard someone's work)
git fetch origin
git checkout main && git pull --rebase origin main
# continuing your unmerged branch instead of starting a new one:
git checkout <your-branch> && git rebase origin/main
```
After every pull, refresh. These are cheap and safe, so just run them (skip any part that doesn't exist yet):
```bash
(cd backend && uv sync)      # new backend dependencies
make db && make migrate      # new database migrations (A adds these); make db starts Postgres if needed
(cd web && pnpm install)     # new web dependencies
make env                     # new settings from the .env.example files (keeps your values)
```
Run `make seed` again only if `backend/app/seed/` changed. It resets the demo data.

### The development loop (one milestone at a time)
1. **Branch** from a freshly synced `main`: `git checkout -b <letter>/<milestone>-<topic>`, e.g. `a/a1-auth`, `b/b2-explore`, `c/c1-scans`.
   - If your previous PR isn't merged yet and the next milestone needs it, branch from your previous branch instead (`git checkout -b <new-branch> <previous-branch>`). Write `Depends on #<n>` in the new PR, and rebase onto `main` once the first PR merges. Don't sit idle waiting.
2. **Run what you need locally** (`PLAN.md` §5.2): `make db` → `make migrate` → `make seed` → `make api` and/or `make web`. Before Phase 0 lands, follow your sub-plan's setup steps instead.
3. **Build** the milestone from your sub-plan in small steps: code → test → run → commit. Anything a teammate hasn't merged yet comes from mocks or stubs; your sub-plan says how.
4. **See it work the way the human will:** call the endpoint (`curl`, or `http://localhost:8000/docs`), or open the page at `http://localhost:3000`. On a phone: `make lan`.
5. **Check, push, PR:** follow "Before opening a PR" and "Opening the PR" below.
6. **Merge** per the rules below, sync again, and print the end-of-milestone block (`AGENTS.md` §4).
7. Go back to step 1 for the next milestone.

### While working
- Commit small and often, using the format `<type>(<area>): <summary> [<milestone>]`. Types: `feat`, `fix`, `test`, `docs`, `chore`, `refactor`. Areas: `api`, `db`, `web`, `ai`, `search`, `infra`.
  Example: `feat(api): transaction state machine [A3]`.
- Touch only the paths you own (`PLAN.md` §4).
- **Shared files** may get small, append-only edits by anyone, always inside your own branch and PR: `PLAN.md` §7 (additive contract changes), `backend/.env.example`, `web/.env.example`, `docs/decisions.md`. Rebase right before you merge.
- Adding a dependency: backend → `cd backend && uv add <pkg>`; web → `cd web && pnpm add <pkg>`. Commit the lockfile in the same commit.

### Before opening a PR
```bash
git fetch origin && git rebase origin/main
# backend changes:
cd backend && uv run ruff check . && uv run pytest -q && cd ..
# web changes:
cd web && pnpm lint && pnpm typecheck && pnpm build && cd ..
git push -u origin HEAD
# already pushed this branch before the rebase? use this instead (your own branch only):
# git push --force-with-lease
```

### Opening the PR
```bash
gh pr create --base main --title "<milestone>: <summary>" --body "$(cat <<'EOF'
## What
<1–3 bullets>
## Milestone
<e.g. A2 — Items + seed>
## How to test
<exact commands / clicks>
## Contract changes
None | Additive: <what> (PLAN.md §7 updated)
## Screenshots (UI changes)
<optional>
EOF
)"
```
Add labels: `gh pr edit --add-label A` (or `B` / `C`), plus `contract` if the PR changes the API contract.

### Proposal PRs
Ideas from your sub-plan's "Research & proposals" section go in a docs-only PR (`AGENTS.md` §6):
- title `proposal(<letter>): <topic>`, label `proposal`;
- it adds one file, `docs/proposals/<letter>-<short-name>.md`;
- it is safe to merge any time, because it changes no code.

### Merging (when the human asks, or `auto_merge: yes` in `.daha/me.md`)
Merge only when the checks pass **and** one of these is true:
- the human said to merge;
- `.daha/me.md` has `auto_merge: yes`, the PR doesn't change the contract, and it doesn't touch another person's paths.
```bash
gh pr merge --squash --delete-branch
git checkout main && git pull --rebase origin main
```
PRs that change the contract, or touch another person's paths, need that person's 👍 on the PR first.

### Resolving conflicts
1. Run `git rebase origin/main`, then for each conflicted file:
   - **A file you own:** combine both sides, keeping everyone's intent.
   - **A file someone else owns:** take `main`'s version (during a rebase that is `git checkout --ours <file>`, because in a rebase "ours" means `main`), then re-apply your change only if it's in your lane.
   - **Lockfiles:** take `main`'s version (`git checkout --ours <lockfile>`), then regenerate: `cd backend && uv lock` or `cd web && pnpm install`.
2. Run `git add <files> && git rebase --continue`, re-run the checks, then `git push --force-with-lease` (your own branch only, **never** `main`).

### Bugs found by others
Bugs found in someone else's area go to them as an issue: `gh issue create --title "<bug>" --body "<steps, expected, actual>" --label <A|B|C>`. During integration, fix your own issues first and link them in the PR with `Fixes #<n>`.

### Never
- Commit on `main`, push to `main`, or force-push `main`. Every change goes through a PR.
- Commit `.env`, keys, real photos of people, `backend/uploads/`, `node_modules/`, or `.venv/`.
- Rewrite another person's files to make your code work. Ask them instead (print a 🧑 TODO).

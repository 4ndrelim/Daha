# Contributing to DAHA

There are two parts here. **Part 1** is for humans: what to click and what to say to Claude. **Part 2** is for agents: the exact git workflow. Agents must follow Part 2 to the letter.

---

## Part 1: for humans (no git knowledge needed)

**Words you'll see**
- **Branch:** your own copy of the code to work on, so you never break anyone else's work.
- **PR (Pull Request):** a request to add your branch's work into the shared version (`main`).
- **Merge:** accepting a PR. After that, everyone gets the work the next time they sync.
- **Conflict:** two people changed the same lines. Claude fixes these for you.

**Phrases to paste into Claude**
| When | Say this |
|---|---|
| First time | `I am Person B. Set me up and start my plan.` |
| Every new session | `Sync with main and continue my plan.` |
| A piece is done | `Open a PR for this milestone.` |
| After checks pass | `Merge my PR.` (or press **Merge** on GitHub) |
| Something conflicts | `Fix the merge conflict with main, keeping everyone's changes.` |
| You're lost | `What are my to-dos right now?` |
| Someone announced a change | `Pull main and adapt to the new change: <paste message>.` |
| Found a bug in someone else's part | `Open a GitHub issue for Person A: <describe bug>.` |

**Merging on GitHub (about 30 seconds)**
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

### Start of a work session
```bash
git checkout main && git pull --rebase origin main
# continuing a branch that is not merged yet:
git checkout <branch> && git rebase origin/main
# starting the next milestone:
git checkout -b <letter>/<milestone>-<topic>      # e.g. a/a1-auth, b/b2-explore, c/c1-scans
```
First time on a machine: `gh auth status` (if logged out: `gh auth login`, choose GitHub.com, HTTPS, log in with a browser). Then create the env files: `cp backend/.env.example backend/.env` and `cp web/.env.example web/.env.local`.

### While working
- Commit small and often, using the format `<type>(<area>): <summary> [<milestone>]`. Types: `feat`, `fix`, `test`, `docs`, `chore`, `refactor`. Areas: `api`, `db`, `web`, `ai`, `search`, `infra`.
  Example: `feat(api): transaction state machine [A3]`.
- Touch only the paths you own (`PLAN.md` §4).
- **Shared files** may get small, append-only edits by anyone: `PLAN.md` §7 (additive contract changes), `backend/.env.example`, `web/.env.example`, `docs/decisions.md`. Rebase right before you merge.
- Adding a dependency: backend → `cd backend && uv add <pkg>`; web → `cd web && pnpm add <pkg>`. Commit the lockfile in the same commit.

### Before opening a PR
```bash
git fetch origin && git rebase origin/main
# backend changes:
cd backend && uv run ruff check . && uv run pytest -q && cd ..
# web changes:
cd web && pnpm lint && pnpm typecheck && pnpm build && cd ..
git push -u origin HEAD
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

### Merging (only when the human asks)
Merge only after the human says so and the checks pass:
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
- Push to `main` directly, or force-push `main`.
- Commit `.env`, keys, real photos of people, `backend/uploads/`, `node_modules/`, or `.venv/`.
- Rewrite another person's files to make your code work. Ask them instead (print a 🧑 TODO).

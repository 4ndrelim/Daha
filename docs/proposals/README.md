# Proposals

Ideas, APIs, and services that an agent found could help DAHA. **Agents write them; humans decide.** Nothing here gets built until its status is `accepted`.

## How it works
1. While building, an agent researches its sub-plan's "Research & proposals" list. It does this in small slices that never block milestones.
2. When something looks worth it, the agent writes `docs/proposals/<letter>-<short-name>.md` from the template below and opens a docs-only PR titled `proposal(<letter>): <topic>`.
3. At the start of the next session, the agent presents the proposal and its human picks **accept / defer / reject**. The agent then updates `Status:`.
4. If accepted, the agent adds the work to its sub-plan as an additive task and builds it after the current milestone. Paid services and new keys always need the human's OK first. Shared keys: see `AGENTS.md` §7 (for example, **web search → ask Andre**).

## Template
```markdown
# <Title>
- Status: new | accepted | deferred | rejected
- Author: Person <A|B|C> · Date: <YYYY-MM-DD>
- Problem it solves: <one or two sentences>
- Proposal: <what to add and where it plugs in>
- Cost: free | $<n>/month | usage-based (~$<n> per <unit>)
- Effort: <hours>, touches <milestones/files>
- Keys / accounts needed: <name> — who has it: <person>
- Risks / privacy: <anything sensitive, rate limits, lock-in>
- Recommendation: <do now | after MVP | skip>, and why
```

# Evals (Person C): a quick version for the hackathon, the full version after it

> **Status (2026-11-17):** the parse, search and match suites run on the seed, with reports in `evals/reports/`: parse 1.00 on every field; search 5/5 demo queries in the top 3 (nDCG@10 0.94, p95 66 ms); match recall@5 1.00, precision@5 0.96. The scan suite is built but gated: it needs labeled eval photos (the HarnessRouter keys are verified). These numbers are a baseline for the improvement loop below, not a finish line.

**Goal:** measure, with numbers, how good the AI parts are. Then improve them, and prove each change helped.

## Hackathon mini-eval (Thu 08:00–09:00, ≤ $3 of HarnessRouter credit)
The goal is three honest numbers for the pitch:
1. **Scan:**
   - Take 10 of C's photos and label them quickly (~5 min: a list of the items in each).
   - Run `evals.run scan --limit 10`.
   - Report "found X% of the items" and "~N s per photo".
2. **Search:** for the 5 demo queries, check whether the expected seed item is in the top 3. Report "5/5 demo searches hit in the top 3".
3. Paste the numbers into the submission write-up (`plans/INTEGRATION.md` §3.3).

## 🧑 Human TODOs: full evals (after the hackathon; C, with help from A and B)
- [ ] Collect 20–30 eval photos: no people, no documents. Put them in `evals/data/scan/images/`. These are committed only if everyone agrees; otherwise keep them in a shared drive and gitignore the folder.
- [ ] Label them with Claude's sheet (`evals/data/scan/labels.csv`): list the shareable items in each photo with category and quantity, and mark sensitive ones. That's about 2 minutes per photo.
- [ ] Write 30 real-sounding requests in your own words. Real dorm-chat messages work too, anonymized. Claude adds 30 synthetic ones.
- [ ] Approve each paid eval run. Claude prints the estimated cost first. Scan evals use HarnessRouter credit; everything else is free.

## Layout
```
evals/
  data/scan/images/*.jpg  · data/scan/labels.jsonl   {"image","items":[{"name","category","quantity","sensitive"}]}
  data/parse/requests.jsonl    {"text","now","gold":{"kind","item_name","category","needed_from","duration_days","transaction_type"}}
  data/search/queries.jsonl    {"q","viewer_seed_key","relevant":{"<item seed_key>":2|1}}
  data/match/requests.jsonl    {"text","requester_seed_key","expected_item_seed_keys":[...]}
  run.py        # uv run python -m evals.run {scan|parse|search|match|all} [--provider] [--limit N] [--yes]
  metrics.py · reports/YYYY-MM-DD-<suite>.md (committed)
```
Search and match evals use the seeded database (`make seed`) and refer to items by their `seed_key`.

## Suites, metrics, MVP targets
| Suite | How it's scored | Target |
|---|---|---|
| **Scan** (vision) | Greedy-match predicted items to labels (same category and name embedding similarity ≥ 0.75). Report precision, recall, F1; category accuracy; quantity exact-match; **sensitive leak rate** (sensitive items with `suggested_share=true`); p50/p95 seconds per photo; $ per photo | recall ≥ 0.70, precision ≥ 0.80, leak rate 0, p50 ≤ 45 s (HarnessRouter) |
| **Parse** (request text) | Per-field accuracy; exact date match on dated examples | kind and category ≥ 0.85, dates ≥ 0.90 |
| **Search** | nDCG@10, P@5, MRR; same-dorm-first rate; zero-result rate; p95 latency | nDCG@10 ≥ 0.80 on the 5 demo queries; 0 zero-result queries; p95 < 300 ms |
| **Match** | recall@5 and precision@5 vs. expected items; notification precision (notified owners who actually hold a relevant item, for both public matches and anonymous private pings) | recall@5 ≥ 0.80 |

## Online metrics (from real usage, `evals/online_metrics.sql`)
- time to first publish (from `scan_started` to `scan_published`)
- scan → publish rate
- **edit rate per field**: how often users fix AI names and categories; this is our real-world accuracy
- request → first offer time
- fulfillment rate
- search click-through @5
- zero-result search rate
- weekly active lenders per dorm

## The improvement loop
1. Run `evals.run all` to get the baseline report.
2. Change one thing: prompt v2 (add few-shot examples taken from real user edits), ranking weights, `MATCH_MIN_SCORE`, or parser rules.
3. Re-run the affected suite. Keep the change only if the headline metric improves and nothing else regresses. Commit the report and the change together.
4. Cost control:
   - cache scan results by (image hash, prompt version, model), so re-running unchanged prompts is free
   - `--limit` for quick checks
   - never loop paid runs without a human OK

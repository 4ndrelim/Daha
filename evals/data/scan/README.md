# Scan eval data (not committed unless the whole team agrees)

Put photos in `images/` (no people, no documents, no screens with personal info) and one line per
photo in `labels.jsonl`:

    {"image": "desk1.jpg", "items": [{"name": "Desk lamp", "category": "dorm", "quantity": 1, "sensitive": false}]}

Run `uv run --project backend python -m evals.run scan --limit 10` (mock provider by default;
`--provider harnessrouter --yes` spends real credit — the runner prints the estimate first).

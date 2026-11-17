# Decision log
| date | person | decision | why |
|---|---|---|---|
| 2026-11-16 | plan | FastAPI + Next.js + Postgres/pgvector monorepo | Clean A/B/C split; Python for AI and evals; one database for every kind of search |
| 2026-11-16 | plan | HarnessRouter for vision only, behind a provider interface (mock / harnessrouter / anthropic) | Uses the $50 credit; HarnessRouter tasks are slow, so scans run as background jobs |
| 2026-11-16 | plan | Local fastembed embeddings; rule-based query and request parsing | Free and instant; paid AI reserved for photos |
| 2026-11-16 | plan | Person C leads integration and evals | C's work spans backend and frontend, and the evals measure C's AI |
| 2026-11-17 | plan | Guided 5–10 min kickoff (role + hands-off/involved mode + optional auto-merge) and async proposals in docs/proposals/ | Non-technical teammates can start by saying anything; research never blocks building |
| 2026-11-17 | plan | Private "I have this" items + anonymous pings in the MVP (C5); personal inventory keeper and declutter mode as follow-ups (F1–F3) | From user feedback; private visibility is the base for both |
| 2026-11-17 | plan | Hackathon schedule (submit Thu Nov 19 12:00): feature freeze Wed 18:00, code freeze Thu 10:30, per-person cut lists. Hosting, feedback week, full evals, and ML go after the hackathon | 5-day hackathon; ship the demo script first |
| 2026-11-17 | A | Dorm coordinates from OpenStreetMap; Manzanita Park, Mirrielees, and The Row use nearby points marked `"approx": true` | Nominatim had no exact match for those three; `PLAN.md` §8 allows the fallback |
| 2026-11-17 | A | Backend tests rebuild `daha_test` from the real Alembic migration and truncate tables between tests | Tests the migration itself; safe with background hooks that open their own DB session |
| 2026-11-17 | A | `requests` also gets GIN (`search_tsv`) and HNSW (`embedding`) indexes, like `items` | C's matching and search query both tables; additive, no contract change |
| 2026-11-17 | A | A request with only `needed_from` (no `needed_until`) expires the day after `needed_from` | `PLAN.md` §7.4 only covers `needed_until` and "no dates"; a dated request shouldn't stay open forever |
| 2026-11-17 | A | Private groups appear in `GET /communities` (name only, no join code); their member list returns 404 to non-members | People need to find the group to enter its code; who is in it stays private |
| 2026-11-17 | A | Signup input errors (bad email, wrong domain, password < 8 characters) return 400; demo login for a non-demo user returns 404 | Matches the error table in `PLAN.md` §5.6 |

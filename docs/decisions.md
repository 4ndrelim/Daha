# Decision log
| date | person | decision | why |
|---|---|---|---|
| 2026-11-16 | plan | FastAPI + Next.js + Postgres/pgvector monorepo | Clean A/B/C split; Python for AI and evals; one database for every kind of search |
| 2026-11-16 | plan | HarnessRouter for vision only, behind a provider interface (mock / harnessrouter / anthropic) | Uses the $50 credit; HarnessRouter tasks are slow, so scans run as background jobs |
| 2026-11-16 | plan | Local fastembed embeddings; rule-based query and request parsing | Free and instant; paid AI reserved for photos |
| 2026-11-16 | plan | Person C leads integration and evals | C's work spans backend and frontend, and the evals measure C's AI |
| 2026-11-17 | plan | Guided 5–10 min kickoff (role + hands-off/involved mode + optional auto-merge) and async proposals in docs/proposals/ | Non-technical teammates can start by saying anything; research never blocks building |

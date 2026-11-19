#!/bin/sh
# Container start: bring the database up to date, make sure it has data, then serve.
set -e
alembic upgrade head
# Empty database → campus, dorms, places (+ the demo world when DEMO_MODE=true). Never resets.
python -m app.seed.seed --if-empty
# Database already in use → add any new dorms or exchange points from the seed files. It only
# inserts or updates those rows and never deletes anything; a failure here must not stop the app.
python -m app.seed.seed --sync-base || echo "WARNING: could not sync dorms and places; continuing"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips "*"

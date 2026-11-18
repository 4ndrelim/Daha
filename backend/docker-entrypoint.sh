#!/bin/sh
# Container start: bring the database up to date, make sure it has data, then serve.
set -e
alembic upgrade head
# Empty database → campus, dorms, places (+ the demo world when DEMO_MODE=true). Never resets.
python -m app.seed.seed --if-empty
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips "*"

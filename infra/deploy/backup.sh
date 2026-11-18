#!/usr/bin/env bash
# Runs ON THE VM: nightly by cron (set up by remote.sh), or now with `./infra/deploy/deploy.sh backup`.
# Saves the database and the uploaded photos to ~/daha/backups and keeps the last 7 days.
# These copies live on the same VM: download one now and then (see infra/deploy/PLAN.md).
set -euo pipefail

out="$HOME/daha/backups"
day=$(date +%F)
mkdir -p "$out"
cd "$HOME/daha/src"

sudo docker compose exec -T db pg_dump -U daha -d daha | gzip > "$out/db-$day.sql.gz"
sudo docker run --rm -v daha_daha_uploads:/uploads:ro -v "$out":/backup alpine \
  tar -czf "/backup/uploads-$day.tgz" -C /uploads .

find "$out" -name 'db-*.sql.gz' -mtime +7 -delete
find "$out" -name 'uploads-*.tgz' -mtime +7 -delete
echo "$(date -Is) backup ok: $(du -h "$out/db-$day.sql.gz" | cut -f1) database, $(du -h "$out/uploads-$day.tgz" | cut -f1) photos"

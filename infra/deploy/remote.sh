#!/usr/bin/env bash
# Runs ON THE VM, started by infra/deploy/deploy.sh (never run it by hand on your laptop).
# Safe to re-run: every step checks first. Never prints keys or the DuckDNS token.
#
# Expects (uploaded by deploy.sh):
#   ~/daha/src.new/             the code to deploy
#   ~/daha/config/deploy.env    SITE, DEMO_MODE, PUBLIC_IP, and DUCKDNS_SUBDOMAIN/TOKEN if used
#   ~/daha/config/backend.env.new   your backend/.env with the server settings applied
set -euo pipefail

DAHA="$HOME/daha"
CONF="$DAHA/config"
SRC="$DAHA/src"
log() { printf '\n==> %s\n' "$*"; }

# shellcheck source=/dev/null
. "$CONF/deploy.env"
MODE="${MODE:-deploy}" # deploy = public with HTTPS; prepare = build and run privately, no Caddy yet
: "${DEMO_MODE:?}"
if [ "$MODE" = deploy ]; then : "${SITE:?}"; fi

# 1. Swap: building the web app needs more memory than small VMs have.
mem_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
if [ "$mem_kb" -lt 3800000 ] && [ -z "$(swapon --noheadings 2>/dev/null)" ]; then
  log "Adding a 4 GB swap file (this VM has $((mem_kb / 1024)) MB of memory)"
  sudo fallocate -l 4G /swapfile 2>/dev/null || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096 status=none
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

# 2. Docker (the official install script; includes Docker Compose).
wait_for_apt() { # a fresh VM (or someone's own `apt install`) may be holding the package lock
  local waited=0
  while sudo fuser /var/lib/dpkg/lock-frontend /var/lib/apt/lists/lock >/dev/null 2>&1; do
    [ "$waited" -eq 0 ] && echo "   waiting for another package install on the VM to finish…"
    [ "$waited" -ge 600 ] && { echo "Another package install has been running for 10 minutes; try again later."; exit 1; }
    sleep 5
    waited=$((waited + 5))
  done
}
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker (about 2 minutes)"
  wait_for_apt
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"   # lets you run docker without sudo after your next login
fi
sudo systemctl enable --now docker >/dev/null 2>&1 || true   # (a snap-installed Docker runs on its own)

# 3. The web address. DuckDNS: point the name at this VM (an empty ip= means "the address this
#    request comes from"). Your own subdomain: its DNS A record already points here.
if [ "$MODE" = prepare ]; then
  log "Prepare mode: no web address yet (the real deploy adds it and HTTPS)"
elif [ -n "${DUCKDNS_SUBDOMAIN:-}" ]; then
  log "Pointing $SITE at this VM"
  answer=$(curl -fsS --max-time 20 "https://www.duckdns.org/update?domains=${DUCKDNS_SUBDOMAIN}&token=${DUCKDNS_TOKEN:-}&ip=${PUBLIC_IP:-}" || true)
  if [ "$answer" != "OK" ]; then
    echo "DuckDNS didn't accept the update (it answered: ${answer:-nothing})."
    echo "Check DUCKDNS_SUBDOMAIN (just the name, without .duckdns.org) and DUCKDNS_TOKEN in infra/deploy/.env."
    exit 1
  fi
else
  log "Using your own address: $SITE (its DNS A record must point at this VM)"
fi

# 4. Swap in the new code; the previous version stays in src.old until the next deploy.
log "Installing the new code"
rm -rf "$DAHA/src.old"
if [ -d "$SRC" ]; then mv "$SRC" "$DAHA/src.old"; fi
mv "$DAHA/src.new" "$SRC"

# 5. Server settings. The JWT secret is made once on this VM and kept, so redeploys never log
#    anyone out. Everything else comes from your laptop's backend/.env.
umask 077
if [ ! -s "$CONF/jwt_secret" ]; then openssl rand -hex 32 > "$CONF/jwt_secret"; fi
{
  cat "$CONF/backend.env.new"
  echo "JWT_SECRET=$(cat "$CONF/jwt_secret")"
} > "$CONF/backend.env"
rm -f "$CONF/backend.env.new"
ln -sf "$CONF/backend.env" "$SRC/backend/.env"
# Docker Compose reads this file for its own settings (which files, ports, the web address).
cat > "$SRC/.env" <<EOF
COMPOSE_PROJECT_NAME=daha
COMPOSE_FILE=docker-compose.yml:infra/deploy/docker-compose.prod.yml
COMPOSE_PROFILES=full
SITE_ADDRESS=${SITE:-localhost}
NEXT_PUBLIC_DEMO_MODE=$DEMO_MODE
API_PORT=127.0.0.1:8000
WEB_PORT=127.0.0.1:3000
EOF
umask 022

# 6. Build and start everything. Data lives in Docker volumes, so it survives every redeploy.
log "Building and starting DAHA (first time: 10-20 minutes; later: a few)"
cd "$SRC"
services=() # all of them; prepare mode leaves Caddy (HTTPS) for the real deploy
if [ "$MODE" = prepare ]; then services=(db api web); fi
if ! sudo docker compose up -d --build --remove-orphans --wait "${services[@]}"; then
  echo "Something didn't start. The last log lines:"
  sudo docker compose ps
  sudo docker compose logs --tail 60
  exit 1
fi

# 7. Nightly backups at 03:30 (database + photos), kept 7 days in ~/daha/backups.
mkdir -p "$DAHA/backups"
job="30 3 * * * bash $SRC/infra/deploy/backup.sh >> $DAHA/backups/backup.log 2>&1"
( crontab -l 2>/dev/null | grep -v 'infra/deploy/backup.sh' || true; echo "$job" ) | crontab -

log "Running:"
sudo docker compose ps --format 'table {{.Service}}\t{{.Status}}'
if curl -fsS --max-time 10 http://127.0.0.1:8000/api/health | grep -q '"ok":true'; then
  echo "backend health check: ok"
else
  echo "backend health check: not answering yet"
fi

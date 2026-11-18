#!/usr/bin/env bash
# Put DAHA online on the Azure VM, from your laptop (infra/deploy/OWNERACTIONS.md).
#
#   ./infra/deploy/deploy.sh          deploy: the first run sets everything up, later runs update
#   ./infra/deploy/deploy.sh prepare  build and start the app on the VM privately (no HTTPS, no web
#                                     address needed yet), so the real deploy later takes a minute
#   ./infra/deploy/deploy.sh status   what's running on the VM, plus an https check
#   ./infra/deploy/deploy.sh logs     follow the live logs (Ctrl+C to stop)
#   ./infra/deploy/deploy.sh backup   back up the database and photos right now
#
# It ships the code you have committed (git HEAD) and your backend/.env, then runs
# infra/deploy/remote.sh on the VM. It never prints your keys or the DuckDNS token.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONF="$ROOT/infra/deploy/.env"
BACKEND_ENV="$ROOT/backend/.env"
die() { printf '\n✋ %s\n' "$*" >&2; exit 1; }
say() { printf '\n==> %s\n' "$*"; }

[ -f "$CONF" ] || die "First create your deploy settings: cp infra/deploy/.env.example infra/deploy/.env
   then fill it in (infra/deploy/OWNERACTIONS.md)."
# shellcheck source=/dev/null
. "$CONF"
if [ -z "${VM:-}" ] || [ "$VM" = "azureuser@0.0.0.0" ]; then die "Set VM=azureuser@<public IP> in infra/deploy/.env"; fi
DOMAIN="${DOMAIN:-}"
DOMAIN="${DOMAIN#https://}"
DOMAIN="${DOMAIN#http://}"
DOMAIN="${DOMAIN%%/*}"
SITE=""
resolve_site() { # sets SITE: your own subdomain (DOMAIN) or a DuckDNS name
  if [ -n "$DOMAIN" ]; then
    SITE="$DOMAIN" # its DNS A record points at the VM
    DUCKDNS_SUBDOMAIN=""
    DUCKDNS_TOKEN=""
  else
    [ -n "${DUCKDNS_SUBDOMAIN:-}" ] || die "Set DOMAIN (your own subdomain) or DUCKDNS_SUBDOMAIN + DUCKDNS_TOKEN in infra/deploy/.env"
    [ -n "${DUCKDNS_TOKEN:-}" ] || die "Set DUCKDNS_TOKEN in infra/deploy/.env"
    DUCKDNS_SUBDOMAIN="${DUCKDNS_SUBDOMAIN%.duckdns.org}"
    SITE="$DUCKDNS_SUBDOMAIN.duckdns.org"
  fi
}
DEMO_MODE="${DEMO_MODE:-true}"
case "$DEMO_MODE" in true | false) ;; *) die "DEMO_MODE must be true or false" ;; esac

# The VM's fingerprint is kept in the project (.daha/ is gitignored), not in ~/.ssh/known_hosts.
mkdir -p "$ROOT/.daha"
SSH_OPTS=(-o UserKnownHostsFile="$ROOT/.daha/known_hosts" -o StrictHostKeyChecking=accept-new
  -o ServerAliveInterval=30 -o ConnectTimeout=15)
if [ -n "${SSH_KEY:-}" ]; then
  SSH_KEY="${SSH_KEY/#\~/$HOME}"
  [ -f "$SSH_KEY" ] || die "SSH_KEY file not found: $SSH_KEY"
  SSH_OPTS+=(-i "$SSH_KEY")
fi
# The remote commands below are single-quoted on purpose: they expand on the VM, not here.
# shellcheck disable=SC2029
ssh_vm() { ssh "${SSH_OPTS[@]}" "$VM" "$@"; }
ssh_vm_tty() { ssh -t "${SSH_OPTS[@]}" "$VM" "$@"; }
healthy() { curl -fsS --max-time 10 "https://$SITE/api/health" 2>/dev/null | grep -q '"ok":true'; }

ship() { # $1 = deploy | prepare: send the code and settings, then run remote.sh on the VM
  local mode=$1
  for tool in git ssh curl; do command -v "$tool" >/dev/null || die "This needs $tool on your laptop."; done
  [ -f "$BACKEND_ENV" ] || die "backend/.env is missing. Create it with: make env (then add your keys)."
  for key in HARNESSROUTER_API_KEY HARNESSROUTER_VISION_HARNESS_ID EXA_API_KEY; do
    grep -qE "^$key=[^[:space:]#]" "$BACKEND_ENV" \
      || echo "⚠️  $key is empty in backend/.env, so that feature will say it isn't set up."
  done
  local commit branch host public_ip=""
  commit=$(git -C "$ROOT" rev-parse --short HEAD)
  branch=$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)
  if [ -n "$(git -C "$ROOT" status --porcelain --untracked-files=no)" ]; then
    echo "⚠️  You have uncommitted changes. Only committed code ($commit) is deployed."
  fi
  host="${VM#*@}"
  if [[ "$host" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then public_ip="$host"; fi
  if [ "$mode" = deploy ] && [ -n "$DOMAIN" ] && [ -n "$public_ip" ] && command -v dig >/dev/null; then
    local resolved
    resolved=$(dig +short "$DOMAIN" A 2>/dev/null | tail -1 || true)
    if [ "$resolved" != "$public_ip" ]; then
      echo "⚠️  $DOMAIN points to ${resolved:-nothing yet}, not to the VM ($public_ip)."
      echo "   Add a DNS record: type A, name ${DOMAIN%%.*}, value $public_ip (OWNERACTIONS.md step 2)."
      echo "   HTTPS starts working within a minute or two of the record being right."
    fi
  fi

  say "Connecting to $VM"
  ssh_vm 'mkdir -p ~/daha/config' \
    || die "Can't SSH into $VM. Check VM and SSH_KEY in infra/deploy/.env, and that the VM is running."

  say "Sending the code ($branch @ $commit)"
  git -C "$ROOT" archive --format=tar HEAD \
    | ssh_vm 'rm -rf ~/daha/src.new && mkdir -p ~/daha/src.new && tar -x -C ~/daha/src.new'

  local base_url="https://$SITE"
  [ "$mode" = prepare ] && base_url="http://localhost:3000" # until the real deploy sets the address
  say "Sending your settings and keys (backend/.env, with the server's address applied)"
  {
    grep -vE '^(JWT_SECRET|DEMO_MODE|PUBLIC_BASE_URL|CORS_ORIGINS)=' "$BACKEND_ENV"
    printf '\n# --- set by infra/deploy/deploy.sh (%s) ---\n' "$mode"
    printf 'DEMO_MODE=%s\nPUBLIC_BASE_URL=%s\nCORS_ORIGINS=%s\n' "$DEMO_MODE" "$base_url" "$base_url"
  } | ssh_vm 'umask 077 && cat > ~/daha/config/backend.env.new'
  printf 'MODE=%q\nSITE=%q\nDEMO_MODE=%q\nDUCKDNS_SUBDOMAIN=%q\nDUCKDNS_TOKEN=%q\nPUBLIC_IP=%q\n' \
    "$mode" "$SITE" "$DEMO_MODE" "${DUCKDNS_SUBDOMAIN:-}" "${DUCKDNS_TOKEN:-}" "$public_ip" \
    | ssh_vm 'umask 077 && cat > ~/daha/config/deploy.env'

  say "Setting up the VM and starting DAHA (the first time takes 10-20 minutes)"
  ssh_vm 'bash ~/daha/src.new/infra/deploy/remote.sh'
}

prepare() {
  DUCKDNS_SUBDOMAIN=""
  DUCKDNS_TOKEN=""
  ship prepare
  printf '\n✅ Built and running on the VM, privately (database, backend, website).\n'
  printf '   Not public yet: open ports 80 and 443, set the web address in infra/deploy/.env,\n'
  printf '   then run ./infra/deploy/deploy.sh (about a minute now that everything is built).\n'
}

deploy() {
  resolve_site
  ship deploy
  say "Waiting for https://$SITE (the first certificate can take a minute)"
  for _ in $(seq 1 36); do
    if healthy; then
      printf '\n✅ DAHA is live: https://%s\n' "$SITE"
      printf '   Share that link. On a phone it can go on the home screen like an app:\n'
      printf '   iPhone: Share → Add to Home Screen · Android: ⋮ → Install app\n'
      return 0
    fi
    sleep 5
  done
  die "DAHA is running on the VM, but https://$SITE isn't answering yet.
   Most likely ports 80 and 443 aren't open in the VM's network settings (OWNERACTIONS.md step 1),
   or DuckDNS is still updating. Look at: ./infra/deploy/deploy.sh logs"
}

case "${1:-deploy}" in
  deploy | up) deploy ;;
  prepare) prepare ;;
  status)
    ssh_vm 'cd ~/daha/src && sudo docker compose ps'
    [ -n "$DOMAIN${DUCKDNS_SUBDOMAIN:-}" ] || { echo "(no web address set yet)"; exit 0; }
    resolve_site
    if healthy; then echo "✅ https://$SITE is up"; else echo "❌ https://$SITE isn't answering"; fi
    ;;
  logs) ssh_vm_tty 'cd ~/daha/src && sudo docker compose logs -f --tail 100' ;;
  backup) ssh_vm 'bash ~/daha/src/infra/deploy/backup.sh' ;;
  *) die "Unknown command: $1 (use: deploy, prepare, status, logs, backup)" ;;
esac

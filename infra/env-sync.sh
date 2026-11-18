#!/bin/sh
# `make env`: create your local env files from the committed examples, or, after a `git pull`,
# append any variables the examples gained since. It never changes or removes a line you already
# have, so your keys are safe. Only the *.env.example files are committed (CONTRIBUTING.md →
# "Environment files").
set -eu
cd "$(dirname "$0")/.."

sync_env() {  # $1 = committed example, $2 = your local file (gitignored)
  example=$1
  target=$2
  if [ ! -s "$target" ]; then
    cp "$example" "$target"
    echo "created $target from $example: fill in the empty keys (CONTRIBUTING.md → Environment files)"
    return
  fi
  missing=$(awk -F= '
    FNR == NR { if ($0 ~ /^[A-Za-z_][A-Za-z0-9_]*=/) have[$1] = 1; next }
    /^[A-Za-z_][A-Za-z0-9_]*=/ && !($1 in have) { print }
  ' "$target" "$example")
  if [ -z "$missing" ]; then
    echo "$target is up to date"
    return
  fi
  {
    printf '\n# --- added by `make env` on %s (new in %s) ---\n' "$(date +%Y-%m-%d)" "$example"
    printf '%s\n' "$missing"
  } >> "$target"
  echo "added to $target (check the values):"
  printf '%s\n' "$missing" | sed 's/=.*//; s/^/  + /'
}

sync_env backend/.env.example backend/.env
sync_env web/.env.example web/.env.local
